# round29 Copilot Opus Review

Source: current VS Code Copilot Chat, read via Computer Use on 2026-06-22 CST.

## Findings

1. Route B direction is methodologically honest: residual-target construction,
   walk-forward validation, removal of GAT/MLP/Kronos from the headline, and the
   "momentum remains core, residual sleeve is exploratory" conclusion are
   defensible.
2. The largest reproducibility issue was that Route B model-search outputs and
   `output/alpha_robustness_audit_route_b_30d/` were only on the GPU server, so
   the report numbers could not be traced from local artifacts.
3. The report mixed two momentum-baseline portfolio conventions: Route B
   pipeline baseline Sharpe 0.740 versus the local standard baseline script
   reproduction Sharpe 0.802. Signal-level metrics match closely, but economic
   metrics differ.
4. The Route B improvement is fragile: Rank IC changes only from roughly 0.0282
   to 0.0283 while Sharpe/drawdown improve, so the result is closer to a
   path-specific risk/drawdown effect than a clearly stronger ranker.
5. The P0 audit should be kept close to any positive claim: full-grid DSR is
   0.003, CSCV PBO is 50%, Fama--MacBeth proxy t-stat is about 0.05, and the
   bootstrap Sharpe interval is wide.
6. The lambda=0.3 diagnostic row should not appear in the main Route B table,
   because it was not validation-selected and is easy to misread as the headline.

## Requested Fixes

- Mirror Route B raw artifacts back to local `output/`.
- Update report/documentation so Route B is locally traceable.
- Keep one consistent interpretation of the momentum baseline convention; if
  both conventions are shown, explicitly state the sensitivity.
- Tighten the language around PBO/DSR and avoid presenting Route B as confirmed
  residual alpha.
- Move or demote the lambda=0.3 diagnostic line.
