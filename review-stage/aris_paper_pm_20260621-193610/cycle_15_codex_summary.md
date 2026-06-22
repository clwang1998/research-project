# Cycle 15 Codex Summary

## Objective

Improve the final ARIS quant research report using the cycle 15 Copilot Opus
paper-first review, prioritizing claim discipline and PM-level credibility.

## Implemented

- Added `scripts/build_momentum_regime_diagnostics.py`, a focused diagnostic
  that recomputes the no-fit sector-neutral 12--1 momentum book across calendar
  slices using the production evaluator controls.
- Archived the new regime artifacts under
  `report/artifacts/momentum_regime_diagnostics/`.
- Updated `report/sp500_case_study.tex` and rebuilt the PDF so the headline now
  distinguishes signal evidence from portfolio-Sharpe evidence.
- Added explicit regime caveats:
  - 5d momentum Sharpe: -0.95 (2008--2011), 0.33 (2012--2016), -0.14
    (2017--2021), 0.62 (2022--2026).
  - 30d momentum Sharpe: -0.91, 0.20, -0.12, 0.67 over the same slices.
- Clarified that 5d is retained for positive traded-horizon IC, lower turnover,
  and PIT robustness, not as an uncharged best-horizon significance claim.
- Relabeled the 30d LightGBM row as weak validation-ICIR / unaudited at the
  table point of presentation.
- Compressed lower-value implementation detail so the report remains 10 pages.

## Validation

- `git diff --check`: passed.
- `python3 -m py_compile scripts/build_momentum_regime_diagnostics.py`: passed.
- `pdflatex` twice from `report/`: passed.
- PDF page count: 10 pages.

## Reviewer gate

Cycle 15 used the saved Copilot Opus PM review at
`review-stage/20260621-231414-cycle15-quant-pm-copilot-opus.md`. No additional
manual Copilot rerun was available from this unattended Codex runtime.

## Commit / push

- Local commit: `54c9534` (`Tighten ARIS paper regime and Sharpe framing`).
- Push attempted but failed because GitHub HTTPS credentials were unavailable in
  the unattended runtime:
  `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.
- Push remains pending.

## Remaining gaps

- The regime diagnostic is calendar-slice stress evidence, not CPCV or
  independent retraining.
- Saved Route B overlay predictions do not cover pre-2022 history, so the report
  now documents that no pre-2022 overlay Sharpe distribution is available.
- True survivorship correction still requires deleted names and delisting
  returns.
