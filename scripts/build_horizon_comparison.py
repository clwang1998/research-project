#!/usr/bin/env python3
"""Aggregate walk-forward runs into a horizon/model comparison.

Reads every ``walk_forward_metrics.json`` produced by ``run_walk_forward.py``
under a results directory, builds a tidy comparison table across horizons,
target families, and models, and selects the best model per (horizon, family)
by the across-fold mean validation rank ICIR. Selection never uses hold-out
metrics; hold-out numbers are reported only after selection.

This replaces the previously-referenced but missing ``build_horizon_comparison``
script and uses the overlap-adjusted ICIR so longer horizons are not inflated by
overlapping forward-return windows.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


FAMILY_RE = re.compile(r"^target_(.+)_fwd_(\d+)d$")


def parse_family_horizon(target_col: str) -> tuple[str, int]:
    m = FAMILY_RE.match(str(target_col))
    if not m:
        return ("unknown", -1)
    return (m.group(1), int(m.group(2)))


def load_runs(results_dir: Path) -> pd.DataFrame:
    rows = []
    for meta_path in sorted(results_dir.glob("*/walk_forward_metrics.json")):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"Skipping unreadable {meta_path}")
            continue
        family, horizon = parse_family_horizon(data.get("target_col", ""))
        agg = data.get("fold_aggregate", {}) or {}
        hold = data.get("holdout", {}) or {}
        rows.append(
            {
                "run_name": data.get("run_name", meta_path.parent.name),
                "model": data.get("model"),
                "family": family,
                "horizon": horizon,
                "n_folds": data.get("n_folds"),
                "val_mean_icir": agg.get("mean_rank_ic_ir"),
                "val_median_icir": agg.get("median_rank_ic_ir"),
                "val_mean_ic": agg.get("mean_mean_rank_ic"),
                "val_mean_sharpe": agg.get("mean_sharpe_net"),
                "holdout_ic": hold.get("mean_rank_ic"),
                "holdout_icir": hold.get("rank_ic_ir"),
                "holdout_icir_raw": hold.get("rank_ic_ir_raw"),
                "holdout_sharpe": hold.get("sharpe_net"),
                "holdout_ann_return": hold.get("ann_return_net"),
                "holdout_max_dd": hold.get("max_drawdown_net"),
                "holdout_turnover": hold.get("avg_turnover"),
                "holdout_suspect": hold.get("suspect_overfit_or_leak"),
            }
        )
    return pd.DataFrame(rows)


def select_best(df: pd.DataFrame) -> pd.DataFrame:
    valid = df.dropna(subset=["val_mean_icir"]).copy()
    if valid.empty:
        return valid
    idx = valid.groupby(["family", "horizon"], dropna=False)["val_mean_icir"].idxmax()
    return df.loc[idx].sort_values(["family", "horizon"]).reset_index(drop=True)


def to_markdown(df: pd.DataFrame, cols: list[str], floatfmt: str = "{:.4f}") -> str:
    use = [c for c in cols if c in df.columns]
    header = "| " + " | ".join(use) + " |"
    sep = "| " + " | ".join("---" for _ in use) + " |"
    lines = [header, sep]
    for _, r in df.iterrows():
        cells = []
        for c in use:
            v = r[c]
            if isinstance(v, float):
                cells.append("" if pd.isna(v) else floatfmt.format(v))
            else:
                cells.append("" if v is None else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="output/walk_forward")
    parser.add_argument("--out-csv", default="output/walk_forward/horizon_comparison.csv")
    parser.add_argument("--out-md", default="docs/horizon_comparison.md")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    df = load_runs(results_dir)
    if df.empty:
        print(f"No walk_forward_metrics.json found under {results_dir}")
        return
    df = df.sort_values(["family", "horizon", "model"]).reset_index(drop=True)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv, index=False)

    best = select_best(df)

    all_cols = [
        "family", "horizon", "model", "n_folds",
        "val_mean_icir", "val_mean_sharpe",
        "holdout_ic", "holdout_icir", "holdout_icir_raw",
        "holdout_sharpe", "holdout_ann_return", "holdout_max_dd",
        "holdout_turnover", "holdout_suspect",
    ]
    lines = [
        "# Walk-Forward Horizon / Model Comparison",
        "",
        "Selection rule: best model per (family, horizon) by across-fold mean "
        "validation rank ICIR (overlap-adjusted). Hold-out metrics are reported "
        "only after selection. `holdout_icir_raw` is the naive overlapping value "
        "and is shown only to document the inflation that the adjusted ICIR fixes.",
        "",
        "## Best model per family and horizon",
        "",
        to_markdown(best, all_cols) if not best.empty else "_No runs with validation ICIR._",
        "",
        "## All runs",
        "",
        to_markdown(df, all_cols),
        "",
    ]
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.out_csv} and {args.out_md} ({len(df)} runs, {len(best)} selected).")


if __name__ == "__main__":
    main()
