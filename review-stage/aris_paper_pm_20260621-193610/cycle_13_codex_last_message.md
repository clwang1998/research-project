Cycle 13 is complete.

Implemented the highest-impact Opus findings:
- Made the 5d sector-neutral momentum book the explicit PM decision row.
- Reframed conviction around traded-horizon IC and turnover, not 1d IC or loose Sharpe.
- Added PIT-filtered Sharpe bootstrap CIs to `scripts/build_pit_inclusion_sensitivity.py`.
- Regenerated 5d/20d/30d PIT artifacts.
- Updated the report/PDF to state the preferred 5d book’s PIT-filtered Sharpe is `0.461`, CI `[-0.49, 1.43]`, so portfolio Sharpe is directional-only.
- Recast Route B as a secondary exploratory residual sleeve.

Validation passed:
- `python3 -m py_compile scripts/build_pit_inclusion_sensitivity.py`
- `git diff --check`
- `pdflatex` three passes
- PDF page count: `10`

Saved:
- Scope note: `review-stage/20260621-224501-cycle13-scope.md`
- Cycle summary: `output/aris_paper_pm_20260621-193610/cycle_13_codex_summary.md`

Committed locally:
- `0525a58 Tighten ARIS paper PM framing`

Push failed because GitHub HTTPS credentials were unavailable in the non-interactive runtime:
`fatal: could not read Username for 'https://github.com': terminal prompts disabled`

Copilot Opus review was used from the supplied cycle review file. A fresh post-fix Opus MCP re-review could not run because `mcp__manual_review__review` is not exposed in this runtime.