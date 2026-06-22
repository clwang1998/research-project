Cycle 22 is complete locally.

Implemented:
- Added reproducible IC split-difference diagnostic: `scripts/build_momentum_ic_split_diff.py`
- Added artifact: `report/artifacts/momentum_ic_traded_horizons_5d_split/momentum_5d_ic_split_diff.csv`
- Updated `report/sp500_case_study.tex` and rebuilt `report/sp500_case_study.pdf`
- Saved scope note: `review-stage/20260622-004915-cycle22-scope.md`
- Saved required summary: `output/aris_paper_pm_20260621-193610/cycle_22_codex_summary.md`

Main paper fix: the report now frames 5-day momentum as regime-contingent research-benchmark evidence, not a robust multi-regime tradable alpha. The new diagnostic shows post-2022 5d IC is higher by `0.0168`, but CI `[-0.0045, 0.0380]` crosses zero with `p(diff <= 0) = 0.0616`.

Validation run:
- `python3 scripts/build_momentum_ic_split_diff.py`
- `python3 -m py_compile scripts/build_momentum_ic_split_diff.py`
- `pdflatex` twice, PDF remains 10 pages
- `git diff --check`

Commit created:
- `d3f7e39 ARIS cloud paper iteration cycle 22`

Push failed because GitHub HTTPS credentials were unavailable:
- `fatal: could not read Username for 'https://github.com': terminal prompts disabled`

Copilot Opus review file was read and used. No manual-review MCP tool was exposed, so I could not run a second Opus pass from this runtime.