# Cycle 1 Codex Summary

## Implemented Fixes

- Fixed the paper's P0 momentum-table integrity issue. The 5d sector momentum
  row now reports the canonical artifact values (`Sharpe=0.627`, annual return
  `5.92%`, turnover `0.221`) instead of the unsourced legacy `1.05 / 13.5% /
  0.16` figures.
- Ran focused baseline computations for 20d market, 20d sector, and 30d sector
  with `scripts/eval_momentum_baseline.py`, writing the resulting JSON artifacts
  under `output/momentum_baseline_priority/`.
- Replaced the unsourced 20d momentum row with the computed 20d market baseline
  (`RankIC=0.0418`, `ICIR=0.653`, `Sharpe=0.822`, annual return `7.83%`,
  turnover `0.356`).
- Reconciled Route B 30d overlay metrics to the robustness-audit artifact:
  validation-selected overlay Sharpe is `0.987`, annual return `8.27%`, max
  drawdown `-7.32%`, and turnover `0.494`.
- Removed stale claims that the Route B standalone momentum baseline had a
  portfolio-convention mismatch. The focused 30d rerun reproduces the Route B
  momentum row exactly.
- Compressed weak graph/GAT/ensemble evidence into prose and kept it framed as
  negative/diagnostic evidence, not empirical alpha.
- Updated supporting docs that repeated the stale `Sharpe ~1.05` and Route B
  convention narratives.

## Validation

- `python3 scripts/eval_momentum_baseline.py` completed for:
  - `target_excess_market_fwd_20d`
  - `target_excess_sector_fwd_20d`
  - `target_excess_sector_fwd_30d`
- `git diff --check` passed.
- `python3 -m py_compile scripts/eval_momentum_baseline.py scripts/run_model_pipeline.py` passed.
- `python3 -m json.tool` passed for the three new baseline JSON artifacts.
- LaTeX compile did not run because no TeX engine is installed in this runtime.

## Reviewer Gate

- Initial read-only Copilot Opus review was read from
  `review-stage/20260621-193616-cycle1-quant-pm-copilot-opus.md`.
- A fresh narrow follow-up prompt was generated at
  `tmp/copilot_opus_review_prompt.md`, with placeholders under
  `review-stage/20260621-1952-round33-*`.
- The follow-up Copilot Opus review could not run unattended because
  `mcp__manual_review__review` is not exposed here and there is no
  browser/clipboard handoff on the cloud server.

## Commit / Push

- Local commit created: `fb3c86a` (`Fix ARIS report momentum baseline claims`).
- Push attempted to `origin/codex/supervised-gat-ensemble-search` but failed:
  `fatal: could not read Username for 'https://github.com': terminal prompts disabled`.
- Push remains pending until credentials are available.

## Remaining Risks

- Page count could not be reverified without LaTeX, although several non-core
  tables were removed from the report.
- Route B remains exploratory: full-grid DSR is `0.003`, CSCV PBO is `50%`, and
  independent style-neutral attribution is weak.
- Survivorship bias is still bounded by sensitivity haircuts rather than
  corrected with point-in-time constituents and delisting returns.
