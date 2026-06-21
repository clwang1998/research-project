# Route B momentum baseline bootstrap artifact

- Momentum source: `output/model_search/route_b_factor_residual_alpha_core_20260622__target_excess_sector_fwd_30d__tabular__ridge__linear_alpha_1000/baseline_score_test_backtest.csv`
- Bootstrap: deterministic iid resample of the 35 non-overlapping 30d net-return periods, seed 20260621, 20,000 draws.
- Annualization: 8.4 rebalances per year.

- n_periods: 35
- momentum_sharpe: 0.7402730584
- mean_return_t_stat: 1.5110760528
- bootstrap_sharpe_ci_2p5: -0.2161506110
- bootstrap_sharpe_ci_97p5: 1.8466938772
- bootstrap_prob_sharpe_positive: 0.9345
- max_drawdown_net: -0.1382520359
