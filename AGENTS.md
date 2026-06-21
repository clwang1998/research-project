# Project Agent Instructions

This repository contains a reproducible S&P 500 research workflow. Keep changes
small, reviewable, and oriented around reproducibility.

## Codex Worker + Copilot Opus Reviewer Gate

For non-trivial work, Codex is the default worker/executor. Codex edits files,
runs local validation, and summarizes the modification scope. GitHub Copilot's
Opus model is used only as an independent read-only reviewer. For this project,
the reviewer is primarily a paper/research reviewer, not a coding assistant:
the final deliverable is the research report, so Opus should judge whether the
paper's claims, methodology, experiments, statistical evidence, and PM-level
research narrative are credible.

Do not use Copilot CLI as a second executor in this repository unless the user
explicitly asks for that. Running two coding agents against the same worktree
makes review scope and file ownership harder to audit.

Default gate:

1. Generate review context:
   ```bash
   python scripts/prepare_copilot_opus_review.py
   ```
   This writes `tmp/copilot_opus_review_prompt.md`, copies it to the clipboard
   when possible, and creates review/scope placeholders under `review-stage/`.
2. If `mcp__manual_review__review` is available, call it with the generated
   prompt and
   `config: {"model_reasoning_effort": "xhigh", "preferred_model": "copilot-opus"}`.
   The browser handoff must be read-only: copy the prompt into VS Code Copilot
   Chat with Opus selected, then paste the review response back. The reviewer
   must not edit files.
3. If the MCP tool is not exposed in the current agent runtime, manually paste
   `tmp/copilot_opus_review_prompt.md` into a fresh VS Code Copilot Chat using
   Opus, then save the full response under `review-stage/`.
4. Treat P0/P1 findings, data leakage risks, reproducibility breaks, and shell
   safety issues as blockers. Fix them and run the reviewer again.
5. Save every review round and modification scope under `review-stage/` or the
   task-specific review archive. In the final response, mention whether Copilot
   Opus review ran, the outcome, and any remaining test gaps.

Use a narrower prompt when only a few files changed:

```bash
python scripts/prepare_copilot_opus_review.py \
  --paths AGENTS.md docs/copilot_opus_reviewer_mcp.md docs/ten_page_technical_report_workflow.md scripts/build_claude_review_prompt.py scripts/build_reviewer_prompt.py scripts/prepare_copilot_opus_review.py
```

If the MCP server is unavailable, continue with local verification and
explicitly state that the Copilot Opus reviewer gate could not run. If Copilot
is available but MCP is not, manually paste `tmp/copilot_opus_review_prompt.md`
into a fresh Copilot Opus chat and save the response before continuing.

## Review Focus

Ask Copilot Opus to prioritize:

- Paper-level quant research judgment first: whether the report has a clear
  investment/research question, a defensible benchmark, a believable alpha
  claim, and a conclusion that follows from the evidence.
- Experimental design: walk-forward split integrity, validation-vs-test
  discipline, transaction-cost assumptions, capacity, turnover, regime
  stability, ablations, negative controls, and whether reported improvements are
  economically and statistically meaningful.
- Market-data risks: leakage, survivorship bias, horizon alignment, corporate
  actions, delisting treatment, universe definition, and whether the paper
  overclaims beyond the available dataset.
- Paper presentation: whether tables/figures support the headline, whether weak
  results are framed honestly, whether failed methods are demoted, and whether
  the final report reads like a credible quant PM / senior researcher review
  artifact rather than a code demo.
- Implementation/reproducibility only after the paper claims are assessed:
  correctness and regression risk in Python/shell scripts, deterministic paths,
  clear inputs/outputs, dependency use, documentation commands, credential
  safety, destructive commands, and accidental large-data commits.
