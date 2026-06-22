# Cycle 20 Codex Summary

Read `AGENTS.md`, `docs/copilot_opus_reviewer_mcp.md`, and
`review-stage/20260622-002147-cycle20-quant-pm-copilot-opus.md`. The highest
impact reviewer findings were the inverted turnover framing, fragile 5d-vs-20d
endorsement language, and the need to label the headline traded IC as
2022--2026 hold-out evidence.

Implemented paper-first fixes:

- Removed "lowest turnover" as a reason to prefer the 5d momentum benchmark.
- Added annualized turnover context: 5d/20d/30d momentum are about
  1115%/449%/337% one-way annualized turnover, despite 5d having the lowest
  per-rebalance turnover.
- Reframed the 5d choice as an IC reliability / signal-existence decision, while
  acknowledging that 20d has higher point Sharpe, higher Rank IC, and lower
  annualized turnover.
- Ran a focused 5d traded-horizon IC split. Discovery-period 2008--2021 traded
  IC is positive but not significant (`t=1.12`, CI `[-0.0045,0.0169]`), while
  the 2022--2026 hold-out remains `t=2.41`, CI `[0.004,0.042]`.
- Updated the abstract-style headline, evidence ladder, discussion, and
  conclusion to disclose that split and avoid overclaiming.
- Added the generated split-IC artifact and README under
  `report/artifacts/momentum_ic_traded_horizons_5d_split/`.

Validation:

- `git diff --check`
- `python3 -m py_compile scripts/build_momentum_ic_robustness.py`
- Two-pass `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex`
  from `report/`
- Final PDF compiles to 10 pages.

Copilot Opus review status: used the supplied cycle-20 Copilot Opus review as
the read-only senior quant PM gate. No new Opus re-review was run after these
fixes because this unattended runtime does not expose the manual-review MCP
tool.

Commit/push:

- Local commit: `e6db721 Tighten momentum turnover framing`
- Push attempted to `origin/codex/supervised-gat-ensemble-search`, but HTTPS
  credentials were unavailable in the non-interactive runtime. Push is pending.
