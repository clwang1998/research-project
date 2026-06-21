#!/usr/bin/env bash
set -euo pipefail

# Route B main experiment from docs/report_improvement_plan.md:
# train compact models on same-date style/sector-neutral residual labels, then
# evaluate raw tradable portfolio returns. This intentionally avoids GAT,
# Kronos, MLP, and broad ablation surfaces.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

USE_VENV="${USE_VENV:-1}"
if [[ "$USE_VENV" == "1" && -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

EXPERIMENT_NAME="${EXPERIMENT_NAME:-route_b_factor_residual_alpha}"
OUT_DIR="${OUT_DIR:-output/model_search}"
HORIZONS="${HORIZONS:-5 10 20 30}"
FAMILIES="${FAMILIES:-excess_sector}"
MODELS="${MODELS:-ridge xgboost}"
FEATURE_VARIANTS="${FEATURE_VARIANTS:-tabular}"
FEATURE_SET="${FEATURE_SET:-core}"
TRAIN_END="${TRAIN_END:-2018-12-31}"
VAL_END="${VAL_END:-2021-12-31}"
START_DATE="${START_DATE:-2001-01-01}"
N_JOBS="${N_JOBS:-8}"
MAX_TRAIN_ROWS="${MAX_TRAIN_ROWS:-800000}"
XGBOOST_DEVICE="${XGBOOST_DEVICE:-cuda}"
LIGHTGBM_DEVICE_TYPE="${LIGHTGBM_DEVICE_TYPE:-cpu}"
SELECTION_METRIC="${SELECTION_METRIC:-sharpe_net}"
TRANSACTION_COST_BPS="${TRANSACTION_COST_BPS:-5}"
RIDGE_ALPHAS="${RIDGE_ALPHAS:-25 100 1000}"
XGBOOST_CANDIDATES_PER_TARGET="${XGBOOST_CANDIDATES_PER_TARGET:-4}"

RESIDUAL_FACTORS="${RESIDUAL_FACTORS:-log_dollar_volume vol_20d beta_60d idio_vol_60d amihud_20d ret_5d mom_252d_skip_21d overnight_ret intraday_ret volume_z_20d market_breadth_20d market_dispersion_20d}"

sector_args=()
if [[ "${SECTOR_NEUTRAL:-1}" == "1" ]]; then
  sector_args=(--sector-neutral)
fi

budget_args=()
if [[ -n "$MAX_TRAIN_ROWS" ]]; then
  budget_args=(--max-train-rows "$MAX_TRAIN_ROWS")
fi

echo "Route B residual-alpha search"
echo "  experiment: $EXPERIMENT_NAME"
echo "  horizons:   $HORIZONS"
echo "  families:   $FAMILIES"
echo "  models:     $MODELS"
echo "  metric:     $SELECTION_METRIC"
echo "  factors:    $RESIDUAL_FACTORS"

python scripts/run_validation_ensemble_search.py \
  --experiment-name "$EXPERIMENT_NAME" \
  --out-dir "$OUT_DIR" \
  --feature-set "$FEATURE_SET" \
  --feature-variants $FEATURE_VARIANTS \
  --models $MODELS \
  --horizons $HORIZONS \
  --families $FAMILIES \
  --start-date "$START_DATE" \
  --train-end "$TRAIN_END" \
  --val-end "$VAL_END" \
  --n-jobs "$N_JOBS" \
  --xgboost-device "$XGBOOST_DEVICE" \
  --lightgbm-device-type "$LIGHTGBM_DEVICE_TYPE" \
  --transaction-cost-bps "$TRANSACTION_COST_BPS" \
  --selection-metric "$SELECTION_METRIC" \
  --ridge-alphas $RIDGE_ALPHAS \
  --xgboost-candidates-per-target "$XGBOOST_CANDIDATES_PER_TARGET" \
  --lightgbm-candidates-per-target 0 \
  --mlp-candidates-per-target 0 \
  --mlp-ensemble-policy exclude \
  --target-residualize-factors $RESIDUAL_FACTORS \
  --target-residualize-sector \
  "${sector_args[@]}" \
  "${budget_args[@]}"
