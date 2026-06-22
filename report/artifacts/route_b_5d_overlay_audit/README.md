# Route B 5d overlay audit

Focused post-training audit for the endorsed 5-day horizon. The script
selects the residual-overlay lambda on validation Sharpe, then evaluates
the selected overlay versus the standalone momentum baseline on the
2022--2026 hold-out. It does not train models.

## Paired summary

| metric                             |      value |
|:-----------------------------------|-----------:|
| selected_lambda                    |   1.000000 |
| n_periods                          | 220.000000 |
| annualization_rebalances_per_year  |  50.400000 |
| momentum_ann_return                |   0.059248 |
| overlay_ann_return                 |   0.051538 |
| increment_ann_return_arithmetic    |  -0.007710 |
| momentum_sharpe                    |   0.626777 |
| overlay_sharpe                     |   0.712683 |
| sharpe_gap_overlay_minus_momentum  |   0.085906 |
| paired_return_diff_mean_per_period |  -0.000153 |
| paired_return_diff_t_stat          |  -0.274086 |
| corr_overlay_momentum              |   0.783438 |
| momentum_max_drawdown              |  -0.145960 |
| overlay_max_drawdown               |  -0.117942 |
| bootstrap_sharpe_gap_ci_2p5        |  -0.547790 |
| bootstrap_sharpe_gap_ci_97p5       |   0.774488 |

## Run metadata

```json
{
  "bootstrap_blocks": 5,
  "bootstrap_samples": 10000,
  "horizon_days": 5,
  "lambda_selection": "maximum validation net Sharpe over supplied lambda grid",
  "lambdas": [
    0.0,
    0.1,
    0.2,
    0.3,
    0.5,
    0.7,
    1.0
  ],
  "prediction_path": "output/model_search/route_b_factor_residual_alpha_core_20260622__target_excess_sector_fwd_5d__tabular__xgboost__xgb_balanced/predictions_val_test.parquet",
  "return_col": "target_ret_fwd_5d",
  "seed": 20260622,
  "selected_lambda": 1.0,
  "target_col": "target_excess_sector_fwd_5d",
  "val_end": "2021-12-31"
}
```
