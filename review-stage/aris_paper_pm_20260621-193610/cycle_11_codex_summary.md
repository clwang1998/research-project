# Cycle 11 Codex Summary

## Objective

Use the cycle 11 Copilot Opus quant-PM review to improve the final ARIS paper,
prioritizing claim discipline and report credibility over broad new experiments.

## Implemented Fixes

- Added `scripts/build_momentum_portfolio_uncertainty.py`, a focused audit script
  that recomputes sector-neutral 12-1 momentum at 5d/20d/30d with the production
  evaluator controls and deterministic iid bootstrap Sharpe intervals.
- Added `report/artifacts/momentum_portfolio_uncertainty/` with summary CSV,
  per-horizon return streams, README, and run metadata.
- Updated `report/sp500_case_study.tex` and rebuilt the PDF:
  - 5d momentum is now framed as the most statistically reliable tradable
    benchmark because its traded-horizon IC interval is positive and turnover is
    lowest, not because its Sharpe is statistically significant.
  - 5d/20d/30d momentum portfolio Sharpes are all explicitly described as
    positive but imprecise.
  - Added the 20d caveat: higher Sharpe point estimate than 5d, but IC and
    portfolio uncertainty do not support ranking it as stronger.
  - Added the Newey--West explanation for the rising HAC t-stat.
  - Defined the 884-row Route B full-grid DSR basis.
  - Clarified the broad-grid 30d MLP row versus the residual-label Route B
    XGBoost rerun.

## New Computation

- 5d momentum: n=220, Sharpe 0.6268, mean-return t=1.3095, bootstrap Sharpe CI
  [-0.3187, 1.6266], turnover 0.2212.
- 20d momentum: n=53, Sharpe 0.8219, mean-return t=1.6856, bootstrap Sharpe CI
  [-0.1172, 1.9041], turnover 0.3560.
- 30d momentum: n=35, Sharpe 0.7403, mean-return t=1.5111, bootstrap Sharpe CI
  [-0.2162, 1.8467], turnover 0.4007.

## Validation

- `python3 scripts/build_momentum_portfolio_uncertainty.py` completed.
- `python3 -m py_compile scripts/build_momentum_portfolio_uncertainty.py`
  passed.
- `git diff --check` passed.
- `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex` ran
  twice from `report/`; final PDF compiled to 10 pages.

## Reviewer Gate

The input Copilot Opus review was read first and used as the fix plan. A
post-fix Opus rerun could not be launched from this unattended runtime because
`mcp__manual_review__review` was not exposed; tool discovery returned unrelated
GitHub/Gmail tools only.

## Git

Local commit created: `106a533` (`Tighten momentum benchmark uncertainty`).
`git push` was attempted but failed because HTTPS credentials were unavailable
in the unattended runtime (`could not read Username for 'https://github.com'`).
Push remains pending.

## Remaining Risks

- The paper still has the same core limitation: current-membership data cannot
  quantify deleted constituents or delisting returns.
- The 5d momentum benchmark has significant traded-horizon IC evidence but not a
  statistically tight standalone portfolio Sharpe.
