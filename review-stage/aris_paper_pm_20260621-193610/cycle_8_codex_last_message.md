Cycle 8 is complete.

Implemented the highest-impact review fixes:
- Added focused 5/10/20/30d momentum IC robustness evidence and archived it under `report/artifacts/momentum_ic_traded_horizons/`.
- Tightened the report’s 1d IC vs 30d traded-horizon framing.
- Corrected the stale `volume_z_20d` table values.
- Reframed survivorship haircut as an adverse sensitivity with unproven sign, not a correction.
- Clarified PBO precision limits and removed misleading 30d bolding.
- Updated supporting docs and audit-script generated wording.

Validation passed:
- `git diff --check`
- Python compile for touched/relevant scripts
- `pdflatex` twice; final report remains 10 pages, no material LaTeX warnings.

Wrote the requested summary:
`/root/research_project_aris/output/aris_paper_pm_20260621-193610/cycle_8_codex_summary.md`

Committed locally:
`9f04400 Tighten ARIS paper horizon and survivorship framing`

Push was attempted but failed due missing noninteractive GitHub HTTPS credentials:
`fatal: could not read Username for 'https://github.com': terminal prompts disabled`

Copilot Opus follow-up review could not run because `mcp__manual_review__review` is not exposed in this runtime and no VS Code Copilot handoff is available. The prompt/placeholders were generated and recorded under `review-stage/`.