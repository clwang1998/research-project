# P0 Alpha Robustness Audit

Updated: 2026-06-22 01:35 CST.

Note: this file audits the older 10d fixed-graph residual overlay. The rerun requested in
`docs/report_improvement_plan.md` is documented separately in
`docs/route_b_residual_alpha_20260622.md`. The newer Route B result is the preferred
main-experiment candidate; this older audit remains as evidence that the previous
ML/GAT direction should be downgraded.

This audit stops new model/graph ablation work and evaluates the best existing 10-day sector-neutral residual overlay as a PM-facing alpha candidate.

## Selected Signal

Final score:

`z(momentum) + 0.25 * z(XGBoost fixed-graph score residualized against momentum)`

Source run:

`output/model_search/overnight_graph_ablation_mlp_small__target_excess_sector_fwd_10d__fixed_graph__xgboost__xgb_balanced`

Raw 2022--2026 test comparison:

| signal | RankIC | ICIR | net Sharpe | ann. return | max drawdown | turnover |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| momentum baseline | 0.0271 | 0.812 | 0.746 | 7.05% | -14.59% | 0.278 |
| residual overlay | 0.0295 | 0.924 | 0.989 | 8.24% | -12.46% | 0.368 |

This is the best research lead, but it is not a production-grade alpha after the checks below.

## Multiple Testing

| check | result | read |
| --- | ---: | --- |
| bootstrap Sharpe 95% CI | [-0.066, 2.007] | crosses zero |
| DSR, same-target trials | 0.0247 | not significant after 196 same-target trials |
| DSR, full grid trials | 0.00025 | fails after 828 grid trial rows |
| CSCV PBO | 34.3% | moderate overfit risk across 126 strategies |

Conclusion: the raw Sharpe improvement is likely a selected maximum from the grid, not a robust production result.

## Factor Attribution

Proxy style factors used: `log_dollar_volume`, `vol_20d`, `beta_60d`, `amihud_20d`, `ret_5d`, `mom_252d_skip_21d`.

| signal | RankIC | ICIR | net Sharpe | ann. return | Fama--MacBeth signal t-stat |
| --- | ---: | ---: | ---: | ---: | ---: |
| raw residual overlay | 0.0295 | 0.924 | 0.989 | 8.24% | n/a |
| factor-neutral overlay | 0.0214 | 0.973 | 0.433 | 2.38% | -0.082 |

Conclusion: there is not enough evidence of independent style-neutral residual alpha.

## Capacity And Impact

Impact model: explicit 5 bps cost plus square-root impact calibrated to 10 bps at 1% ADV participation.

| AUM | net Sharpe | ann. return | p95 participation |
| ---: | ---: | ---: | ---: |
| $10M | 0.962 | 8.01% | 0.25% |
| $100M | 0.902 | 7.51% | 2.45% |
| $500M | 0.794 | 6.61% | 12.25% |
| $1B | 0.713 | 5.93% | 24.51% |

Conclusion: capacity is plausible only at smaller scale; short-side liquidity and turnover are first-order constraints.

## Survivorship Haircut

This is a sensitivity overlay, not a correction. True correction requires point-in-time constituents plus delisting returns.

| scenario | annual delisting rate | delisting return | Sharpe after haircut |
| --- | ---: | ---: | ---: |
| low | 1% | -30% | 0.971 |
| base | 2% | -30% | 0.953 |
| stress | 5% | -50% | 0.839 |

## Report-Safe Conclusion

Do not claim the current ML/GAT system beats the baseline as a tradeable alpha. The correct conclusion is:

> Momentum remains the only robust benchmark. The residual ML overlay is an interesting research lead because it improves raw hold-out metrics, but it fails multiple-testing deflation and has no convincing independent style-neutral alpha. Before any trading claim, the next iteration needs point-in-time constituents, delisting returns, style-factor-neutral IC/Fama--MacBeth, and capacity-aware turnover selection.
