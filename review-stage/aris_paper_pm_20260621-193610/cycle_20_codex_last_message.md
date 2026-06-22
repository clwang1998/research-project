Cycle 20 is complete.

Implemented and committed locally as `e6db721 Tighten momentum turnover framing`.

Key changes:
- Fixed the paper’s 5d turnover framing: no longer claims 5d has “lowest turnover” as an endorsement.
- Added annualized turnover context: 5d/20d/30d momentum are about `1115% / 449% / 337%` one-way annualized.
- Ran the focused 5d traded-horizon IC split:
  - 2008-2021 discovery: `t=1.12`, CI `[-0.0045, 0.0169]`
  - 2022-2026 hold-out: `t=2.41`, CI `[0.004, 0.042]`
- Updated [report/sp500_case_study.tex](/root/research_project_aris/report/sp500_case_study.tex) and regenerated the 10-page PDF.
- Added audit artifacts under `report/artifacts/momentum_ic_traded_horizons_5d_split/`.
- Filled the cycle scope note and wrote the requested summary at:
  [cycle_20_codex_summary.md](/root/research_project_aris/output/aris_paper_pm_20260621-193610/cycle_20_codex_summary.md)

Validation passed:
- `git diff --check`
- `python3 -m py_compile scripts/build_momentum_ic_robustness.py`
- two-pass `pdflatex`, final PDF is 10 pages

Copilot Opus: used the supplied cycle-20 read-only review. I did not run a fresh Opus re-review because the manual-review MCP tool is not exposed in this runtime.

Push was attempted but failed because GitHub HTTPS credentials are unavailable in the non-interactive environment: `could not read Username`. Local commit is ready; push is pending.