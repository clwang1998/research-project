Cycle 19 is complete.

Implemented the paper-level fixes in [report/sp500_case_study.tex](/root/research_project_aris/report/sp500_case_study.tex):
- Clarified Route B as a 30-day horizon-specific risk/drawdown sleeve, not evidence that ML improves the endorsed 5-day benchmark.
- Added the DSR threshold wording: same-target DSR 0.814 still fails a 0.95 pass threshold.
- Sharpened capacity caveat: fixed-turnover scaling and rough 10% ADV ceiling near $395M.
- Kept Kronos future-only for PIT universe/survivorship mitigation.
- Added a focused vol-timing negative control from existing Route B paired returns.

Added:
- [scripts/build_route_b_vol_timing_control.py](/root/research_project_aris/scripts/build_route_b_vol_timing_control.py)
- [report/artifacts/route_b_vol_timing_control/](/root/research_project_aris/report/artifacts/route_b_vol_timing_control/)
- [review-stage/20260622-000847-cycle19-scope.md](/root/research_project_aris/review-stage/20260622-000847-cycle19-scope.md)
- Summary written to `/root/research_project_aris/output/aris_paper_pm_20260621-193610/cycle_19_codex_summary.md`

Validation passed:
- `git diff --check`
- `python3 -m py_compile scripts/build_route_b_vol_timing_control.py`
- Two-pass `pdflatex`; PDF remains 10 pages per LaTeX log

Committed locally:
- `6c40294 Tighten Route B paper framing`

Push was attempted but failed because GitHub HTTPS credentials are unavailable in this non-interactive runtime:
`fatal: could not read Username for 'https://github.com': terminal prompts disabled`

Copilot Opus review used: supplied cycle 19 review file. No fresh MCP reviewer rerun was available in this runtime.