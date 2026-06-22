Cycle 15 is complete.

Implemented the highest-impact paper fixes from the saved Copilot Opus review:

- Added a regime diagnostic for no-fit sector-neutral momentum: `scripts/build_momentum_regime_diagnostics.py`.
- Archived results in `report/artifacts/momentum_regime_diagnostics/`.
- Updated `report/sp500_case_study.tex` and rebuilt `report/sp500_case_study.pdf`.
- Reframed the headline so 5d momentum is a detectable signal with directional portfolio economics, not a statistically tight tradable Sharpe.
- Added explicit pre-2022 regime weakness and clarified that Route B lacks pre-2022 overlay predictions.
- Kept the PDF at 10 pages.
- Wrote the requested summary: `output/aris_paper_pm_20260621-193610/cycle_15_codex_summary.md`.

Validation passed:

- `git diff --check`
- `python3 -m py_compile scripts/build_momentum_regime_diagnostics.py`
- `pdflatex` twice, final PDF: 10 pages

Local commit created:

- `54c9534 Tighten ARIS paper regime and Sharpe framing`

Push was attempted but failed because GitHub HTTPS credentials are unavailable in this unattended runtime:

```text
fatal: could not read Username for 'https://github.com': terminal prompts disabled
```

Copilot Opus review used: `review-stage/20260621-231414-cycle15-quant-pm-copilot-opus.md`. No additional reviewer rerun was available from this runtime.