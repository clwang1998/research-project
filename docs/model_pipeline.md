# Runnable Modeling Pipeline

This pipeline starts from the already generated feature parquet files in
`data/processed/features_by_group/`. It trains a cross-sectional model for
future relative stock returns and evaluates the score with rank IC, decile
spread, and a long-short portfolio backtest.

## Default Research Design

- Target: `target_excess_sector_fwd_5d`
- Realized portfolio return: `target_ret_fwd_5d`
- Feature set: curated `core` technical, liquidity, market, peer, and
  cross-sectional features
- Baseline: single-factor cross-sectional momentum rank
- Model: ridge regression by default, with optional `lightgbm`, `xgboost`, or
  `sklearn-hgb`
- Split:
  - train: up to `2018-12-31`
  - validation: `2019-01-01` to `2020-12-31`
  - test: after `2020-12-31`
- Leakage controls:
  - effective labels and portfolio returns start after a 1-trading-day execution
    lag by default
  - train/validation rows are purged when their forward label crosses the next
    split boundary; the test/hold-out split is symmetrically purged of rows whose
    forward label extends past the last available trading day
  - validation/test starts are embargoed by the target horizon unless
    `--embargo-days` is set
  - features are winsorized per date at 1%/99% and the universe drops the bottom
    10% by dollar volume each day (`--winsorize-pct`, `--min-dollar-volume-pct`)
  - the rebalance interval defaults to the target horizon so portfolio returns are
    non-overlapping, and rank ICIR is computed on a non-overlapping subsample so
    long horizons are not inflated (`rank_ic_ir` vs reference `rank_ic_ir_raw`)
- Validation: a single static split is the quick path; the canonical evaluation
  is expanding yearly walk-forward with a final untouched hold-out, via
  `scripts/run_walk_forward.py` and the grid in `scripts/run_walk_forward_grid.sh`
- Portfolio: long top decile, short bottom decile, rebalanced every `horizon`
  trading days
- Metrics: rank IC, ICIR, top-bottom spread, annualized return, volatility,
  Sharpe, max drawdown, turnover, and transaction cost

## Setup

```bash
python3 -m pip install -r requirements.txt
```

The default ridge version does not require scikit-learn, LightGBM, or XGBoost.

## Run A Smoke Test

Use this first to confirm the pipeline is working end to end.

```bash
python3 scripts/run_model_pipeline.py \
  --run-name smoke \
  --start-date 2020-01-01 \
  --train-end 2021-12-31 \
  --val-end 2022-12-31 \
  --max-train-rows 50000 \
  --max-eval-rows 50000
```

`--max-eval-rows` preserves complete daily cross-sections, so rank and portfolio
metrics still have valid per-date stock universes. `--max-train-rows` likewise
subsamples **whole dates** (seeded), keeping each selected day's full
cross-section intact rather than dropping individual rows.

## Run The Main Ridge Version

```bash
python3 scripts/run_model_pipeline.py \
  --run-name ridge_core_5d \
  --target-col target_excess_sector_fwd_5d \
  --return-col target_ret_fwd_5d \
  --feature-set core \
  --train-end 2018-12-31 \
  --val-end 2020-12-31 \
  --execution-lag-days 1 \
  --rebalance-every 5 \
  --transaction-cost-bps 5
```

## Optional Boosted Tree Models

Install the package first, then switch `--model`.

```bash
python3 -m pip install lightgbm
python3 scripts/run_model_pipeline.py --run-name lgbm_core_5d --model lightgbm
```

```bash
python3 -m pip install xgboost
python3 scripts/run_model_pipeline.py --run-name xgb_core_5d --model xgboost
```

The script also supports `--model auto`, which uses LightGBM if installed,
then XGBoost, then scikit-learn HistGradientBoosting, otherwise ridge.

## Useful Variants

Use a 10-day or 20-day style horizon:

```bash
python3 scripts/run_model_pipeline.py \
  --run-name ridge_core_20d \
  --target-col target_excess_sector_fwd_20d \
  --return-col target_ret_fwd_20d
```

Disable the default horizon-length embargo only for a diagnostic run:

```bash
python3 scripts/run_model_pipeline.py \
  --run-name ridge_core_5d_no_embargo_diag \
  --embargo-days 0
```

Use all generated features:

```bash
python3 scripts/run_model_pipeline.py \
  --run-name ridge_all_5d \
  --feature-set all
```

Use selected feature groups:

```bash
python3 scripts/run_model_pipeline.py \
  --run-name ridge_momentum_vol \
  --feature-groups price_momentum volatility cross_sectional
```

Run a sector-neutral portfolio construction:

```bash
python3 scripts/run_model_pipeline.py \
  --run-name ridge_core_5d_sector_neutral \
  --sector-neutral
```

## Outputs

Each run writes to `output/model_pipeline/<run-name>/`.

- `summary.md`: report-ready summary table
- `metrics.json`: machine-readable metrics
- `selected_features.csv`: model feature list
- `feature_importance.csv`: ridge coefficients or tree feature importances
- `*_rank_ic.csv`: daily rank IC series
- `*_decile_spread.csv`: daily top-bottom spread series
- `*_backtest.csv`: portfolio return, turnover, cost, and equity curve
- `predictions_val_test.parquet`: optional, only written with
  `--save-predictions`

`summary.md` also includes a split audit table. For a leakage-clean run,
`train.label_end_max` must be no later than `train-end`, and
`val.label_end_max` must be no later than `val-end`.

## Report Interpretation

In the report, present the workflow as:

1. Clean raw S&P 500 OHLCV and company metadata.
2. Build stock-level technical, volatility, liquidity, market, and peer
   features.
3. Define future sector-relative return as the prediction target.
4. Compare a single-factor baseline with a multivariate model.
5. Use time-based validation with label purge, horizon embargo, and one-day
   execution lag to avoid look-ahead leakage.
6. Convert daily scores into a top-decile long and bottom-decile short
   portfolio.
7. Evaluate predictive power with IC and economic value with spread, Sharpe,
   turnover, and transaction costs.

The main limitation to mention is survivorship bias because the dataset uses
the current S&P 500 membership over historical dates.
