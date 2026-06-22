Implemented cycle 4 and committed locally.

Changes made:
- Reframed the paper headline/conclusion around the negative, deflated result.
- Demoted Route B overlay claims with N=35, DSR 0.003, PBO 50%, FM t=0.05.
- Removed winner-style emphasis from unaudited 30d LightGBM rows.
- Added horizon-selection and shared-sample robustness caveats.
- Regenerated frequency/sleeve diagnostics and added tracked CSV snapshots under `report/artifacts/`.
- Wrote the requested summary: `output/aris_paper_pm_20260621-193610/cycle_4_codex_summary.md`.

Validation passed:
- `git diff --check`
- Python compile for relevant scripts
- `pdflatex` twice; PDF remains 9 pages
- LaTeX log scan found no unresolved refs or overfull/underfull warnings

Commit:
- `e53de43 Refine ARIS paper cycle 4 framing`

Push did not complete:
- `git push` failed because HTTPS credentials are unavailable in the non-interactive runtime.
- This is recorded in `review-stage/20260621-202613-cycle4-scope.md`.

Copilot Opus:
- Used the provided cycle-4 Opus review file.
- A fresh post-fix Opus handoff was not run because `manual-review` MCP is not exposed here.