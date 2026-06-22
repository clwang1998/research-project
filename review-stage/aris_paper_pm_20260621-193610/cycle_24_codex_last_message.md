Cycle 24 is complete.

Implemented paper-level fixes in [report/sp500_case_study.tex](/root/research_project_aris/report/sp500_case_study.tex):
- Reframed momentum around cross-regime 1d IC evidence, not the weaker “post-2022 improvement” headline.
- Clarified Route B as a 30d exploratory risk sleeve, not a 5d benchmark improvement claim.
- Tightened DSR, diagnostic-row, capacity, PIT/survivorship, and conclusion language.
- Rebuilt [report/sp500_case_study.pdf](/root/research_project_aris/report/sp500_case_study.pdf).

Saved:
- Scope note: [review-stage/20260622-011500-cycle24-scope.md](/root/research_project_aris/review-stage/20260622-011500-cycle24-scope.md)
- Cycle summary: `/root/research_project_aris/output/aris_paper_pm_20260621-193610/cycle_24_codex_summary.md`

Validation:
- `git diff --check` passed.
- `pdflatex` ran twice successfully; log reports `sp500_case_study.pdf (10 pages, 762113 bytes)`.
- No Python scripts touched, so Python compile was not applicable.

Commit:
- Local commit: `a11cdc8 Refine cycle 24 paper framing`
- Push attempted, but failed: `fatal: could not read Username for 'https://github.com': terminal prompts disabled`

Copilot Opus:
- Read and used the provided cycle 24 Opus review.
- Post-fix Opus rerun could not be performed here because `manual_review` MCP is not exposed in this runtime.