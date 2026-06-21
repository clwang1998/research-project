#!/usr/bin/env python3
"""Evaluate same-family tree seed-bagging rank ensembles."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="output/model_search")
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--selection-metric", default="rank_ic_ir")
    parser.add_argument("--min-val-rank-ic", type=float, default=0.0)
    parser.add_argument("--top-k", type=int, default=0, help="0 keeps all members passing filters.")
    parser.add_argument("--models", nargs="+", default=["lightgbm", "xgboost"])
    parser.add_argument("--save-predictions", action="store_true")
    return parser.parse_args()


def safe_float(value: object) -> float:
    try:
        out = float(value)
    except Exception:
        return math.nan
    return out if math.isfinite(out) else math.nan


def eval_args(config: dict[str, object]) -> SimpleNamespace:
    horizon = rmp.infer_horizon_days(str(config["target_col"]), str(config["return_col"]))
    rebalance_every = int(config.get("rebalance_every") or horizon)
    return SimpleNamespace(
        rebalance_every=rebalance_every,
        long_short_pct=float(config.get("long_short_pct", 0.10)),
        transaction_cost_bps=float(config.get("transaction_cost_bps", 5.0)),
        min_names_per_date=int(config.get("min_names_per_date", 100)),
        sector_neutral=bool(config.get("sector_neutral", False)),
        label_horizon_days=horizon,
    )


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


def load_candidate_rows(out_root: Path, experiment_name: str, args: argparse.Namespace) -> pd.DataFrame:
    rows = []
    for run_dir in sorted(out_root.glob(f"{experiment_name}__*")):
        metrics_path = run_dir / "metrics.json"
        config_path = run_dir / "config.json"
        pred_path = run_dir / "predictions_val_test.parquet"
        if not (metrics_path.exists() and config_path.exists() and pred_path.exists()):
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        model = str(config.get("model_resolved") or config.get("model"))
        if model not in set(args.models):
            continue
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        val = metrics.get("model_score", {}).get("val", {})
        val_rank_ic = safe_float(val.get("mean_rank_ic"))
        val_metric = safe_float(val.get(args.selection_metric))
        if not math.isfinite(val_rank_ic) or val_rank_ic < args.min_val_rank_ic:
            continue
        rows.append(
            {
                "run_name": run_dir.name,
                "run_dir": str(run_dir),
                "pred_path": str(pred_path),
                "target_col": config.get("target_col"),
                "return_col": config.get("return_col"),
                "model": model,
                "feature_variant": config.get("feature_variant"),
                "grid_tag": run_dir.name.split("__")[-1],
                "val_mean_rank_ic": val_rank_ic,
                "val_metric": val_metric,
            }
        )
    return pd.DataFrame(rows)


def evaluate_group(group: pd.DataFrame, out_root: Path, experiment_name: str, args: argparse.Namespace) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    group = group.sort_values("val_metric", ascending=False)
    if args.top_k > 0:
        group = group.head(args.top_k)
    if len(group) < 2:
        return [], []

    merged = None
    score_cols = []
    members = []
    for i, row in enumerate(group.itertuples(index=False), start=1):
        pred = pd.read_parquet(row.pred_path)
        score_col = f"score_{i}"
        keep_cols = [
            "date",
            "symbol",
            "sector",
            rmp.EVAL_TARGET_COL,
            rmp.EVAL_RETURN_COL,
            "model_score",
        ]
        pred = pred.loc[:, [c for c in keep_cols if c in pred.columns]].rename(columns={"model_score": score_col})
        if merged is None:
            merged = pred
        else:
            pred = pred.drop(columns=[c for c in ["sector", rmp.EVAL_TARGET_COL, rmp.EVAL_RETURN_COL] if c in pred.columns])
            merged = merged.merge(pred, on=["date", "symbol"], how="inner")
        score_cols.append(score_col)
        members.append(row._asdict())

    assert merged is not None
    for col in score_cols:
        merged[f"rank__{col}"] = merged.groupby("date", observed=True)[col].rank(pct=True, method="average")
    rank_cols = [f"rank__{col}" for col in score_cols]
    merged["seed_bag_rank_equal"] = merged[rank_cols].mean(axis=1)
    val_weights = np.asarray([max(0.0, safe_float(m["val_metric"])) for m in members], dtype=np.float64)
    if np.isfinite(val_weights).all() and val_weights.sum() > 0:
        val_weights = val_weights / val_weights.sum()
        merged["seed_bag_rank_weighted"] = merged[rank_cols].to_numpy() @ val_weights
    else:
        merged["seed_bag_rank_weighted"] = merged["seed_bag_rank_equal"]

    first_config = json.loads((Path(members[0]["run_dir"]) / "config.json").read_text(encoding="utf-8"))
    cfg = eval_args(first_config)
    dates = pd.to_datetime(merged["date"])
    val_end = pd.Timestamp(first_config.get("val_end", "2021-12-31"))
    split_masks = {"val": dates <= val_end, "test": dates > val_end}
    out_rows = []
    member_rows = []
    target_col = str(group.iloc[0]["target_col"])
    feature_variant = str(group.iloc[0]["feature_variant"])
    target_dir = out_root / f"{experiment_name}_seed_bagging" / target_col / feature_variant
    target_dir.mkdir(parents=True, exist_ok=True)
    if args.save_predictions:
        merged.to_parquet(target_dir / "seed_bagging_predictions.parquet", index=False)
    (target_dir / "seed_bagging_members.json").write_text(
        json.dumps(members, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    for member in members:
        member_rows.append(
            {
                "target_col": target_col,
                "feature_variant": feature_variant,
                "run_name": member["run_name"],
                "model": member["model"],
                "grid_tag": member["grid_tag"],
                "val_metric": member["val_metric"],
                "val_mean_rank_ic": member["val_mean_rank_ic"],
            }
        )
    for score_col in ["seed_bag_rank_equal", "seed_bag_rank_weighted"]:
        for split, mask in split_masks.items():
            frame = merged.loc[mask].copy()
            if frame.empty:
                continue
            out_rows.append(
                {
                    "target_col": target_col,
                    "feature_variant": feature_variant,
                    "score": score_col,
                    "split": split,
                    "n_members": int(len(members)),
                    **evaluate(frame, score_col, cfg),
                }
            )
    return out_rows, member_rows


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_dir)
    candidates = load_candidate_rows(out_root, args.experiment_name, args)
    rows: list[dict[str, object]] = []
    member_rows: list[dict[str, object]] = []
    if not candidates.empty:
        for _, group in candidates.groupby(["target_col", "feature_variant"], dropna=False):
            out, members = evaluate_group(group, out_root, args.experiment_name, args)
            rows.extend(out)
            member_rows.extend(members)
    metrics = pd.DataFrame(rows)
    members = pd.DataFrame(member_rows)
    metrics_path = out_root / f"{args.experiment_name}_seed_bagging_metrics.csv"
    members_path = out_root / f"{args.experiment_name}_seed_bagging_members.csv"
    metrics.to_csv(metrics_path, index=False)
    members.to_csv(members_path, index=False)
    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "members": str(members_path),
                "candidate_rows": int(len(candidates)),
                "ensemble_rows": int(len(metrics)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
