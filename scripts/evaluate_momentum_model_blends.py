#!/usr/bin/env python3
"""Evaluate validation-selected rank blends of momentum baseline and model scores."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="output/model_search")
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--weights", nargs="+", type=float, default=[0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0])
    parser.add_argument("--selection-metric", default="rank_ic_ir")
    return parser.parse_args()


def safe_float(value: object) -> float:
    try:
        out = float(value)
    except Exception:
        return math.nan
    return out if math.isfinite(out) else math.nan


def args_from_config(config: dict[str, object]) -> SimpleNamespace:
    horizon = int(config.get("label_horizon_days") or 1)
    rebalance = config.get("rebalance_every") or horizon
    return SimpleNamespace(
        long_short_pct=float(config.get("long_short_pct", 0.10)),
        rebalance_every=int(rebalance),
        transaction_cost_bps=float(config.get("transaction_cost_bps", 5.0)),
        min_names_per_date=int(config.get("min_names_per_date", 100)),
        sector_neutral=bool(config.get("sector_neutral", False)),
        label_horizon_days=horizon,
    )


def blended_score(frame: pd.DataFrame, model_weight: float) -> pd.Series:
    base_rank = frame.groupby("date", sort=False)["baseline_score"].rank(pct=True)
    model_rank = frame.groupby("date", sort=False)["model_score"].rank(pct=True)
    return (1.0 - model_weight) * base_rank + model_weight * model_rank


def evaluate(frame: pd.DataFrame, score_col: str, cfg: SimpleNamespace) -> dict[str, object]:
    ic = rmp.spearman_by_date(frame, score_col, rmp.EVAL_TARGET_COL, cfg.min_names_per_date)
    spread = rmp.decile_spread_by_date(
        frame, score_col, rmp.EVAL_TARGET_COL, cfg.long_short_pct, cfg.min_names_per_date
    )
    bt = rmp.run_backtest(
        frame,
        score_col,
        rmp.EVAL_RETURN_COL,
        cfg.long_short_pct,
        cfg.rebalance_every,
        cfg.transaction_cost_bps,
        cfg.min_names_per_date,
        cfg.sector_neutral,
    )
    periods_per_year = 252.0 / cfg.rebalance_every
    return {
        **rmp.summarize_ic(ic, cfg.label_horizon_days),
        **rmp.summarize_spread(spread, periods_per_year),
        **rmp.summarize_backtest(bt, periods_per_year),
        "rows": int(len(frame)),
        "dates": int(frame["date"].nunique()),
    }


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_dir)
    rows: list[dict[str, object]] = []
    for pred_path in sorted(out_root.glob(f"{args.experiment_name}__*/predictions_val_test.parquet")):
        run_dir = pred_path.parent
        config_path = run_dir / "config.json"
        if not config_path.exists():
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        cfg = args_from_config(config)
        pred = pd.read_parquet(pred_path)
        if not {"baseline_score", "model_score", "date"}.issubset(pred.columns):
            continue
        pred["date"] = pd.to_datetime(pred["date"])
        for weight in args.weights:
            score_col = f"blend_w_model_{weight:g}"
            pred[score_col] = blended_score(pred, weight)
            for split in ["val", "test"]:
                mask = pred["date"] <= pd.Timestamp(config.get("val_end", "2021-12-31"))
                split_frame = pred.loc[mask if split == "val" else ~mask].copy()
                if split_frame.empty:
                    continue
                metrics = evaluate(split_frame, score_col, cfg)
                rows.append(
                    {
                        "run_name": run_dir.name,
                        "target_col": config.get("target_col"),
                        "return_col": config.get("return_col"),
                        "model": config.get("model_resolved") or config.get("model"),
                        "feature_variant": config.get("feature_variant"),
                        "grid_tag": config.get("grid_tag"),
                        "model_weight": weight,
                        "split": split,
                        **metrics,
                    }
                )
            pred.drop(columns=[score_col], inplace=True)

    all_metrics = pd.DataFrame(rows)
    all_path = out_root / f"{args.experiment_name}_momentum_blend_all_metrics.csv"
    best_run_path = out_root / f"{args.experiment_name}_momentum_blend_best_by_run.csv"
    best_target_path = out_root / f"{args.experiment_name}_momentum_blend_best_by_target.csv"
    all_metrics.to_csv(all_path, index=False)
    if all_metrics.empty:
        print(f"Wrote empty {all_path}")
        return

    val = all_metrics.loc[all_metrics["split"] == "val"].copy()
    val["_rank_key"] = val[args.selection_metric].map(safe_float).fillna(-1e9)
    best_by_run = val.sort_values("_rank_key", ascending=False).groupby("run_name", as_index=False).head(1)
    best_by_run = best_by_run.drop(columns=["_rank_key"])
    selected_pairs = set(zip(best_by_run["run_name"], best_by_run["model_weight"]))
    selected_rows = all_metrics.loc[
        [(r, w) in selected_pairs for r, w in zip(all_metrics["run_name"], all_metrics["model_weight"])]
    ].copy()
    selected_rows.to_csv(best_run_path, index=False)

    val_selected = selected_rows.loc[selected_rows["split"] == "val"].copy()
    val_selected["_rank_key"] = val_selected[args.selection_metric].map(safe_float).fillna(-1e9)
    best_targets = (
        val_selected.sort_values("_rank_key", ascending=False)
        .groupby("target_col", as_index=False)
        .head(1)
        .drop(columns=["_rank_key"])
    )
    target_pairs = set(zip(best_targets["run_name"], best_targets["model_weight"]))
    best_target_rows = selected_rows.loc[
        [(r, w) in target_pairs for r, w in zip(selected_rows["run_name"], selected_rows["model_weight"])]
    ].copy()
    best_target_rows.to_csv(best_target_path, index=False)
    print(
        json.dumps(
            {
                "all_metrics": str(all_path),
                "best_by_run": str(best_run_path),
                "best_by_target": str(best_target_path),
                "rows": int(len(all_metrics)),
                "runs": int(all_metrics["run_name"].nunique()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
