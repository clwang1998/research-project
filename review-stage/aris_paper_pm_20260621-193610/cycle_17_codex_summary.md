# Cycle 17 Codex Summary

## Objective

Use the saved Copilot Opus senior quant PM review to improve the final report's
paper-level credibility, with emphasis on claim discipline, benchmark framing,
horizon interpretation, DSR family justification, and Route B cost robustness.

## Implemented

- Tightened the headline PM decision in `report/sp500_case_study.tex`: the 5-day
  momentum book is retained as a research benchmark and possible small paper
  sleeve, but sizing should be based on IC stability and turnover rather than
  the recent-regime Sharpe.
- Relabeled the 1-day momentum IC evidence as non-traded signal-existence
  evidence and kept the 5-day block-bootstrap IC as the traded-horizon support.
- Clarified that the 30-day LightGBM row fails the broad-grid walk-forward mean
  validation RankICIR rule (`0.0804` versus selected MLP `0.4882`), remains
  unaudited, and sits below the 884-trial expected-max null Sharpe.
- Visually demoted the unaudited 30-day LightGBM rows with light shading.
- Added an annualization convention note explaining arithmetic report returns
  versus geometric archived paired-increment returns.
- Added a sentence justifying the 884-trial DSR family as the relevant research
  process family, with the 14-trial same-target DSR treated as a diagnostic.
- Added `report/artifacts/route_b_cost_breakeven/`, a focused transaction-cost
  sensitivity computed from existing Route B and momentum return/turnover
  streams. The overlay Sharpe gap is `0.246` at 5 bps, `0.212` at 25 bps,
  `0.169` at 50 bps, and crosses zero near 147 bps per side.

## Validation

- `git diff --check` passed.
- Route B cost sensitivity recomputed with `python3` from existing artifacts.
- `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex` ran
  twice successfully.
- `report/sp500_case_study.pdf` is 10 pages.
- LaTeX reported one minor underfull hbox warning and no fatal errors.
- No Python scripts were edited, so touched-script compile was not applicable.

## Git

- Local commits created:
  - `d49424c Refine ARIS paper benchmark framing`
  - `4a68b49 Record cycle 17 push status`
- Push attempted to `origin/codex/supervised-gat-ensemble-search` but failed:
  GitHub credentials were unavailable in the noninteractive runtime
  (`could not read Username for 'https://github.com'`). Push remains pending.

## Review Gate

The cycle used the saved read-only Copilot Opus review at
`review-stage/20260621-234130-cycle17-quant-pm-copilot-opus.md`. No new Opus
rerun was performed after these scoped fixes.

## Residual Risk

Route B is still exploratory because the paired return increment is weak, the
overlay is highly correlated with momentum, and the 35-period hold-out is thin.
The benchmark remains a research/paper sleeve until PIT constituents, delisting
returns, and CPCV-style multi-regime stability are available.
