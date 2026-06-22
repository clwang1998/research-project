# Cycle 16 Codex Summary

## Objective

Address the highest-impact safe findings from the cycle 16 Copilot Opus
quant-PM review, prioritizing paper credibility over new model claims.

## Implemented Fixes

- Tightened the abstract/opening decision: the endorsed 5-day sector-neutral
  12--1 momentum book is now framed as a signal/research benchmark, not a
  fundable standalone product.
- Added Table `tab:momentum_ladder`, a compact evidence ladder that puts the
  PM-relevant hierarchy in one place:
  - signal IC evidence is strongest;
  - portfolio Sharpe is directional only;
  - PIT inclusion reduces the 5-day Sharpe from `0.620` to `0.461`;
  - borrow/capacity keep the point estimates upper-bound research statistics;
  - calendar slices show 5-day Sharpe of `-0.95`, `0.33`, `-0.14`, and `0.62`.
- Replaced "untouched hold-out" wording with "single-evaluation hold-out" to
  avoid overstating the hold-out after horizon/framing choices.
- Marked the 30-day LightGBM row as "validation-rejected; unaudited" despite
  its high hold-out Sharpe point estimate.
- Added a concise PM decision paragraph in the conclusion: keep 5-day momentum
  as the live research benchmark/small paper sleeve, require PIT constituents
  and delisting returns before capital allocation, and keep Route B exploratory
  until CPCV-style stability and stronger style-neutral tests pass.
- Regenerated `report/sp500_case_study.pdf`.

## Validation

- `git diff --check`: passed.
- `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex`
  twice from `report/`: passed.
- Output PDF remains 10 pages.
- LaTeX log contains one underfull hbox in the compact evidence-ladder table;
  no overfull boxes or undefined references were observed.

## Computation Notes

No new focused computation was run. The cycle 16 P1 findings were paper
positioning/synthesis issues and the required numbers already existed in the
archived artifacts. CPCV and a true delisting-side survivorship correction
remain follow-up work; no existing CPCV script was present, and adding that
methodology in this cycle would have been broader than the requested safe paper
fix.

## Reviewer Gate

The read-only Copilot Opus review for cycle 16 was already saved at
`review-stage/20260621-233029-cycle16-quant-pm-copilot-opus.md` and reported no
P0 blockers, with two P1 positioning findings. The manual-review MCP tool was
not exposed in this runtime, so a fresh post-fix Opus handoff could not be run
unattended here.
