# Route B Residual Alpha Rerun

Updated: 2026-06-22 01:33 CST.

This rerun follows `docs/report_improvement_plan.md`: stop graph/Kronos/MLP ablations, train compact models on factor-neutral residual labels, and evaluate a momentum-plus-residual overlay.

## Experiment

- Experiment: `route_b_factor_residual_alpha_core_20260622`, trained on the GPU
  server and mirrored locally under
  `output/model_search/route_b_factor_residual_alpha_core_20260622*`.
- Models: Ridge and XGBoost only.
- Feature set: `core` plus residualization factors.
- Horizons: 5d, 10d, 20d, 30d.
- Target family: `target_excess_sector_fwd_*d`.
- Residual target controls: sector dummies, `log_dollar_volume`, `vol_20d`, `beta_60d`, `idio_vol_60d`, `amihud_20d`, `ret_5d`, `mom_252d_skip_21d`, `overnight_ret`, `intraday_ret`, `volume_z_20d`, `market_breadth_20d`, `market_dispersion_20d`.
- Selection metric: validation `sharpe_net`.

## Main Result

The best usable result is the 30d residual overlay:

`z(momentum) + 0.2 * z(residual-target XGBoost score)`

where the XGBoost model is `xgb_balanced` trained on the 30d factor-neutral residual label.

| 30d signal | test raw RankIC | test raw ICIR | net Sharpe | ann. return | max drawdown | turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| momentum baseline | 0.0282 | 0.698 | 0.740 | 7.78% | -13.83% | 0.401 |
| Route B overlay, val-selected | 0.0283 | 0.768 | 0.970 | 8.08% | -6.96% | 0.492 |

Use the validation-selected `lambda=0.2` line as the report-safe positive
result. The diagnostic `lambda=0.3` line exists in
`output/model_search/route_b_factor_residual_alpha_core_20260622_30d_ultra_blend_metrics.csv`
with test Sharpe 1.20, but it is intentionally excluded from the main table
because it was not the validation-selected overlay weight.

The synchronized local artifacts also preserve the standard-baseline
cross-check: `eval_momentum_baseline.py` reproduces the 30d signal metrics and
turnover closely, but gives a different standalone momentum Sharpe
(`0.802` rather than the Route B pipeline's `0.740`). Therefore the Route B
overlay improvement should be read under one internal pipeline convention
(+0.23 Sharpe versus Route B momentum), with a conservative cross-convention
read of roughly +0.17 versus the standard baseline script.

## Single Residual Model

The residual model alone should not replace momentum. Its best 30d XGBoost single-model test result was:

| model | test residual RankIC | test residual ICIR | net Sharpe | ann. return | max drawdown | turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| XGBoost shallow | 0.0268 | 1.373 | 0.581 | 3.26% | -6.99% | 0.769 |
| XGBoost balanced | 0.0264 | 1.447 | 0.457 | 2.49% | -9.95% | 0.761 |

Interpretation: the model finds a residual ranking signal, but the standalone residual book has high turnover and weak economics. The useful construction is incremental overlay on momentum.

## Robustness Audit

Post-training audit path, mirrored locally:

`output/alpha_robustness_audit_route_b_30d/`

| check | result | read |
| --- | ---: | --- |
| bootstrap Sharpe 95% CI | [0.019, 1.796] | positive but wide |
| DSR, same-target trials | 0.814 | encouraging within the narrow 30d target search |
| DSR, full-grid trials | 0.003 | fails if charged for the broader experiment zoo |
| CSCV PBO | 50.0% | high overfit risk |
| Fama--MacBeth proxy t-stat | 0.048 | no convincing independent marginal alpha after proxies |

Capacity stress for the Route B overlay:

| AUM | net Sharpe | ann. return | p95 participation |
| ---: | ---: | ---: | ---: |
| $10M | 0.974 | 8.17% | 0.25% |
| $100M | 0.948 | 7.95% | 2.53% |
| $500M | 0.900 | 7.55% | 12.65% |
| $1B | 0.864 | 7.25% | 25.30% |

Survivorship haircut sensitivity:

| scenario | Sharpe after haircut |
| --- | ---: |
| low, 1% delisting at -30% | 0.969 |
| base, 2% delisting at -30% | 0.951 |
| stress, 5% delisting at -50% | 0.837 |

## Report Positioning

The revised report should not claim that complex ML broadly beats momentum. The stronger, defensible statement is:

> Momentum remains the base tradable signal. A compact XGBoost model trained on
> factor-neutral residual labels provides a 30-day incremental overlay that
> improves 2022--2026 holdout Sharpe and drawdown under the Route B pipeline.
> The result is a candidate risk-timing sleeve, not a confirmed alpha: the Rank
> IC improvement is negligible, the full-grid DSR fails, CSCV PBO is 50%, and
> the standalone momentum baseline has a portfolio-convention sensitivity.

This is materially better than the old graph/MLP/GAT story because it has a clean economic role: the model is not a replacement for momentum; it is a small residual sleeve added to a strong baseline.
