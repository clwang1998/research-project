Cycle 12 is complete.

Implemented and committed locally:

- Tightened [report/sp500_case_study.tex](/root/research_project_aris/report/sp500_case_study.tex) around the PM decision, survivorship caveats, LightGBM framing, and factor-neutral attribution.
- Added horizon-matched PIT inclusion artifacts for 5d and 20d momentum under `report/artifacts/pit_inclusion_sensitivity_5d/` and `_20d/`.
- Updated the paper/PDF to report:
  - 5d momentum Sharpe `0.620 -> 0.461`
  - 20d momentum Sharpe `0.828 -> 0.513`
  - 30d momentum Sharpe `0.741 -> 0.446`
- Saved the cycle scope note at [review-stage/20260621-223052-cycle12-scope.md](/root/research_project_aris/review-stage/20260621-223052-cycle12-scope.md).
- Wrote the requested summary at [cycle_12_codex_summary.md](/root/research_project_supervised_gat/output/aris_paper_pm_20260621-193610/cycle_12_codex_summary.md).

Validation passed:

```bash
python3 -m py_compile scripts/build_pit_inclusion_sensitivity.py scripts/run_alpha_robustness_audit.py
git diff --check
pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex
pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex
```

LaTeX reported the PDF at 10 pages. `pdfinfo` is not installed, so page count was verified from `pdflatex` output.

Local commit:

```text
e595b47 Tighten PM paper claims with PIT haircuts
```

Push was attempted but failed because GitHub HTTPS credentials are unavailable in this non-interactive runtime:

```text
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

Copilot Opus review: used the supplied read-only review file. A post-fix Opus rerun could not be launched because `mcp__manual_review__review` is not exposed in this runtime.