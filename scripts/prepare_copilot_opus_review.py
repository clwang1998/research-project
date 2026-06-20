#!/usr/bin/env python3
"""Prepare a manual Copilot Opus review handoff.

This script builds the reviewer prompt, copies it to the macOS clipboard when
possible, and creates review-stage placeholder files for the Copilot response
and Codex modification scope.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from build_claude_review_prompt import (
    DEFAULT_MAX_DIFF_CHARS,
    DEFAULT_MAX_FILE_CHARS,
    DEFAULT_MAX_UNTRACKED_CHARS,
    build_prompt,
)


DEFAULT_PROMPT_OUTPUT = Path("tmp/copilot_opus_review_prompt.md")
DEFAULT_REVIEW_DIR = Path("review-stage")
REVIEW_RE = re.compile(r"round(?P<round>\d+)-(?:copilot-opus|scope)\.md$")


def next_round(review_dir: Path) -> int:
    max_round = 0
    if not review_dir.exists():
        return 1
    for path in review_dir.glob("*-round*.md"):
        match = REVIEW_RE.search(path.name)
        if match:
            max_round = max(max_round, int(match.group("round")))
    return max_round + 1


def applescript_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def copy_to_clipboard(text: str, source_path: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["pbcopy"],
            input=text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        result = None
    if result is not None and result.returncode == 0:
        return True, "copied with pbcopy"

    pbcopy_stderr = "" if result is None else result.stderr.decode("utf-8", errors="replace").strip()
    pbcopy_error = "pbcopy not found" if result is None else (pbcopy_stderr or "pbcopy failed")
    resolved = applescript_string(str(source_path.resolve()))
    script = f'set the clipboard to (read POSIX file "{resolved}" as «class utf8»)'
    try:
        osa = subprocess.run(
            ["osascript", "-e", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, f"{pbcopy_error}; osascript not found"
    if osa.returncode == 0:
        return True, "copied with osascript"
    osa_error = osa.stderr.strip() or "osascript failed"
    return False, f"{pbcopy_error}; {osa_error}"


def write_if_missing(path: Path, text: str) -> None:
    if path.exists():
        raise SystemExit(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_prompt_args(args: argparse.Namespace) -> SimpleNamespace:
    return SimpleNamespace(
        paths=args.paths,
        output=args.prompt_output,
        max_diff_chars=args.max_diff_chars,
        max_file_chars=args.max_file_chars,
        max_untracked_chars=args.max_untracked_chars,
        reviewer_name=args.reviewer_name,
        author_name=args.author_name,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Optional git pathspecs to limit review context.",
    )
    parser.add_argument(
        "--prompt-output",
        type=Path,
        default=DEFAULT_PROMPT_OUTPUT,
        help=f"Prompt output path. Default: {DEFAULT_PROMPT_OUTPUT}",
    )
    parser.add_argument(
        "--review-dir",
        type=Path,
        default=DEFAULT_REVIEW_DIR,
        help=f"Directory for review records. Default: {DEFAULT_REVIEW_DIR}",
    )
    parser.add_argument(
        "--round",
        type=int,
        default=None,
        help="Positive review round number. Defaults to one greater than existing Copilot Opus rounds.",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="Timestamp prefix for review files, e.g. 20260620-1130. Defaults to local time.",
    )
    parser.add_argument(
        "--max-diff-chars",
        type=int,
        default=DEFAULT_MAX_DIFF_CHARS,
        help="Maximum characters to include from each diff block.",
    )
    parser.add_argument(
        "--max-file-chars",
        type=int,
        default=DEFAULT_MAX_FILE_CHARS,
        help="Maximum characters to include from each untracked text file.",
    )
    parser.add_argument(
        "--max-untracked-chars",
        type=int,
        default=DEFAULT_MAX_UNTRACKED_CHARS,
        help="Aggregate character budget for untracked text file contents.",
    )
    parser.add_argument(
        "--reviewer-name",
        default="GitHub Copilot Opus",
        help="Name of the independent reviewer to place in the generated prompt.",
    )
    parser.add_argument(
        "--author-name",
        default="Codex",
        help="Name of the executor/author whose work is being reviewed.",
    )
    parser.add_argument(
        "--no-clipboard",
        action="store_true",
        help="Do not copy the generated prompt to the clipboard.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    review_round = args.round if args.round is not None else next_round(args.review_dir)
    if review_round < 1:
        raise SystemExit("--round must be a positive integer")
    stamp = args.timestamp or dt.datetime.now().strftime("%Y%m%d-%H%M")
    round_label = f"round{review_round:02d}"

    review_path = args.review_dir / f"{stamp}-{round_label}-copilot-opus.md"
    scope_path = args.review_dir / f"{stamp}-{round_label}-scope.md"
    paths_text = ", ".join(args.paths) if args.paths else "entire working tree"
    if review_path.exists():
        raise SystemExit(f"Refusing to overwrite existing file: {review_path}")
    if scope_path.exists():
        raise SystemExit(f"Refusing to overwrite existing file: {scope_path}")

    prompt = build_prompt(build_prompt_args(args))
    args.prompt_output.parent.mkdir(parents=True, exist_ok=True)
    args.prompt_output.write_text(prompt, encoding="utf-8")

    review_placeholder = f"""# {round_label} Copilot Opus Review

Paste the full VS Code Copilot Chat response below this line.

Reviewer: {args.reviewer_name}
Prompt file: {args.prompt_output}
Scope: {paths_text}
Generated: {dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}

---

"""
    scope_placeholder = f"""# {round_label} Modification Scope

## Review Handoff

- Reviewer: {args.reviewer_name}
- Executor: {args.author_name}
- Prompt file: `{args.prompt_output}`
- Review response file: `{review_path}`
- Scope: `{paths_text}`

## Codex Changes In Response

- Pending. Fill this after applying fixes from the review.

## Validation

- Pending.

## Remaining Risk

- Pending.
"""
    write_if_missing(review_path, review_placeholder)
    write_if_missing(scope_path, scope_placeholder)

    copied = False
    clipboard_message = "skipped"
    if not args.no_clipboard:
        copied, clipboard_message = copy_to_clipboard(prompt, args.prompt_output)

    print(f"Prompt: {args.prompt_output}")
    print(f"Review response file: {review_path}")
    print(f"Scope file: {scope_path}")
    print(f"Clipboard: {clipboard_message}")
    if copied:
        print("Next: paste the clipboard into a fresh VS Code Copilot Chat with Opus selected.")
    else:
        print(f"Next: manually copy {args.prompt_output} into VS Code Copilot Chat with Opus selected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
