Cycle 18 is complete.

Implemented the highest-impact paper fixes in `report/sp500_case_study.tex` and rebuilt `report/sp500_case_study.pdf`:
- tightened benchmark framing around traded-horizon IC, not recent Sharpe
- changed survivorship language to net-sign indeterminate
- clarified same-target DSR vs conservative 884-trial DSR
- flagged high-AUM capacity as extrapolated beyond calibration
- marked the attractive LightGBM row as “not a result”
- compressed the conclusion while keeping the PDF at 10 pages

Validation:
- `git diff --check` passed
- `pdflatex` ran twice successfully
- rebuilt PDF is 10 pages
- no Python scripts were touched, so no Python compile was needed
- one non-blocking underfull hbox remains in a compact table row

Artifacts:
- Scope note: `review-stage/20260621-235445-cycle18-scope.md`
- Requested summary: `output/aris_paper_pm_20260621-193610/cycle_18_codex_summary.md`

Committed locally:
- `dfdc9e2 Refine ARIS paper cycle 18 framing`

Push attempted but failed because HTTPS GitHub credentials are unavailable in this runtime:
`fatal: could not read Username for 'https://github.com': terminal prompts disabled`

Branch is now ahead of origin by 35 commits.