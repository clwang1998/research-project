# Cycle 14 Codex Summary

- Review source: `review-stage/20260621-225901-cycle14-quant-pm-copilot-opus.md`
- Executor: Codex cloud
- Branch: `codex/supervised-gat-ensemble-search`

## Implemented

- Added `scripts/build_borrow_sensitivity.py` and generated
  `report/artifacts/borrow_sensitivity/`.
- Updated `report/sp500_case_study.tex` and rebuilt the PDF.
- Clarified that reported long--short net returns are net of 5 bps/side trading
  cost but gross of stock-borrow/financing.
- Added short-borrow sensitivity: with 50% short notional, 25/50/100 bps annual
  borrow lowers 5d momentum Sharpe from 0.627 to 0.614/0.600/0.574; 30d Route B
  overlay from 0.987 to 0.972/0.957/0.927.
- Tightened survivorship-bias language: exact impact remains unidentified, but
  absent bankrupt/delisted losers likely make loser-short momentum optimistic.
- Tightened multiple-testing language: 5d momentum is retained as the PM
  benchmark and discovery-to-hold-out survivor, not as a fully deflated
  familywise Sharpe winner.
- Added a table-caption reconciliation for the small PIT-vs-canonical momentum
  Sharpe differences.

## Validation

- `python3 scripts/build_borrow_sensitivity.py`
- `python3 -m py_compile scripts/build_borrow_sensitivity.py`
- `git diff --check`
- `pdflatex -interaction=nonstopmode -halt-on-error sp500_case_study.tex`
  from `report/`; final log reports a 10-page PDF.

## Reviewer Gate

Used the supplied read-only Copilot Opus review for cycle 14. A fresh
`mcp__manual_review__review` tool was not available in this runtime, and tool
discovery did not expose a manual-review equivalent, so no post-fix Opus
re-review was run.

## Commit / Push

- Local commit: `5e09e9f Tighten ARIS paper borrow and survivorship caveats`
- `git push` failed because HTTPS credentials were unavailable in the
  non-interactive runtime. Push remains pending.

## Remaining Gaps

- No stock-specific borrow availability, rebate, or hard-to-borrow history is
  available in the current artifacts.
- The current S&P 500 panel still lacks deleted names and delisting returns, so
  survivorship remains a production-blocking data limitation.
