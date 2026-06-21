# Route B paired increment artifact

- Momentum source: `output/model_search/route_b_factor_residual_alpha_core_20260622__target_excess_sector_fwd_30d__tabular__ridge__linear_alpha_1000/baseline_score_test_backtest.csv`
- Overlay source: `output/alpha_robustness_audit_route_b_30d/residual_overlay_test_backtest.csv`
- Bootstrap: deterministic iid paired resample, seed 20260621, 20,000 draws.

- n_periods: 35
- annualization_rebalances_per_year: 8.4
- momentum_ann_return: 0.07481794761
- overlay_ann_return: 0.08221146436
- increment_ann_return_arithmetic: 0.004952139189
- momentum_period_sd: 0.0362599496
- overlay_period_sd: 0.02894095212
- momentum_ann_vol: 0.1050913181
- overlay_ann_vol: 0.08387884811
- momentum_sharpe: 0.7402730584
- overlay_sharpe: 0.9865229735
- sharpe_gap_overlay_minus_momentum: 0.2462499151
- paired_return_diff_mean_per_period: 0.0005895403796
- paired_return_diff_t_stat: 0.2483079846
- corr_overlay_momentum: 0.9315196388
- momentum_max_drawdown: -0.1382520359
- overlay_max_drawdown: -0.07324214472
- bootstrap_sharpe_gap_ci_2p5: -0.1740099243
- bootstrap_sharpe_gap_ci_97p5: 0.6275797753
- bootstrap_prob_sharpe_gap_positive: 0.8793
- bootstrap_mean_diff_ci_2p5: -0.003849784528
- bootstrap_mean_diff_ci_97p5: 0.005367052249
