Cycle 10 is complete.

Updated the paper/report to address the saved Copilot Opus PM review:
- Reframed the headline around 5-day sector-neutral 12-1 momentum as the cleanest tradable benchmark.
- Foregrounded survivorship sensitivity: PIT inclusion cuts 30-day momentum Sharpe `0.741 -> 0.446`.
- Clarified 1-day IC vs traded-horizon evidence.
- Recast Route B as a residual-sleeve diagnostic, not independent production alpha.
- Standardized `tab:results` to sector-relative 5d/20d/30d rows.

Validation passed:
- `git diff --check`
- `python3 -m py_compile ...`
- `pdflatex` twice
- PDF remains 10 pages

Saved:
- Scope note: `review-stage/20260621-215914-cycle10-scope.md`
- Summary: `output/aris_paper_pm_20260621-193610/cycle_10_codex_summary.md`

Committed locally:
- `3d3c6c2 Improve ARIS paper benchmark framing`

Push was attempted but failed because GitHub credentials are unavailable in the non-interactive runtime: `could not read Username for 'https://github.com': terminal prompts disabled`. The branch is now ahead of origin with the local commit.