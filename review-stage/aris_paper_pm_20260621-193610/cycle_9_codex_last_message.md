Cycle 9 is complete.

Implemented the main Copilot Opus P1 fix: added a PIT inclusion sensitivity using `sp500_member_asof == 1`, archived under `report/artifacts/pit_inclusion_sensitivity/`, and updated the paper/PDF to make the survivorship caveat quantitative and more conservative.

Key PIT result:
- 30d momentum Sharpe: `0.741 -> 0.446`
- Route B overlay Sharpe: `0.987 -> 0.725`
- This is now framed as a material point-estimate hit, not a correction for missing delisted names.

Validation run:
- Python compile passed for touched/relevant scripts.
- PIT builder reran successfully.
- LaTeX compiled twice; PDF remains 10 pages.
- `git diff --check` passed.
- `pdfinfo`/`pdftotext` are not installed, so PDF text smoke checks could not run.

Artifacts/notes:
- Scope note: `review-stage/20260621-214109-cycle9-scope.md`
- Requested cycle summary: `/root/research_project_aris/output/aris_paper_pm_20260621-193610/cycle_9_codex_summary.md`

Commit:
- Local commit created: `6f030bb Add PIT inclusion sensitivity to ARIS paper cycle 9`
- Push attempted, but failed because GitHub HTTPS credentials are unavailable in the noninteractive terminal. Push is pending.

Copilot Opus:
- The provided cycle 9 Opus review was read first and used as the paper-first reviewer input.
- Post-fix Opus rerun could not run because `mcp__manual_review__review` is not exposed here and there is no unattended interactive Copilot handoff.