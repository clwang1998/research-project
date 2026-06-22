Cycle 11 is complete.

Implemented and committed locally as `106a533` (`Tighten momentum benchmark uncertainty`). Push was attempted but failed because GitHub HTTPS credentials are unavailable in this unattended runtime, so push remains pending.

Key changes:
- Added focused 5d/20d/30d momentum portfolio uncertainty computation.
- Added artifacts under `report/artifacts/momentum_portfolio_uncertainty/`.
- Updated the paper to stop implying the 5d momentum Sharpe is independently significant.
- Reframed 5d momentum as the most reliable tradable benchmark based on positive traded-horizon IC plus lowest turnover.
- Added 5d/20d/30d Sharpe CIs, Newey-West explanation, 884-row DSR definition, and 30d MLP-vs-Route-B-XGBoost clarification.
- Rebuilt `report/sp500_case_study.pdf`; final compile is 10 pages.
- Wrote the requested summary at `output/aris_paper_pm_20260621-193610/cycle_11_codex_summary.md`.

Validation passed:
- `python3 scripts/build_momentum_portfolio_uncertainty.py`
- `python3 -m py_compile scripts/build_momentum_portfolio_uncertainty.py`
- `git diff --check`
- `pdflatex` twice from `report/`

Copilot Opus review file was read first. A post-fix Opus rerun could not run because `mcp__manual_review__review` is not exposed in this runtime.