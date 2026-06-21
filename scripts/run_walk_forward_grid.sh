#!/usr/bin/env bash
# Run the walk-forward grid across feature variants, horizons, target families,
# and models, then build the horizon/model comparison. Each run is one expanding
# walk-forward with yearly folds + a final untouched hold-out, non-overlapping
# rebalance == horizon, overlap-adjusted ICIR, winsorized features, and a
# liquidity-filtered universe.
#
# Override any axis via environment variables, e.g.:
#   FEATURE_VARIANTS="graph" MODELS="ridge lightgbm" HORIZONS="5 20" scripts/run_walk_forward_grid.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PY:-./.venv/bin/python}
FEATURE_VARIANTS=${FEATURE_VARIANTS:-"tabular graph"}
GRAPH_EMBEDDING_PATH=${GRAPH_EMBEDDING_PATH:-data/processed/graph_embeddings/graph_relation_embeddings_daily.parquet}
HORIZONS=${HORIZONS:-"1 5 20 30 90"}
FAMILIES=${FAMILIES:-"excess_market excess_sector"}
MODELS=${MODELS:-"ridge lightgbm xgboost mlp"}
START=${START:-2008-01-01}
FIRST_TRAIN_END=${FIRST_TRAIN_END:-2014-12-31}
HOLDOUT_START=${HOLDOUT_START:-2022-01-01}
MLP_EPOCHS=${MLP_EPOCHS:-20}

OUT=output/walk_forward
mkdir -p "$OUT"
LOG="$OUT/grid_progress.log"
echo "grid start $(date)" > "$LOG"

failures=0
for variant in $FEATURE_VARIANTS; do
  graph_args=()
  case "$variant" in
    tabular)
      ;;
    graph)
      if [[ ! -f "$GRAPH_EMBEDDING_PATH" ]]; then
        echo "Missing graph embedding file: $GRAPH_EMBEDDING_PATH" | tee -a "$LOG"
        exit 1
      fi
      graph_args=(--include-graph-embeddings --graph-embedding-path "$GRAPH_EMBEDDING_PATH")
      ;;
    *)
      echo "Unknown FEATURE_VARIANTS entry: $variant (expected tabular or graph)" | tee -a "$LOG"
      exit 1
      ;;
  esac

  for h in $HORIZONS; do
    for fam in $FAMILIES; do
      for m in $MODELS; do
        if [[ "$variant" = "tabular" ]]; then
          run="${m}_${fam}_${h}d"
        else
          run="${variant}_${m}_${fam}_${h}d"
        fi
        tgt="target_${fam}_fwd_${h}d"
        ret="target_ret_fwd_${h}d"
        extra=()
        if [ "$m" = "mlp" ]; then extra=(--mlp-epochs "$MLP_EPOCHS"); fi
        echo "[$(date +%H:%M:%S)] START $run" | tee -a "$LOG"
        if $PY scripts/run_walk_forward.py --run-name "$run" --model "$m" \
            --start-date "$START" --first-train-end "$FIRST_TRAIN_END" \
            --holdout-start "$HOLDOUT_START" \
            --target-col "$tgt" --return-col "$ret" \
            "${graph_args[@]}" "${extra[@]}" \
            > "$OUT/${run}.log" 2>&1; then
          echo "[$(date +%H:%M:%S)] DONE  $run" | tee -a "$LOG"
        else
          echo "[$(date +%H:%M:%S)] FAIL  $run (see $OUT/${run}.log)" | tee -a "$LOG"
          failures=$((failures + 1))
        fi
      done
    done
  done
done

if [[ "$failures" -gt 0 ]]; then
  echo "grid failed runs: $failures" | tee -a "$LOG"
  exit 1
fi

echo "grid done $(date)" | tee -a "$LOG"
$PY scripts/build_horizon_comparison.py 2>&1 | tee -a "$LOG"
echo "comparison built $(date)" | tee -a "$LOG"
