#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Run the cloud data + feature pipeline from a fresh Git checkout.

Default behavior:
  1. create/use .venv and install Python dependencies
  2. ensure raw Kaggle S&P 500 CSVs exist under data/raw/
  3. build typed interim Parquet files
  4. build grouped feature Parquet files
  5. build feature_columns_by_group.csv
  6. build graph edges, graph embeddings, and diagnostics

Typical cloud run:
  KAGGLE_USERNAME=... KAGGLE_KEY=... scripts/run_cloud_data_pipeline.sh

Smoke test:
  PIPELINE_MODE=smoke KAGGLE_USERNAME=... KAGGLE_KEY=... scripts/run_cloud_data_pipeline.sh

Useful environment variables:
  PIPELINE_MODE=full|smoke          default: full
  RAW_SOURCE=auto|existing|kaggle   default: auto
  KAGGLE_DATASET=andrewmvd/sp-500-stocks
  RUN_SETUP=1|0                    create .venv and pip install requirements
  RUN_GRAPHS=1|0
  RUN_GRAPH_EMBEDDINGS=1|0
  RUN_DIAGNOSTICS=1|0
  RUN_MODEL_SMOKE=1|0              optional quick ridge smoke model
  RUN_TARGET_GRID=1|0              optional long model grid
  RUN_KRONOS_DATA=1|0              optional Kronos pkl data preparation
  MAX_SYMBOLS=50                   useful for smoke/debug runs
  START_DATE=YYYY-MM-DD
  END_DATE=YYYY-MM-DD
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_CMD="$PYTHON_BIN"
VENV_DIR="${VENV_DIR:-.venv}"
USE_VENV="${USE_VENV:-1}"
RUN_SETUP="${RUN_SETUP:-1}"
PIPELINE_MODE="${PIPELINE_MODE:-full}"
RAW_SOURCE="${RAW_SOURCE:-auto}"
RAW_DIR="${RAW_DIR:-data/raw}"
KAGGLE_DATASET="${KAGGLE_DATASET:-andrewmvd/sp-500-stocks}"
FORCE_DOWNLOAD="${FORCE_DOWNLOAD:-0}"

RUN_PREPARE_DATA="${RUN_PREPARE_DATA:-1}"
RUN_FEATURES="${RUN_FEATURES:-1}"
RUN_FEATURE_MAP="${RUN_FEATURE_MAP:-1}"
RUN_GRAPHS="${RUN_GRAPHS:-1}"
RUN_GRAPH_EMBEDDINGS="${RUN_GRAPH_EMBEDDINGS:-1}"
RUN_DIAGNOSTICS="${RUN_DIAGNOSTICS:-1}"
RUN_MODEL_SMOKE="${RUN_MODEL_SMOKE:-0}"
RUN_TARGET_GRID="${RUN_TARGET_GRID:-0}"
RUN_KRONOS_DATA="${RUN_KRONOS_DATA:-0}"

COMPRESSION="${COMPRESSION:-zstd}"
LOG_ROOT="${LOG_ROOT:-output/cloud_pipeline/logs}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="$LOG_ROOT/$TIMESTAMP"

STOCKS_CSV="${STOCKS_CSV:-$RAW_DIR/sp500_stocks.csv}"
COMPANIES_CSV="${COMPANIES_CSV:-$RAW_DIR/sp500_companies.csv}"
STOCKS_PARQUET="${STOCKS_PARQUET:-data/interim/sp500_stocks_typed.parquet}"
COMPANIES_PARQUET="${COMPANIES_PARQUET:-data/interim/sp500_companies_typed.parquet}"
PREPARE_METADATA="${PREPARE_METADATA:-data/interim/prepare_data_metadata.json}"
FEATURE_OUT_DIR="${FEATURE_OUT_DIR:-data/processed/features_by_group}"
FEATURE_MANIFEST="${FEATURE_MANIFEST:-data/processed/feature_manifest.csv}"
FEATURE_METADATA="${FEATURE_METADATA:-data/processed/feature_group_metadata.json}"
FEATURE_MAP="${FEATURE_MAP:-data/processed/feature_columns_by_group.csv}"
GRAPH_OUT_DIR="${GRAPH_OUT_DIR:-data/processed/graphs}"
GRAPH_EMBEDDING_OUT_DIR="${GRAPH_EMBEDDING_OUT_DIR:-data/processed/graph_embeddings}"
DIAGNOSTICS_OUT_DIR="${DIAGNOSTICS_OUT_DIR:-output/diagnostics}"
MODEL_OUT_DIR="${MODEL_OUT_DIR:-output/model_pipeline}"

if [[ "$PIPELINE_MODE" == "smoke" ]]; then
  MAX_SYMBOLS="${MAX_SYMBOLS:-50}"
  START_DATE="${START_DATE:-2018-01-01}"
  END_DATE="${END_DATE:-2021-12-31}"
  GRAPH_REBALANCE_STEP="${GRAPH_REBALANCE_STEP:-60}"
  GRAPH_MIN_HISTORY_DAYS="${GRAPH_MIN_HISTORY_DAYS:-120}"
  GRAPH_SKIP_DAILY="${GRAPH_SKIP_DAILY:-1}"
  DIAGNOSTICS_MIN_NAMES_PER_DATE="${DIAGNOSTICS_MIN_NAMES_PER_DATE:-5}"
  MODEL_MIN_NAMES_PER_DATE="${MODEL_MIN_NAMES_PER_DATE:-5}"
  MODEL_MAX_TRAIN_ROWS="${MODEL_MAX_TRAIN_ROWS:-20000}"
  MODEL_MAX_EVAL_ROWS="${MODEL_MAX_EVAL_ROWS:-8000}"
else
  MAX_SYMBOLS="${MAX_SYMBOLS:-}"
  START_DATE="${START_DATE:-}"
  END_DATE="${END_DATE:-}"
  GRAPH_REBALANCE_STEP="${GRAPH_REBALANCE_STEP:-20}"
  GRAPH_MIN_HISTORY_DAYS="${GRAPH_MIN_HISTORY_DAYS:-252}"
  GRAPH_SKIP_DAILY="${GRAPH_SKIP_DAILY:-0}"
  DIAGNOSTICS_MIN_NAMES_PER_DATE="${DIAGNOSTICS_MIN_NAMES_PER_DATE:-100}"
  MODEL_MIN_NAMES_PER_DATE="${MODEL_MIN_NAMES_PER_DATE:-100}"
  MODEL_MAX_TRAIN_ROWS="${MODEL_MAX_TRAIN_ROWS:-}"
  MODEL_MAX_EVAL_ROWS="${MODEL_MAX_EVAL_ROWS:-}"
fi

mkdir -p "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

run_step() {
  local name="$1"
  shift
  local log_file="$LOG_DIR/${name}.log"
  log "START $name: $*"
  "$@" 2>&1 | tee "$log_file"
  local status=${PIPESTATUS[0]}
  if [[ "$status" -ne 0 ]]; then
    log "FAILED $name; see $log_file"
    exit "$status"
  fi
  log "DONE $name"
}

OPTIONAL_SCOPE_ARGS=()

build_optional_scope_args() {
  OPTIONAL_SCOPE_ARGS=()
  if [[ -n "$MAX_SYMBOLS" ]]; then
    OPTIONAL_SCOPE_ARGS+=(--max-symbols "$MAX_SYMBOLS")
  fi
  if [[ -n "$START_DATE" ]]; then
    OPTIONAL_SCOPE_ARGS+=(--start-date "$START_DATE")
  fi
  if [[ -n "$END_DATE" ]]; then
    OPTIONAL_SCOPE_ARGS+=(--end-date "$END_DATE")
  fi
}

setup_python() {
  if [[ "$RUN_SETUP" == "1" ]]; then
    if [[ ! -d "$VENV_DIR" ]]; then
      "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    PYTHON_CMD=python
    run_step setup_pip "$PYTHON_CMD" -m pip install --upgrade pip
    run_step install_requirements "$PYTHON_CMD" -m pip install -r requirements.txt
  elif [[ "$USE_VENV" == "1" && -d "$VENV_DIR" ]]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    PYTHON_CMD=python
  fi
}

install_kaggle_if_needed() {
  if ! "$PYTHON_CMD" - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("kaggle") else 1)
PY
  then
    run_step install_kaggle "$PYTHON_CMD" -m pip install kaggle
  fi
}

ensure_kaggle_auth() {
  if [[ -n "${KAGGLE_JSON:-}" ]]; then
    mkdir -p "$HOME/.kaggle"
    printf '%s' "$KAGGLE_JSON" > "$HOME/.kaggle/kaggle.json"
    chmod 600 "$HOME/.kaggle/kaggle.json"
  fi

  if [[ -f "$HOME/.kaggle/kaggle.json" ]]; then
    chmod 600 "$HOME/.kaggle/kaggle.json" || true
    return
  fi

  if [[ -n "${KAGGLE_USERNAME:-}" && -n "${KAGGLE_KEY:-}" ]]; then
    return
  fi

  cat >&2 <<'MSG'
Kaggle credentials are missing.

Set either:
  KAGGLE_USERNAME=... KAGGLE_KEY=...

or:
  KAGGLE_JSON='{"username":"...","key":"..."}'

or upload ~/.kaggle/kaggle.json to the cloud host.
MSG
  exit 2
}

download_raw_from_kaggle() {
  install_kaggle_if_needed
  ensure_kaggle_auth

  local download_dir="$RAW_DIR/_kaggle_download"
  if [[ "$FORCE_DOWNLOAD" == "1" ]]; then
    rm -rf "$download_dir"
  fi
  mkdir -p "$download_dir"
  run_step download_kaggle_dataset kaggle datasets download -d "$KAGGLE_DATASET" -p "$download_dir" --unzip

  local stocks_src
  local companies_src
  stocks_src="$(find "$download_dir" -type f -name 'sp500_stocks.csv' | head -n 1 || true)"
  companies_src="$(find "$download_dir" -type f -name 'sp500_companies.csv' | head -n 1 || true)"

  if [[ -z "$stocks_src" || -z "$companies_src" ]]; then
    cat >&2 <<MSG
Downloaded dataset did not contain sp500_stocks.csv and sp500_companies.csv.
Dataset: $KAGGLE_DATASET
Download dir: $download_dir
MSG
    exit 2
  fi

  mkdir -p "$RAW_DIR"
  cp "$stocks_src" "$STOCKS_CSV"
  cp "$companies_src" "$COMPANIES_CSV"
}

ensure_raw_data() {
  if [[ "$RAW_SOURCE" == "auto" ]]; then
    if [[ -f "$STOCKS_CSV" && -f "$COMPANIES_CSV" && "$FORCE_DOWNLOAD" != "1" ]]; then
      RAW_SOURCE="existing"
    else
      RAW_SOURCE="kaggle"
    fi
  fi

  case "$RAW_SOURCE" in
    existing)
      ;;
    kaggle)
      download_raw_from_kaggle
      ;;
    *)
      echo "Unsupported RAW_SOURCE=$RAW_SOURCE; use auto, existing, or kaggle." >&2
      exit 2
      ;;
  esac

  if [[ ! -f "$STOCKS_CSV" || ! -f "$COMPANIES_CSV" ]]; then
    echo "Missing raw files: $STOCKS_CSV and/or $COMPANIES_CSV" >&2
    exit 2
  fi
}

run_pipeline() {
  if [[ "$RUN_PREPARE_DATA" == "1" ]]; then
    run_step prepare_data "$PYTHON_CMD" scripts/prepare_data.py \
      --stocks-csv "$STOCKS_CSV" \
      --companies-csv "$COMPANIES_CSV" \
      --stocks-out "$STOCKS_PARQUET" \
      --companies-out "$COMPANIES_PARQUET" \
      --metadata "$PREPARE_METADATA" \
      --compression "$COMPRESSION"
  fi

  if [[ "$RUN_FEATURES" == "1" ]]; then
    local feature_args=(
      scripts/make_feature_groups.py
      --stocks "$STOCKS_PARQUET"
      --companies "$COMPANIES_PARQUET"
      --out-dir "$FEATURE_OUT_DIR"
      --manifest "$FEATURE_MANIFEST"
      --metadata "$FEATURE_METADATA"
      --compression "$COMPRESSION"
    )
    build_optional_scope_args
    feature_args+=("${OPTIONAL_SCOPE_ARGS[@]}")
    run_step make_feature_groups "$PYTHON_CMD" "${feature_args[@]}"
  fi

  if [[ "$RUN_FEATURE_MAP" == "1" ]]; then
    run_step build_feature_column_map "$PYTHON_CMD" scripts/build_feature_column_map.py \
      --feature-dir "$FEATURE_OUT_DIR" \
      --out "$FEATURE_MAP"
  fi

  if [[ "$RUN_GRAPHS" == "1" ]]; then
    run_step build_graph_edges "$PYTHON_CMD" scripts/build_graph_edges.py \
      --feature-dir "$FEATURE_OUT_DIR" \
      --out-dir "$GRAPH_OUT_DIR" \
      --rebalance-step "$GRAPH_REBALANCE_STEP" \
      --min-history-days "$GRAPH_MIN_HISTORY_DAYS" \
      --compression "$COMPRESSION"
  fi

  if [[ "$RUN_GRAPH_EMBEDDINGS" == "1" ]]; then
    local emb_args=(
      scripts/make_graph_embeddings.py
      --graph-dir "$GRAPH_OUT_DIR"
      --feature-dir "$FEATURE_OUT_DIR"
      --out-dir "$GRAPH_EMBEDDING_OUT_DIR"
      --compression "$COMPRESSION"
    )
    if [[ "$GRAPH_SKIP_DAILY" == "1" ]]; then
      emb_args+=(--skip-daily)
    fi
    run_step make_graph_embeddings "$PYTHON_CMD" "${emb_args[@]}"
  fi

  if [[ "$RUN_DIAGNOSTICS" == "1" ]]; then
    run_step run_research_diagnostics "$PYTHON_CMD" scripts/run_research_diagnostics.py \
      --stocks "$STOCKS_PARQUET" \
      --targets "$FEATURE_OUT_DIR/targets.parquet" \
      --out-dir "$DIAGNOSTICS_OUT_DIR" \
      --start-date "${START_DATE:-2005-01-01}" \
      --min-names-per-date "$DIAGNOSTICS_MIN_NAMES_PER_DATE"
  fi

  if [[ "$RUN_MODEL_SMOKE" == "1" ]]; then
    local smoke_args=(
      scripts/run_model_pipeline.py
      --feature-dir "$FEATURE_OUT_DIR"
      --feature-map "$FEATURE_MAP"
      --out-dir "$MODEL_OUT_DIR"
      --run-name "cloud_smoke_ridge"
      --model ridge
      --feature-set core
      --min-names-per-date "$MODEL_MIN_NAMES_PER_DATE"
    )
    if [[ -n "$START_DATE" ]]; then
      smoke_args+=(--start-date "$START_DATE")
    fi
    if [[ -n "$END_DATE" ]]; then
      smoke_args+=(--end-date "$END_DATE")
    fi
    if [[ -n "$MODEL_MAX_TRAIN_ROWS" ]]; then
      smoke_args+=(--max-train-rows "$MODEL_MAX_TRAIN_ROWS")
    fi
    if [[ -n "$MODEL_MAX_EVAL_ROWS" ]]; then
      smoke_args+=(--max-eval-rows "$MODEL_MAX_EVAL_ROWS")
    fi
    run_step run_model_smoke "$PYTHON_CMD" "${smoke_args[@]}"
  fi

  if [[ "$RUN_TARGET_GRID" == "1" ]]; then
    local grid_args=(
      scripts/run_target_model_experiments.py
      --out-dir "$MODEL_OUT_DIR"
      --experiment-name "${TARGET_GRID_NAME:-cloud_target_grid_core}"
      --feature-set core
      --n-jobs "${MODEL_N_JOBS:--1}"
    )
    if [[ -n "$START_DATE" ]]; then
      grid_args+=(--start-date "$START_DATE")
    fi
    if [[ -n "$MODEL_MAX_TRAIN_ROWS" ]]; then
      grid_args+=(--max-train-rows "$MODEL_MAX_TRAIN_ROWS")
    fi
    if [[ -n "$MODEL_MAX_EVAL_ROWS" ]]; then
      grid_args+=(--max-eval-rows "$MODEL_MAX_EVAL_ROWS")
    fi
    run_step run_target_model_experiments "$PYTHON_CMD" "${grid_args[@]}"
  fi

  if [[ "$RUN_KRONOS_DATA" == "1" ]]; then
    local kronos_args=(scripts/prepare_kronos_sp500.py --stocks-csv "$STOCKS_CSV")
    if [[ -n "$MAX_SYMBOLS" ]]; then
      kronos_args+=(--max-symbols "$MAX_SYMBOLS")
    fi
    run_step prepare_kronos_sp500 "$PYTHON_CMD" "${kronos_args[@]}"
  fi
}

setup_python
ensure_raw_data
run_pipeline

cat <<MSG

Cloud data pipeline complete.

Raw data:        $RAW_DIR
Interim data:    data/interim
Feature groups:  $FEATURE_OUT_DIR
Feature map:     $FEATURE_MAP
Graphs:          $GRAPH_OUT_DIR
Graph embeds:    $GRAPH_EMBEDDING_OUT_DIR
Diagnostics:     $DIAGNOSTICS_OUT_DIR
Logs:            $LOG_DIR
MSG
