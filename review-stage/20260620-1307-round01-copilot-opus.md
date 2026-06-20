# round01 Copilot Opus Review

Paste the full VS Code Copilot Chat response below this line.

Reviewer: GitHub Copilot Opus
Prompt file: tmp/copilot_opus_review_prompt.md
Scope: AGENTS.md, docs/copilot_opus_reviewer_mcp.md, docs/claude_reviewer_mcp.md, docs/ten_page_technical_report_workflow.md, scripts/build_claude_review_prompt.py, scripts/build_reviewer_prompt.py, scripts/prepare_copilot_opus_review.py, review-stage/README.md, review-stage/20260620-1128-round00-scope.md, review-stage/20260620-1307-round01-scope.md
Generated: 2026-06-20T05:07:00+00:00

---

## Verdict

One blocking issue (P1) found, plus two reproducibility issues (P2) and three
minor issues (P3). The P1 is confirmed reproducible and is the direct cause of
this review round arriving with garbled Chinese text. Reviewer gathered ground
truth read-only (read files, listed dirs, ran non-destructive probes in /tmp);
no reviewed file was modified.

## Findings (by severity)

### P1 — osascript clipboard fallback corrupts UTF-8 / Chinese (BLOCKER, confirmed)

- File: `scripts/prepare_copilot_opus_review.py`, `copy_to_clipboard()`:
  `script = f'set the clipboard to (read POSIX file "{resolved}")'`.
- Impact: When `pbcopy` is unavailable or fails (the round01 scope itself notes
  "Sandbox pbcopy failed, then macOS clipboard copy succeeded via osascript"),
  the fallback puts mojibake on the clipboard for any non-ASCII content.
  AppleScript `read POSIX file` defaults to MacRoman, not UTF-8, so every
  Chinese-language doc (`docs/copilot_opus_reviewer_mcp.md`,
  `docs/claude_reviewer_mcp.md`, etc.) is delivered to the reviewer as
  unreadable text. This silently defeats the review gate for those files and is
  exactly why this round's prompt arrived corrupted — while the on-disk file
  `tmp/copilot_opus_review_prompt.md` is clean UTF-8.
- Reproduction (verified): running the current osascript on a UTF-8 file with
  Chinese yields `��」���"Codex �ц�锛...宸ャü`; adding the utf8 class yields the
  correct text.
- Fix: read as UTF-8 —
  `script = f'set the clipboard to (read POSIX file "{resolved}" as «class utf8»)'`.
  (The `«class utf8»` guillemets must be literal; verified working.)

### P2 — pbcopy stdin encoding not pinned to UTF-8 (latent crash)

- File: `scripts/prepare_copilot_opus_review.py`, `copy_to_clipboard()`:
  `subprocess.run(["pbcopy"], input=text, text=True, ...)`.
- Impact: With `text=True`, Python encodes stdin using the locale preferred
  encoding. Under a non-UTF-8 locale (e.g. `LANG=C`/`POSIX`), encoding Chinese
  raises `UnicodeEncodeError`, which is NOT caught (only `FileNotFoundError`
  is), crashing the whole helper. The current machine is `C.UTF-8` so it works
  today, but this is fragile.
- Fix: pass bytes explicitly: `input=text.encode("utf-8")` and drop `text=True`
  on that call (decode stderr separately), or pass `encoding="utf-8"`.

### P2 — `.mcp.json` referenced but gitignored/untracked (not reproducible)

- Files: `docs/copilot_opus_reviewer_mcp.md:28` documents a `.mcp.json` block;
  `review-stage/20260620-1128-round00-scope.md:17` lists
  `python -m json.tool .mcp.json` as a validation step; `.gitignore:19` ignores
  `.mcp.json`, and `git ls-files` confirms it is untracked.
- Impact: From a clean clone there is no `.mcp.json`, so the round00 validation
  command fails (`No such file`) and the documented host MCP integration cannot
  be reproduced without the user hand-creating the gitignored file. No committed
  example exists.
- Fix: commit a `.mcp.json.example` with a placeholder/relative path, point the
  doc at the example, and label the `json.tool .mcp.json` step as local-only
  (or drop it from the reproducible-validation list).

### P3 — dangling trailing backslash in documented commands

- Files: `AGENTS.md` (narrower-prompt block) and
  `docs/copilot_opus_reviewer_mcp.md` (narrower-prompt block). Both end with:
  `... scripts/prepare_copilot_opus_review.py \` with nothing after the `\`.
- Impact: Pasting the block leaves the shell at a `>` continuation prompt
  waiting for input; it only "runs" if the user then submits an empty line.
  Confusing copy-paste UX.
- Fix: remove the trailing `\` on the last argument line.

### P3 — silent omission of non-ASCII untracked filenames

- File: `scripts/build_claude_review_prompt.py`, `parse_status_paths()` +
  `read_untracked_files()`.
- Impact: With git's default `core.quotepath=true`, non-ASCII untracked paths
  are C-quoted (e.g. `"docs/\344\270..."`). `repo / rel_path` then fails to
  resolve and the file is silently skipped (`if not path.is_file(): continue`),
  so a review tool whose job is completeness can drop files without warning.
  ASCII-only today, so not triggered, but it is a silent-omission risk.
- Fix: run git with `-c core.quotepath=false` (or `-z` NUL-delimited parsing)
  and emit a warning when a `??` path cannot be resolved.

### P3 — round numbering coupled to reviewer placeholders (fragile)

- File: `scripts/prepare_copilot_opus_review.py`, `next_round()`.
- Impact: Round numbering is derived from existing `*-copilot-opus.md` files.
  Round00 produced only a `-scope.md` (no copilot-opus file), so deleting or
  renaming reviewer files can regress the counter; a later run could then collide
  and `write_if_missing` would abort. Currently consistent.
- Fix: derive the round from both `*-scope.md` and `*-copilot-opus.md`, or pass
  `--round` explicitly in the workflow.

## Non-blocking / residual risk

- Scope of this diff is review tooling + docs only; there is no market-data,
  feature, or model code in scope, so leakage / survivorship / horizon checks
  are N/A for this round. The pipeline scripts referenced by
  `docs/ten_page_technical_report_workflow.md` (`make_features.py`,
  `run_model_pipeline.py`) were not reviewed here.
- Safety posture is good: no secrets, no destructive shell, and
  `write_if_missing()` prevents clobbering prior review rounds.
- The osascript fallback re-reads the file from disk rather than the in-memory
  prompt; harmless once the P1 utf8 fix lands.
- `main()` writes `tmp/...prompt.md` before `write_if_missing()` can abort on an
  existing review/scope file, leaving a stale prompt on early exit. Cosmetic.

## Required before delivery

Fix P1 (one line) and re-run the helper so the regenerated prompt reaches the
reviewer as clean UTF-8. P2 items should be addressed for reproducibility; P3
items are cleanups.
