#!/usr/bin/env python3
"""Aggregate walk-forward runs into a horizon/model comparison.

Reads every ``walk_forward_metrics.json`` produced by ``run_walk_forward.py``
under a results directory, builds a tidy comparison table across feature
variants, horizons, target families, and models, and selects the best model by
the across-fold mean validation rank ICIR. Selection never uses hold-out metrics;
hold-out numbers are reported only after selection.

This replaces the previously-referenced but missing ``build_horizon_comparison``
script and uses the overlap-adjusted ICIR so longer horizons are not inflated by
overlapping forward-return windows.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import run_model_pipeline as rmp
except Exception:  # pragma: no cover - comparison should still read old results.
    rmp = None


FAMILY_RE = re.compile(r"^target_(.+)_fwd_(\d+)d$")


def parse_family_horizon(target_col: str) -> tuple[str, int]:
    m = FAMILY_RE.match(str(target_col))
    if not m:
        return ("unknown", -1)
    return (m.group(1), int(m.group(2)))


def read_run_config(meta_path: Path) -> dict[str, object]:
    config_path = meta_path.parent / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"Skipping unreadable config {config_path}")
        return {}


def resolve_feature_variant(
    metrics: dict[str, object], config: dict[str, object]
) -> tuple[str, bool]:
    include_graph = bool(
        metrics.get("include_graph_embeddings", config.get("include_graph_embeddings", False))
    )
    variant = metrics.get("feature_variant") or config.get("feature_variant")
    if not variant:
        variant = "graph" if include_graph else "tabular"
    return str(variant), include_graph


def resolve_feature_counts(
    meta_path: Path,
    metrics: dict[str, object],
    config: dict[str, object],
    include_graph: bool,
) -> tuple[int | None, int]:
    graph_count = metrics.get("graph_feature_count", config.get("graph_feature_count"))
    if graph_count is None:
        graph_count = len(rmp.GRAPH_FEATURES) if include_graph and rmp is not None else 0
    graph_count = int(graph_count)

    feature_count = metrics.get("feature_count", config.get("feature_count"))
    if feature_count is not None:
        return int(feature_count), graph_count

    selected_path = meta_path.parent / "selected_features.csv"
    if selected_path.exists():
        selected = pd.read_csv(selected_path)
        return int(len(selected)), graph_count

    if (
        rmp is not None
        and config.get("feature_set", "core") == "core"
        and not config.get("feature_groups")
    ):
        return int(len(rmp.CORE_FEATURES) + graph_count), graph_count
    return None, graph_count


def load_runs(results_dir: Path) -> pd.DataFrame:
    rows = []
    for meta_path in sorted(results_dir.glob("*/walk_forward_metrics.json")):
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"Skipping unreadable {meta_path}")
            continue
        config = read_run_config(meta_path)
        feature_variant, include_graph = resolve_feature_variant(data, config)
        feature_count, graph_count = resolve_feature_counts(
            meta_path, data, config, include_graph
        )
        family, horizon = parse_family_horizon(data.get("target_col", ""))
        agg = data.get("fold_aggregate", {}) or {}
        hold = data.get("holdout", {}) or {}
        rows.append(
            {
                "run_name": data.get("run_name", meta_path.parent.name),
                "model": data.get("model"),
                "feature_variant": feature_variant,
                "include_graph_embeddings": include_graph,
                "feature_count": feature_count,
                "graph_feature_count": graph_count,
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


def select_best(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    valid = df.dropna(subset=["val_mean_icir"]).copy()
    if valid.empty:
        return valid
    idx = valid.groupby(group_cols, dropna=False)["val_mean_icir"].idxmax()
    return df.loc[idx].sort_values(group_cols).reset_index(drop=True)


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
    df = df.sort_values(["feature_variant", "family", "horizon", "model"]).reset_index(drop=True)
    Path(args.out_csv).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv, index=False)

    best_by_variant = select_best(df, ["feature_variant", "family", "horizon"])
    best_overall = select_best(df, ["family", "horizon"])

    all_cols = [
        "feature_variant", "family", "horizon", "model", "n_folds",
        "feature_count", "graph_feature_count",
        "val_mean_icir", "val_mean_sharpe",
        "holdout_ic", "holdout_icir", "holdout_icir_raw",
        "holdout_sharpe", "holdout_ann_return", "holdout_max_dd",
        "holdout_turnover", "holdout_suspect",
    ]
    lines = [
        "# Walk-Forward Horizon / Model Comparison",
        "",
        "Selection rule: best model by across-fold mean validation rank ICIR "
        "(overlap-adjusted). Graph runs include the sector graph, style kNN graph, "
        "rolling-correlation graph, and deterministic graph relation embedding features. "
        "Hold-out metrics are reported only after selection. `holdout_icir_raw` is "
        "the naive overlapping value and is shown only to document the inflation "
        "that the adjusted ICIR fixes.",
        "",
        "## Best model per feature variant, family, and horizon",
        "",
        to_markdown(best_by_variant, all_cols)
        if not best_by_variant.empty
        else "_No runs with validation ICIR._",
        "",
        "## Best model overall per family and horizon",
        "",
        to_markdown(best_overall, all_cols)
        if not best_overall.empty
        else "_No runs with validation ICIR._",
        "",
        "## All runs",
        "",
        to_markdown(df, all_cols),
        "",
    ]
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.out_csv} and {args.out_md} "
        f"({len(df)} runs, {len(best_by_variant)} variant selections, "
        f"{len(best_overall)} overall selections)."
    )


if __name__ == "__main__":
    main()
