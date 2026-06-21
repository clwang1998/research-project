# Experiment Triage for Submission

Updated: 2026-06-22 00:21 CST.

## What To Treat As Main Experiments

0. **P0 robustness audit changes the headline**
   - Source: `output/alpha_robustness_audit/p0_10d_sector_overlay/`.
   - Stop presenting the 10d residual overlay as a production alpha. It is a useful exploratory improvement over momentum on the 2022--2026 test split, but it fails PM-level multiple-testing and factor-attribution checks.
   - The report-safe headline is now: complex ML/GAT does not pass a production-grade robustness audit on this dataset; the residual overlay is the best research lead, not a trade-ready alpha.

| audit | key result | interpretation |
| --- | ---: | --- |
| residual overlay test Sharpe | 0.989 | Better than momentum's 0.746 before statistical deflation. |
| bootstrap Sharpe 95% CI | [-0.066, 2.007] | Too wide; zero is inside the interval. |
| DSR, same target trials | 0.0247 | Not significant after accounting for 196 same-target trials. |
| DSR, all grid trials | 0.00025 | Strong evidence the best-looking result is max-of-grid fragile. |
| CSCV PBO | 34.3% | Moderate overfit risk across 126 overnight strategies. |
| factor-neutral Sharpe | 0.433 | Much weaker after neutralizing against style proxies. |
| Fama--MacBeth signal t-stat | -0.082 | No evidence of independent residual alpha after style proxies. |
| capacity Sharpe at $100M / $1B | 0.902 / 0.713 | Capacity stress is tolerable at small size but fades with impact. |
| survivorship stress haircut Sharpe | 0.839 | Haircut does not destroy the result, but it remains an uncorrected sensitivity. |

1. **Single-factor momentum baseline**
   - Signal: `cs_rank_mom_252d_skip_21d`.
   - Portfolio: sector-neutral long-short, 5 bps cost, 2022+ holdout.
   - This is a strong baseline and must be shown before any complex model.

| target | horizon | holdout RankIC | non-overlap ICIR | net Sharpe | ann. return | max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `target_excess_sector_fwd_5d` | 5d | 0.0234 | 1.016 | 0.627 | 5.92% | -14.60% |
| `target_excess_sector_fwd_10d` | 10d | 0.0271 | 0.812 | 0.746 | 7.05% | -14.59% |
| `target_excess_market_fwd_5d` | 5d | 0.0313 | 1.085 | 0.627 | 5.92% | -14.60% |
| `target_excess_market_fwd_10d` | 10d | 0.0361 | 0.836 | 0.746 | 7.05% | -14.59% |

2. **Best current positive model result**
   - Use this as the strongest model result, not the whole model zoo.
   - Source experiment: `overnight_graph_ablation_mlp_small` prefill.
   - Best credible target so far: `target_excess_sector_fwd_10d`.

| model | variant | RankIC | ICIR | net Sharpe | ann. return | max drawdown | interpretation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| XGBoost balanced | `fixed_graph` | 0.0250 | 0.909 | 1.116 | 8.08% | -5.18% | Beats momentum on ICIR/Sharpe, not on mean RankIC. |
| XGBoost deeper | `fixed_graph` | 0.0229 | 0.978 | 0.540 | 3.24% | -7.98% | Higher ICIR, weaker portfolio Sharpe. |

2b. **Residual overlay that beats the momentum baseline**

This is the cleanest "beat the baseline" result so far. The final signal is:

`z(momentum) + lambda * z(ML score residualized against momentum)`.

The residual is computed cross-sectionally by date, using only same-date scores and no labels. In the narrow validation-selected run, the selected configuration is:

- base model: `target_excess_sector_fwd_10d`, `fixed_graph`, XGBoost balanced,
- residual overlay weight: `lambda=0.25`,
- no EWMA smoothing,
- no no-trade band.

| signal | target | RankIC | ICIR | net Sharpe | ann. return | max drawdown | turnover |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| single momentum baseline | `target_excess_sector_fwd_10d` | 0.0271 | 0.812 | 0.746 | 7.05% | -14.59% | 0.278 |
| residual overlay, val-selected | `target_excess_sector_fwd_10d` | 0.0292 | 0.912 | 0.995 | 8.29% | -12.26% | 0.368 |
| residual overlay, stronger ML weight (`lambda=1.0`, diagnostic only) | `target_excess_sector_fwd_10d` | 0.0332 | 1.205 | 1.297 | 9.44% | -7.60% | 0.509 |

Use the val-selected residual overlay only as the best research lead. The P0 audit shows that it is not a statistically deflated production alpha claim. The `lambda=1.0` line is a useful diagnostic, but do not present it as selected unless a validation rule is added that selects it without looking at the test set.

Seed-bagging note: a 24-member LGBM/XGBoost fixed-graph seed ensemble was tested for the same 10d sector target. It did **not** beat momentum: weighted seed-bag test RankIC 0.0171, ICIR 0.517, Sharpe 0.290, turnover 0.649. Do not use it as a main positive result.

3. **Graph structure ablation**
   - Completed priority run: `priority_graph_ablation_5d10d_tree`.
   - Scope: 5d/10d, tree-only, supervised graph variants `all`, `sector`, `style_knn`, `rolling_corr`, `random`, `no_edges`.
   - Completed 120/120 candidate models.
   - This is the important ablation table for the paper. The result is mostly negative for graph-edge contribution.

Early completed block: `target_excess_sector_fwd_5d`.

| feature variant | best model | test RankIC | test ICIR | test Sharpe | note |
| --- | --- | ---: | ---: | ---: | --- |
| `supervised_graph_random` | XGBoost balanced | 0.0168 | 0.898 | 0.623 | Highest among current graph variants, but it is a placebo graph. |
| `supervised_graph_sector` | LightGBM shallow | 0.0138 | 0.765 | 0.030 | Does not beat random/no-edge. |
| `supervised_graph_style_knn` | XGBoost balanced | 0.0161 | 0.765 | 0.324 | Does not beat random. |
| `supervised_graph_no_edges` | XGBoost balanced | 0.0149 | 0.763 | 0.520 | Similar to real-edge variants. |
| `supervised_graph_all` | LightGBM shallow | 0.0152 | 0.762 | 0.480 | Does not beat random. |
| `supervised_graph_rolling_corr` | LightGBM shallow | 0.0144 | 0.706 | 0.280 | Weakest among shown variants. |

Interpretation so far: the first complete graph-ablation block does **not** support a strong claim that the learned relation-aware GAT edges improve performance. The random graph placebo is currently best by ICIR. Keep this as an honest ablation result unless the remaining 5d market or 10d blocks reverse the pattern.

Second completed block: `target_excess_market_fwd_5d`.

| feature variant | best model | test RankIC | test ICIR | test Sharpe | note |
| --- | --- | ---: | ---: | ---: | --- |
| `supervised_graph_random` | Ridge | 0.0147 | 0.523 | -0.367 | Highest ICIR, but still a placebo. |
| `supervised_graph_all` | Ridge | 0.0134 | 0.505 | -0.548 | Does not beat random. |
| `supervised_graph_sector` | Ridge | 0.0145 | 0.478 | -0.717 | Does not beat random. |
| `supervised_graph_style_knn` | XGBoost shallow | 0.0182 | 0.475 | 0.397 | Better Sharpe than random, lower ICIR. |
| `supervised_graph_rolling_corr` | XGBoost shallow | 0.0183 | 0.449 | 0.527 | Better Sharpe than random, lower ICIR. |
| `supervised_graph_no_edges` | XGBoost shallow | 0.0175 | 0.418 | 0.029 | Weak. |

5d graph conclusion: both sector and market 5d graph ablations fail to beat the single momentum baseline and do not show real edges consistently beating random/no-edge controls.

Third completed block: `target_excess_sector_fwd_10d`.

| feature variant | best model | test RankIC | test ICIR | test Sharpe | note |
| --- | --- | ---: | ---: | ---: | --- |
| `supervised_graph_random` | XGBoost shallow | 0.0272 | 0.932 | 0.975 | Highest ICIR; still a placebo graph. |
| `supervised_graph_no_edges` | XGBoost shallow | 0.0228 | 0.818 | 0.881 | Similar to real-edge variants. |
| `supervised_graph_style_knn` | LightGBM balanced | 0.0214 | 0.812 | 0.637 | Best real-edge variant by ICIR. |
| `supervised_graph_sector` | XGBoost shallow | 0.0224 | 0.808 | 0.841 | Does not beat random. |
| `supervised_graph_all` | Ridge | 0.0185 | 0.748 | 0.186 | Weak. |
| `supervised_graph_rolling_corr` | XGBoost shallow | 0.0213 | 0.647 | 0.695 | Weak. |

10d sector graph conclusion: even where the main residual overlay beats the momentum baseline, the supervised graph relation ablation does not support a graph-edge contribution. The random graph placebo is still best by test ICIR.

Fourth completed block: `target_excess_market_fwd_10d`.

| feature variant | best model | test RankIC | test ICIR | test Sharpe | note |
| --- | --- | ---: | ---: | ---: | --- |
| `supervised_graph_style_knn` | XGBoost shallow | 0.0207 | 0.443 | 0.694 | Best by ICIR; real edge beats random/no-edge here, but still far below momentum ICIR 0.836. |
| `supervised_graph_random` | Ridge | 0.0135 | 0.430 | 0.278 | Placebo remains close to best ICIR. |
| `supervised_graph_sector` | XGBoost shallow | 0.0219 | 0.425 | 0.917 | Best Sharpe in this block, but lower ICIR and below momentum. |
| `supervised_graph_all` | Ridge | 0.0140 | 0.405 | 0.113 | Weak. |
| `supervised_graph_no_edges` | Ridge | 0.0089 | 0.231 | -0.060 | Weak control. |
| `supervised_graph_rolling_corr` | Ridge | 0.0102 | 0.208 | -0.067 | Weakest by ICIR. |

Overall graph conclusion: the supervised GAT pipeline is useful as a controlled experiment, but the current evidence does not justify making graph learning a headline contribution. Across the four 5d/10d blocks, true graph relations do not consistently beat random or no-edge controls, and the 5d blocks do not beat the single momentum baseline. Use this as an honest ablation and keep the paper headline on the residual momentum overlay.

## What Not To Claim

- Do **not** claim the full model family broadly beats single momentum. It does not, based on current holdout results.
- Do **not** use MLP as a headline result. It is unstable and should only enter an ensemble if validation gates pass.
- Do **not** claim Kaggle-style date aggregate features improved results. The first completed sector 5d run was worse than both momentum and the existing tree models.
- Do **not** claim same-family LGBM/XGBoost seed-bagging improved the result. The 24-member seed-bagging ensemble underperformed the momentum baseline.
- Do **not** claim the 10d residual overlay is statistically significant after the full model-selection process. DSR is far below 95%, and the bootstrap Sharpe interval crosses zero.
- Do **not** claim independent style-neutral alpha. The proxy factor-neutral portfolio Sharpe drops to 0.433 and the Fama--MacBeth signal t-stat is approximately -0.08.

## Kaggle/Ubiquant Borrowed Idea

The Kaggle/Ubiquant writeup suggests using time-level feature aggregates as market-state context. I implemented the analogous S&P 500 feature group:

- `data/processed/features_by_group/kaggle_time_agg.parquet`
- 144 date-level aggregate and rolling aggregate features.
- Separate feature map: `data/processed/feature_columns_by_group_kaggle_time_agg.csv`.

Initial result: sector 5d best test ICIR was only 0.569, below single momentum ICIR 1.016. Treat this as a negative exploratory result, not as a main contribution.

## Submission Narrative

The credible paper story after the P0 audit is:

> A simple 12-1 momentum factor remains a strong benchmark. Multivariate tree models and graph features do not produce a production-grade alpha after realistic robustness checks. The best research lead is a 10-day sector-neutral residual overlay of XGBoost on top of momentum, which improves the raw hold-out metrics, but this result fails multiple-testing deflation and loses most of its economic strength after proxy style-factor neutralization. The contribution is therefore a rigorous rejection/triage study and a clear next-step research plan: point-in-time constituents, stronger factor attribution, and capacity-aware turnover control before any trading claim.
