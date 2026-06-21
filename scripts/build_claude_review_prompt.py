#!/usr/bin/env python3
"""Build an external reviewer prompt from the current git worktree.

The filename is kept for compatibility with earlier Claude-review setup docs.
Use --reviewer-name to target another reviewer such as GitHub Copilot Opus.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


DEFAULT_OUTPUT = Path("tmp/copilot_opus_review_prompt.md")
DEFAULT_MAX_DIFF_CHARS = 120_000
DEFAULT_MAX_FILE_CHARS = 30_000
DEFAULT_MAX_UNTRACKED_CHARS = 120_000
SKIP_SUFFIXES = {
    ".7z",
    ".bz2",
    ".csv",
    ".gz",
    ".jpeg",
    ".jpg",
    ".parquet",
    ".pdf",
    ".png",
    ".tar",
    ".tgz",
    ".zip",
}


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def git_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit("Not inside a git repository")
    return Path(result.stdout.strip()).resolve()


def truncate(text: str, limit: int, label: str) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}\n\n[truncated {omitted} chars from {label}]\n"


def longest_backtick_run(text: str) -> int:
    longest = current = 0
    for char in text:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def code_block(body: str, lang: str = "text") -> str:
    if not body.strip():
        body = "(empty)"
    fence = "`" * max(3, longest_backtick_run(body) + 1)
    return f"{fence}{lang}\n{body.rstrip()}\n{fence}\n"


def fenced(label: str, body: str, lang: str = "text") -> str:
    return f"## {label}\n\n{code_block(body, lang)}"


def parse_status_paths(status: str) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for line in status.splitlines():
        if not line or line.startswith("## "):
            continue
        code = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        parsed.append((code, path))
    return parsed


def read_text_prefix(path: Path, max_file_chars: int) -> tuple[str, bool]:
    with path.open("r", encoding="utf-8") as handle:
        text = handle.read(max_file_chars + 1)
    if len(text) <= max_file_chars:
        return text, False
    return text[:max_file_chars], True


def read_untracked_files(
    repo: Path,
    status: str,
    max_file_chars: int,
    max_total_chars: int,
) -> str:
    sections: list[str] = []
    total_chars = 0
    for code, rel_path in parse_status_paths(status):
        if code != "??":
            continue
        remaining_chars = max_total_chars - total_chars
        if remaining_chars <= 0:
            sections.append(
                f"[stopped reading untracked files after aggregate cap of {max_total_chars} chars]\n"
            )
            break
        path = repo / rel_path
        if path.is_symlink():
            sections.append(f"### {rel_path}\n\n[skipped symlink]\n")
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            sections.append(f"### {rel_path}\n\n[skipped binary or large-data suffix]\n")
            continue
        try:
            file_char_limit = min(max_file_chars, remaining_chars)
            text, truncated = read_text_prefix(path, file_char_limit)
        except UnicodeDecodeError:
            sections.append(f"### {rel_path}\n\n[skipped non-UTF-8 file]\n")
            continue
        except OSError as exc:
            sections.append(f"### {rel_path}\n\n[skipped unreadable file: {exc}]\n")
            continue
        total_chars += len(text)
        if truncated:
            reason = f"after {file_char_limit} chars from {rel_path}"
            if file_char_limit < max_file_chars:
                reason += f" due to aggregate cap of {max_total_chars} chars"
            text = f"{text}\n\n[truncated {reason}]\n"
        sections.append(
            f"### {rel_path}\n\n{code_block(text, 'text')}"
        )
    return "\n".join(sections)


def build_prompt(args: argparse.Namespace) -> str:
    repo = git_root(Path.cwd())
    pathspecs = args.paths or []
    git_path_args = ["--", *pathspecs] if pathspecs else []

    status = run_git(repo, "status", "--short", "--branch", "--untracked-files=all", *git_path_args)
    diff_stat = run_git(repo, "diff", "--stat", *git_path_args)
    staged_stat = run_git(repo, "diff", "--cached", "--stat", *git_path_args)
    diff = run_git(repo, "diff", "--", *pathspecs) if pathspecs else run_git(repo, "diff")
    staged_diff = (
        run_git(repo, "diff", "--cached", "--", *pathspecs)
        if pathspecs
        else run_git(repo, "diff", "--cached")
    )
    untracked = read_untracked_files(
        repo,
        status,
        args.max_file_chars,
        args.max_untracked_chars,
    )

    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    scope = ", ".join(pathspecs) if pathspecs else "entire working tree"

    parts = [
        f"# {args.reviewer_name} Review Request\n",
        f"You are {args.reviewer_name} acting as the independent reviewer for {args.author_name} work.\n",
        "Review the supplied repository status, diffs, and file contents. Do not edit files, run commands, "
        "or take over as the executor.\n",
        "Review as a senior quantitative researcher / quant PM judging the final paper report, not mainly "
        "as a coding assistant. The most important deliverable is the report's methodology, experiment "
        "design, empirical evidence, and claim discipline.\n",
        "Prioritize whether the paper has a defensible research question, benchmark, alpha narrative, "
        "validation/test separation, transaction-cost and turnover treatment, regime analysis, ablations, "
        "negative controls, survivorship-bias handling, and conclusions that follow from the reported results.\n",
        "Then review implementation support: correctness bugs, regressions, missing tests, reproducibility "
        "issues, data leakage risks, unsafe shell behavior, credential exposure, and documentation commands "
        "that would fail.\n",
        "Return findings first, ordered by severity. For each finding include severity, file/line if possible, "
        "impact on the paper/report claim, and the concrete fix. If there are no blocking paper-level issues, "
        "say that explicitly and list residual risk.\n",
        f"\nRepository: `{repo}`\n",
        f"Scope: `{scope}`\n",
        f"Generated: `{generated_at}`\n\n",
        fenced("Git Status", status),
        fenced("Unstaged Diff Stat", diff_stat),
        fenced("Staged Diff Stat", staged_stat),
        fenced("Unstaged Diff", truncate(diff, args.max_diff_chars, "unstaged diff"), "diff"),
        fenced("Staged Diff", truncate(staged_diff, args.max_diff_chars, "staged diff"), "diff"),
    ]
    if untracked.strip():
        parts.append("## Untracked File Contents\n\n")
        parts.append(untracked.rstrip())
        parts.append("\n")
    return "\n".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="*",
        default=[],
        help="Optional git pathspecs to limit review context.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Prompt output path. Default: {DEFAULT_OUTPUT}",
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompt = build_prompt(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(prompt, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
