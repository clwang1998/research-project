# Ten-Page Technical Report Workflow

This project can produce a ten-page technical report now. The most natural
report is:

> **A Reproducible S&P 500 Forecasting Pipeline: Feature Engineering, Leakage
> Controls, Horizon Alignment, and Model Evaluation**

This should be treated as a technical report first, not a submission-ready paper.
A submission paper needs a tighter claim, finalized figures, and an external
novelty/citation pass.

## Available Source Material

- `docs/feature_catalog.md` — feature groups and construction notes.
- `docs/model_pipeline.md` — model pipeline and experiment flow.
- `docs/data_leakage_review.md` — leakage and horizon-alignment review.
- `docs/report_design_solutions.md` — report design notes.
- `docs/experiment_results_report_*.md` and horizon/ablation reports when
  present — empirical results and comparisons.
- `scripts/make_features.py`, `scripts/run_model_pipeline.py`, and related
  scripts — executable implementation details.

## Recommended Ten-Page Structure

1. **Executive Summary**: problem, dataset, main result, reproducibility status.
2. **Research Question**: target definition, forecasting horizon, evaluation
   constraints, and why leakage risk is high.
3. **Data and Universe Construction**: S&P 500 membership assumptions, price
   data, labels, splits, missing data.
4. **Feature Pipeline**: feature families, normalization, lagging, timestamp
   discipline, and feature catalog.
5. **Model Pipeline**: baselines, MLP/Kronos or other target models, training
   configuration, and inference flow.
6. **Leakage Controls**: future-data exclusion, rolling fit boundaries, horizon
   alignment, survivorship-bias notes.
7. **Experiments**: core runs, horizon comparisons, ablations, and parameter
   search design.
8. **Results**: metrics, tables, stability observations, and failed/negative
   findings.
9. **Limitations**: data access, market regime sensitivity, transaction costs,
   turnover, missing robustness tests.
10. **Reproducibility Checklist**: commands, inputs/outputs, environment, and
    remaining verification gaps.

Target length: 4,500-6,000 words plus tables/figures. In Markdown this is a
ten-page report after export with normal academic spacing; in LaTeX it should be
roughly 8-10 pages depending on figure density.

## ARIS-Style Path

For a narrative technical report:

```text
Codex writes docs/technical_report_10p.md from the source material above.
Copilot Opus reviews it with scripts/prepare_copilot_opus_review.py.
Codex fixes blocking findings and regenerates the report.
```

For an ARIS paper-writing path:

```text
1. Create NARRATIVE_REPORT.md using the ARIS narrative template.
2. Create PAPER_PLAN.md with claims, evidence, figures, and section plan.
3. Run the paper-writing workflow:
   /paper-writing "NARRATIVE_REPORT.md"
4. Compile/inspect the PDF, then run an external reviewer loop.
```

The ARIS upstream workflow explicitly supports `/paper-writing
"NARRATIVE_REPORT.md"` as Workflow 3. In this adapted project, Codex can produce
the narrative/report files, while Copilot Opus remains the independent reviewer.

## Current Readiness

Ready now:

- Markdown ten-page technical report.
- Claims grounded in existing docs and scripts.
- Manual Opus review loop.

Needs another pass before calling it a paper:

- Final experiment table inventory.
- Figure/table generation and visual QA.
- Citation/related-work expansion if targeting an academic venue.
- Explicit statement of novelty beyond an engineering report.
