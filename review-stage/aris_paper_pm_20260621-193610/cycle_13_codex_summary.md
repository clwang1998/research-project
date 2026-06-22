# Cycle 13 Codex Summary

Implemented the highest-impact paper fixes from
`review-stage/20260621-224501-cycle13-quant-pm-copilot-opus.md`.

## What changed

- Made the 5-day sector-neutral momentum book the explicit PM decision row in
  the abstract/headline, results-table caption, survivorship discussion, and
  conclusion.
- Reframed conviction around traded-horizon IC and turnover rather than the
  non-traded 1-day IC statistic or an imprecise portfolio Sharpe.
- Extended `scripts/build_pit_inclusion_sensitivity.py` to add deterministic
  bootstrap Sharpe intervals for current-membership and PIT-filtered books.
- Regenerated 5d/20d/30d PIT inclusion artifacts and added the new uncertainty
  columns to their summary CSVs.
- Updated the report to state that the preferred 5d book's PIT-filtered Sharpe
  is 0.461 with CI `[-0.49, 1.43]`, so portfolio Sharpe is directional-only
  after the partial survivorship haircut.
- Recast Route B as a secondary residual sleeve; it remains exploratory despite
  improved 30d drawdown.

## Key computed results

- 5d momentum PIT-filtered Sharpe: 0.461, bootstrap CI `[-0.49, 1.43]`
- 20d momentum PIT-filtered Sharpe: 0.513, bootstrap CI `[-0.45, 1.58]`
- 30d momentum PIT-filtered Sharpe: 0.446, bootstrap CI `[-0.52, 1.50]`

## Validation

- `python3 -m py_compile scripts/build_pit_inclusion_sensitivity.py`
- `git diff --check`
- `pdflatex` from `report/`, three passes
- PDF page count: 10

Only residual LaTeX issue is one underfull hbox warning in the long results
table caption. Copilot Opus review was supplied for this cycle and used as the
input gate; no fresh MCP Opus re-review was available in this runtime.
