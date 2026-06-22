Implemented cycle 2 fixes and committed locally.

Changed the final report to:
- Reframe Route B as exploratory risk-timing/residual sleeve evidence, not confirmed alpha.
- Cut the compiled PDF from 12 pages to 9 pages.
- Add `N=35`, bootstrap CI, full-grid DSR, and PBO next to the 30d Route B result.
- Add the 30d LightGBM comparison to avoid horizon-selective benchmark framing.
- Correct the rank-IC traceability language and lead factor-neutral interpretation with the weak FM `t=0.05`.
- Compress older weak diagnostics/negative controls into prose.

Validation passed:
- `pdflatex` twice, PDF verified at 9 pages.
- LaTeX log: no undefined refs, zero overfull hboxes.
- `git diff --check`
- `python3 -m py_compile scripts/prepare_copilot_opus_review.py scripts/eval_momentum_baseline.py scripts/run_alpha_robustness_audit.py`

Cycle notes written:
- `review-stage/20260621-195616-cycle2-scope.md`
- `/root/research_project_aris/output/aris_paper_pm_20260621-193610/cycle_2_codex_summary.md`

Local commit created: `8f226fb Tighten ARIS report claim discipline`.

Push was attempted but failed because GitHub credentials are unavailable in the unattended shell: `could not read Username for 'https://github.com': terminal prompts disabled`. Push remains pending. The supplied Copilot Opus review was used; a fresh post-fix Opus MCP review could not run because `mcp__manual_review__review` is not exposed here.