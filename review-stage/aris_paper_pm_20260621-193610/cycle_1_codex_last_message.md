Cycle 1 is complete.

Implemented the paper-level fixes from the Opus review:
- Corrected the inflated 5d momentum baseline in `report/sp500_case_study.tex`.
- Ran focused 20d/30d momentum baseline checks and used the computed 20d market row.
- Reconciled Route B overlay Sharpe to `0.987`.
- Removed the stale Route B convention-mismatch claim.
- Compressed weak graph/GAT/ensemble evidence into prose instead of promoting it.
- Updated supporting docs that repeated stale `Sharpe ~1.05` / convention language.

Validation:
- `git diff --check` passed.
- `python3 -m py_compile scripts/eval_momentum_baseline.py scripts/run_model_pipeline.py` passed.
- New baseline JSON artifacts validated with `python3 -m json.tool`.
- LaTeX compile could not run because no TeX engine is installed.

Artifacts:
- Cycle summary written to `output/aris_paper_pm_20260621-193610/cycle_1_codex_summary.md`.
- Review/scope notes saved under `review-stage/`.

Commit:
- Local commit: `fb3c86a Fix ARIS report momentum baseline claims`
- Push failed because GitHub HTTPS credentials are unavailable: `could not read Username for 'https://github.com': terminal prompts disabled`.
- Branch is ahead of origin by 1 commit; push remains pending.