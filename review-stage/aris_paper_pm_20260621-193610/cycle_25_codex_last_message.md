Cycle 25 is complete.

Implemented the high-impact paper fixes:
- Ran the missing 5d Route B overlay audit and updated the report to lead with the negative/indeterminate horizon-matched result.
- Demoted the old 30d Route B overlay to sensitivity evidence.
- Added canonical 5d Route B IC artifacts and an IC-decay figure.
- Rebuilt `report/sp500_case_study.pdf`; it remains 10 pages.
- Wrote the required summary at `output/aris_paper_pm_20260621-193610/cycle_25_codex_summary.md`.
- Saved scope notes under `review-stage/20260622-013231-cycle25-scope.md`.

Validation run:
- 5d overlay audit
- 5d canonical IC recomputation
- IC-decay figure generation
- Python compile for touched scripts
- `pdflatex` twice
- `git diff --check`

Committed locally:
- `a84ce71 Cycle 25 tighten Route B paper claims`

Push was attempted but failed because GitHub HTTPS credentials are unavailable in this non-interactive runtime:
`fatal: could not read Username for 'https://github.com': terminal prompts disabled`

Copilot Opus: I used the supplied cycle 25 Opus review file. A new Opus re-review was not run because the manual-review MCP tool is not exposed here.