#!/usr/bin/env bash
# Overnight supervised-GAT + validation-ensemble search driver.
#
# This script is designed for the remote GPU host. It is resumable: completed
# model/GAT runs are skipped by their output artifacts.
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
USE_VENV="${USE_VENV:-1}"
RUN_SETUP="${RUN_SETUP:-1}"

EXPERIMENT_NAME="${EXPERIMENT_NAME:-overnight_supervised_gat_ensemble}"
SEARCH_OUT_DIR="${SEARCH_OUT_DIR:-output/model_search}"
GAT_OUT_DIR="${GAT_OUT_DIR:-data/processed/supervised_graph_embeddings}"
LOG_DIR="${LOG_DIR:-output/overnight_search/logs/$(date -u +%Y%m%dT%H%M%SZ)}"

SEARCH_HORIZONS="${SEARCH_HORIZONS:-1 5 10 20}"
SEARCH_FAMILIES="${SEARCH_FAMILIES:-excess_sector excess_market}"
GAT_HORIZONS="${GAT_HORIZONS:-$SEARCH_HORIZONS}"
GAT_FAMILIES="${GAT_FAMILIES:-$SEARCH_FAMILIES}"

START_DATE="${START_DATE:-2001-01-01}"
TRAIN_END="${TRAIN_END:-2018-12-31}"
VAL_END="${VAL_END:-2021-12-31}"
FEATURE_SET="${FEATURE_SET:-all}"
GAT_FEATURE_SET="${GAT_FEATURE_SET:-all}"

CPU_MODELS="${CPU_MODELS:-ridge lightgbm xgboost}"
FULL_MODELS="${FULL_MODELS:-ridge lightgbm xgboost mlp}"
CPU_FEATURE_VARIANTS="${CPU_FEATURE_VARIANTS:-tabular fixed_graph}"
FULL_FEATURE_VARIANTS="${FULL_FEATURE_VARIANTS:-tabular fixed_graph supervised_graph graph_supervised}"

N_JOBS="${N_JOBS:-8}"
XGBOOST_DEVICE="${XGBOOST_DEVICE:-cpu}"
LIGHTGBM_DEVICE_TYPE="${LIGHTGBM_DEVICE_TYPE:-cpu}"
SECTOR_NEUTRAL="${SECTOR_NEUTRAL:-1}"
MAX_TRAIN_ROWS="${MAX_TRAIN_ROWS:-800000}"
MAX_EVAL_ROWS="${MAX_EVAL_ROWS:-}"
RIDGE_ALPHAS="${RIDGE_ALPHAS:-25}"
LIGHTGBM_CANDIDATES_PER_TARGET="${LIGHTGBM_CANDIDATES_PER_TARGET:-0}"
XGBOOST_CANDIDATES_PER_TARGET="${XGBOOST_CANDIDATES_PER_TARGET:-0}"
MLP_CANDIDATES_PER_TARGET="${MLP_CANDIDATES_PER_TARGET:-12}"
MLP_EPOCHS="${MLP_EPOCHS:-30}"

GAT_HIDDEN_DIM="${GAT_HIDDEN_DIM:-64}"
GAT_EMBEDDING_DIM="${GAT_EMBEDDING_DIM:-16}"
GAT_EPOCHS="${GAT_EPOCHS:-40}"
GAT_PATIENCE="${GAT_PATIENCE:-6}"
GAT_BATCH_DATES="${GAT_BATCH_DATES:-4}"
GAT_LR="${GAT_LR:-0.0003}"
GAT_DROPOUT="${GAT_DROPOUT:-0.1}"
GAT_LOSS="${GAT_LOSS:-huber}"

GPU_MIN_FREE_MB="${GPU_MIN_FREE_MB:-24000}"
GPU_MAX_UTIL_PCT="${GPU_MAX_UTIL_PCT:-35}"
GPU_WAIT_POLL_SECONDS="${GPU_WAIT_POLL_SECONDS:-120}"
GPU_WAIT_TIMEOUT_SECONDS="${GPU_WAIT_TIMEOUT_SECONDS:-0}"

mkdir -p "$LOG_DIR" "$SEARCH_OUT_DIR" "$GAT_OUT_DIR"
mkdir -p output/overnight_search
basename "$LOG_DIR" > output/overnight_search/latest_run_id

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG_DIR/driver.log"
}

setup_python() {
  if [[ "$RUN_SETUP" == "1" ]]; then
    if [[ ! -d "$VENV_DIR" ]]; then
      "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
  elif [[ "$USE_VENV" == "1" && -d "$VENV_DIR" ]]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
  fi
}

processed_data_ready() {
  [[ -f data/processed/features_by_group/targets.parquet \
     && -f data/processed/graphs/sector_edges.parquet \
     && -f data/processed/graph_embeddings/graph_relation_embeddings_daily.parquet ]] || return 1
  SEARCH_HORIZONS="$SEARCH_HORIZONS" SEARCH_FAMILIES="$SEARCH_FAMILIES" python - <<'PY'
import os
import sys
from pathlib import Path

try:
    import pyarrow.parquet as pq
except Exception as exc:
    print(f"Unable to inspect targets parquet schema: {exc}", file=sys.stderr)
    sys.exit(1)

path = Path("data/processed/features_by_group/targets.parquet")
horizons = [h for h in os.environ.get("SEARCH_HORIZONS", "").split() if h]
families = [f for f in os.environ.get("SEARCH_FAMILIES", "").split() if f]
required = {f"target_ret_fwd_{h}d" for h in horizons}
for family in families:
    required.update(f"target_{family}_fwd_{h}d" for h in horizons)
available = set(pq.ParquetFile(path).schema_arrow.names)
missing = sorted(required - available)
if missing:
    print("targets.parquet missing required columns: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)
PY
}

ensure_data() {
  if processed_data_ready; then
    return
  fi
  log "Processed data missing or stale; rebuilding data pipeline."
  RUN_MODEL_SMOKE=0 RUN_TARGET_GRID=0 scripts/run_cloud_data_pipeline.sh \
    > "$LOG_DIR/data_pipeline.log" 2>&1
}

gpu_is_ready() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    return 1
  fi
  local line used total util free
  line="$(nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits | head -n 1)"
  used="$(printf '%s' "$line" | awk -F, '{gsub(/ /,"",$1); print $1}')"
  total="$(printf '%s' "$line" | awk -F, '{gsub(/ /,"",$2); print $2}')"
  util="$(printf '%s' "$line" | awk -F, '{gsub(/ /,"",$3); print $3}')"
  free=$((total - used))
  [[ "$free" -ge "$GPU_MIN_FREE_MB" && "$util" -le "$GPU_MAX_UTIL_PCT" ]]
}

wait_for_gpu() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    log "nvidia-smi not found; supervised GAT will run on CPU."
    return
  fi
  local start now elapsed
  start="$(date +%s)"
  while ! gpu_is_ready; do
    nvidia-smi --query-gpu=timestamp,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits \
      | tee -a "$LOG_DIR/gpu_wait.log" >/dev/null || true
    if [[ "$GPU_WAIT_TIMEOUT_SECONDS" -gt 0 ]]; then
      now="$(date +%s)"
      elapsed=$((now - start))
      if [[ "$elapsed" -ge "$GPU_WAIT_TIMEOUT_SECONDS" ]]; then
        log "GPU wait timed out after ${elapsed}s; continuing with CPU fallback."
        return
      fi
    fi
    sleep "$GPU_WAIT_POLL_SECONDS"
  done
  log "GPU is ready."
}

run_search_phase() {
  local phase_name="$1"
  local models="$2"
  local variants="$3"
  local -a sector_args=()
  local -a budget_args=()
  log "START search phase ${phase_name}: models=${models}; variants=${variants}"
  # shellcheck disable=SC2086
  if [[ "$SECTOR_NEUTRAL" == "1" ]]; then
    sector_args+=(--sector-neutral)
  fi
  if [[ -n "$MAX_TRAIN_ROWS" ]]; then
    budget_args+=(--max-train-rows "$MAX_TRAIN_ROWS")
  fi
  if [[ -n "$MAX_EVAL_ROWS" ]]; then
    budget_args+=(--max-eval-rows "$MAX_EVAL_ROWS")
  fi
  python scripts/run_validation_ensemble_search.py \
    --experiment-name "$EXPERIMENT_NAME" \
    --out-dir "$SEARCH_OUT_DIR" \
    --supervised-gat-root "$GAT_OUT_DIR" \
    --feature-set "$FEATURE_SET" \
    --feature-variants $variants \
    --models $models \
    --horizons $SEARCH_HORIZONS \
    --families $SEARCH_FAMILIES \
    --start-date "$START_DATE" \
    --train-end "$TRAIN_END" \
    --val-end "$VAL_END" \
    --n-jobs "$N_JOBS" \
    --xgboost-device "$XGBOOST_DEVICE" \
    --lightgbm-device-type "$LIGHTGBM_DEVICE_TYPE" \
    "${sector_args[@]}" \
    "${budget_args[@]}" \
    --ridge-alphas $RIDGE_ALPHAS \
    --lightgbm-candidates-per-target "$LIGHTGBM_CANDIDATES_PER_TARGET" \
    --xgboost-candidates-per-target "$XGBOOST_CANDIDATES_PER_TARGET" \
    --mlp-candidates-per-target "$MLP_CANDIDATES_PER_TARGET" \
    --mlp-epochs "$MLP_EPOCHS" \
    > "$LOG_DIR/search_${phase_name}.log" 2>&1
  log "DONE search phase ${phase_name}"
}

gat_run_name() {
  local target="$1"
  printf 'supervised_gat__%s' "$target"
}

train_gat_targets() {
  local device="cpu"
  if command -v nvidia-smi >/dev/null 2>&1 && gpu_is_ready; then
    device="cuda"
  fi
  for h in $GAT_HORIZONS; do
    for family in $GAT_FAMILIES; do
      local target="target_${family}_fwd_${h}d"
      local ret="target_ret_fwd_${h}d"
      local run
      run="$(gat_run_name "$target")"
      if [[ -f "$GAT_OUT_DIR/$run/supervised_gat_oof_embeddings.parquet" ]]; then
        log "Skip completed GAT $target"
        continue
      fi
      log "START supervised GAT $target on $device"
      python scripts/train_supervised_gat.py \
        --run-name "$run" \
        --out-dir "$GAT_OUT_DIR" \
        --feature-set "$GAT_FEATURE_SET" \
        --target-col "$target" \
        --return-col "$ret" \
        --start-date "$START_DATE" \
        --train-end "$TRAIN_END" \
        --val-end "$VAL_END" \
        --hidden-dim "$GAT_HIDDEN_DIM" \
        --embedding-dim "$GAT_EMBEDDING_DIM" \
        --epochs "$GAT_EPOCHS" \
        --patience "$GAT_PATIENCE" \
        --batch-dates "$GAT_BATCH_DATES" \
        --lr "$GAT_LR" \
        --dropout "$GAT_DROPOUT" \
        --loss "$GAT_LOSS" \
        --device "$device" \
        > "$LOG_DIR/gat_${target}.log" 2>&1
      log "DONE supervised GAT $target"
    done
  done
}

main() {
  log "overnight search start"
  setup_python
  ensure_data

  run_search_phase "cpu_prefill" "$CPU_MODELS" "$CPU_FEATURE_VARIANTS" &
  cpu_pid=$!

  wait_for_gpu
  train_gat_targets

  wait "$cpu_pid"
  run_search_phase "full_after_gat" "$FULL_MODELS" "$FULL_FEATURE_VARIANTS"
  log "overnight search done"
}

main "$@"
