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
| Route B overlay, val-selected | ~0.028 | ~0.77 | 0.987 | 8.27% | -7.32% | 0.494 |
| Route B overlay, diagnostic lambda=0.3 | 0.0280 | 0.806 | 1.201 | 9.98% | -6.10% | 0.521 |

Use the validation-selected `lambda=0.2` line only as an exploratory
risk-sleeve result. The diagnostic `lambda=0.3` line is shown for transparency
but was not the validation-selected overlay weight. The overlay IC/ICIR is
cross-convention in the current archived artifacts, so it should be read as
approximately unchanged versus momentum rather than as an ICIR win.

The synchronized local artifacts also preserve the standard-baseline
cross-check: `eval_momentum_baseline.py` now reproduces the 30d sector-relative
momentum row exactly (`output/momentum_baseline_priority/momentum_excess_sector_30d_sector_neutral.json`).
Therefore the Route B overlay's absolute economic comparison can be read under
one local evaluator: +0.247 Sharpe versus standalone 30d momentum before the
DSR/PBO selection charge. The paired increment artifact in
`report/artifacts/route_b_paired_increment/` is more conservative: across the
same 35 rebalance dates, the mean return increment is only 0.059% per period
(about 0.5% annualized), paired return-difference `t=0.25`, overlay--momentum
correlation is 0.93, and the paired bootstrap Sharpe-gap CI is [-0.17, 0.63].
This frames the result as volatility/drawdown dampening, not new residual alpha.

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
| paired overlay-minus-momentum test | t=0.25; corr=0.93 | no statistically distinguishable return increment |
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
> factor-neutral residual labels provides a 30-day overlay that reduces
> volatility and drawdown under the Route B pipeline, but the paired return
> increment is not statistically distinguishable. The result is a candidate
> risk-timing sleeve, not a confirmed alpha: the Rank IC improvement is
> negligible, the full-grid DSR fails, CSCV PBO is 50%, and independent
> style-neutral attribution is weak.

This is materially better than the old graph/MLP/GAT story because it has a clean economic role: the model is not a replacement for momentum; it is a small residual sleeve added to a strong baseline.
