# Route B cost break-even

This artifact recomputes the 30-day Route B overlay and 30-day momentum baseline from the existing non-overlapping return/turnover streams at alternative per-side transaction costs. The current evaluator charges 5 bps per side on realized turnover.

Key result: The overlay's Sharpe advantage over 30-day momentum is eliminated at about 147.1 bps per side. At 5 bps, the Sharpe gap is 0.246; at 25 bps it is 0.212; at 50 bps it is 0.169; at 100 bps it is 0.082.

Sources:

- `report/artifacts/route_b_momentum_baseline/momentum_baseline_returns.csv`
- `output/alpha_robustness_audit_route_b_30d/residual_overlay_test_backtest.csv`
