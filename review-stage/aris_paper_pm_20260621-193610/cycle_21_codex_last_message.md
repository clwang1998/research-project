Cycle 21 is complete.

Implemented paper-level fixes from the Copilot Opus review in `report/sp500_case_study.tex` and regenerated `report/sp500_case_study.pdf`. The report now foregrounds 1d discovery/confirmation IC, demotes 5d traded IC to regime-contingent evidence, promotes PIT survivorship sensitivity as the funding blocker, adds a rough four-horizon selection haircut, clarifies Route B IC conventions, and removes visual emphasis from non-result LightGBM diagnostics.

Validation:
- `git diff --check` passed.
- `pdflatex` ran twice successfully.
- Final PDF is 10 pages.
- Python compile was not applicable; no Python scripts were touched.

Audit/summary:
- Scope note saved: `review-stage/20260622-003717-cycle21-scope.md`
- Cycle summary saved: `output/aris_paper_pm_20260621-193610/cycle_21_codex_summary.md`
- Used the provided read-only Copilot Opus review; no second review round was run.

Commit:
- Local commit: `59d60ed Tighten ARIS paper regime and survivorship claims`
- Push attempted, but failed because GitHub HTTPS credentials are unavailable in this runtime. Branch remains ahead of origin.