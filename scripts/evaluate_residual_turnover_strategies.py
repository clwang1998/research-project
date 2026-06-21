#!/usr/bin/env python3
"""Evaluate momentum-residual overlays and turnover-aware backtests.

This is a post-training evaluator. It reuses saved ``predictions_val_test``
files, so it can test whether ML predictions add orthogonal incremental signal
over a strong momentum baseline without retraining models.
"""

from __future__ import annotations

import argparse
import json
import math
import re
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
    parser.add_argument("--target-cols", nargs="*", default=None)
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--feature-variants", nargs="*", default=None)
    parser.add_argument("--run-name-regex", default=None)
    parser.add_argument("--lambdas", nargs="+", type=float, default=[0.0, 0.25, 0.5, 0.75, 1.0, 1.5])
    parser.add_argument("--ewma-spans", nargs="+", type=int, default=[0, 3, 5])
    parser.add_argument("--no-trade-bands", nargs="+", type=float, default=[0.0, 0.05, 0.10, 0.15])
    parser.add_argument("--selection-metric", default="rank_ic_ir")
    parser.add_argument("--selection-split", default="val", choices=["val", "test"])
    parser.add_argument("--save-best-predictions", action="store_true")
    return parser.parse_args()


def safe_float(value: object) -> float:
    try:
        out = float(value)
    except Exception:
        return math.nan
    return out if math.isfinite(out) else math.nan


def zscore_by_date(frame: pd.DataFrame, col: str) -> pd.Series:
    grouped = frame.groupby("date", observed=True)[col]
    mean = grouped.transform("mean")
    std = grouped.transform("std").replace(0, np.nan)
    out = (frame[col] - mean) / std
    return out.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def residualize_by_date(frame: pd.DataFrame, y_col: str, x_col: str) -> pd.Series:
    x = frame[x_col].to_numpy(dtype=np.float64, copy=False)
    y = frame[y_col].to_numpy(dtype=np.float64, copy=False)
    dates = frame["date"].to_numpy()
    out = np.zeros(len(frame), dtype=np.float32)
    for _, idx in pd.Series(np.arange(len(frame))).groupby(dates, sort=False):
        loc = idx.to_numpy()
        xv = x[loc]
        yv = y[loc]
        denom = float(np.dot(xv, xv))
        if denom <= 1e-12:
            out[loc] = yv.astype(np.float32)
        else:
            beta = float(np.dot(xv, yv) / denom)
            out[loc] = (yv - beta * xv).astype(np.float32)
    return pd.Series(out, index=frame.index)


def ewma_by_symbol(frame: pd.DataFrame, col: str, span: int) -> pd.Series:
    if span <= 1:
        return frame[col]
    ordered = frame[["symbol", "date", col]].copy()
    ordered["_orig_idx"] = np.arange(len(ordered))
    ordered = ordered.sort_values(["symbol", "date"], kind="mergesort")
    smoothed = (
        ordered.groupby("symbol", observed=True)[col]
        .transform(lambda s: s.ewm(span=span, adjust=False).mean())
        .astype("float32")
    )
    ordered["_smoothed"] = smoothed
    return ordered.sort_values("_orig_idx", kind="mergesort")["_smoothed"].reset_index(drop=True)


def choose_weights_with_band(
    g: pd.DataFrame,
    score_col: str,
    pct: float,
    min_names: int,
    sector_neutral: bool,
    prev_w: pd.Series,
    no_trade_band: float,
) -> pd.Series:
    target = rmp.choose_weights(g, score_col, pct, min_names, sector_neutral)
    if target.empty or prev_w.empty or no_trade_band <= 0:
        return target
    all_idx = target.index.union(prev_w.index)
    target = target.reindex(all_idx, fill_value=0.0)
    prev = prev_w.reindex(all_idx, fill_value=0.0)
    turnover = 0.5 * float((target - prev).abs().sum())
    if turnover < no_trade_band:
        return prev.loc[prev != 0.0]
    return target.loc[target != 0.0]


def run_backtest_with_band(
    df: pd.DataFrame,
    score_col: str,
    return_col: str,
    pct: float,
    rebalance_every: int,
    cost_bps: float,
    min_names: int,
    sector_neutral: bool,
    no_trade_band: float,
) -> pd.DataFrame:
    unique_dates = pd.Index(sorted(df["date"].unique()))
    rebalance_dates = unique_dates[::rebalance_every]
    prev_w = pd.Series(dtype=np.float64)
    rows = []
    for dt in rebalance_dates:
        g = df.loc[df["date"] == dt, ["symbol", "sector", score_col, return_col]].dropna()
        if len(g) < min_names:
            continue
        weights = choose_weights_with_band(
            g, score_col, pct, min_names, sector_neutral, prev_w, no_trade_band
        )
        if weights.empty:
            continue
        returns = g.set_index("symbol")[return_col]
        gross_ret = float((weights * returns.reindex(weights.index).fillna(0.0)).sum())
        all_idx = weights.index.union(prev_w.index)
        turnover = 0.5 * float(
            (weights.reindex(all_idx, fill_value=0.0) - prev_w.reindex(all_idx, fill_value=0.0))
            .abs()
            .sum()
        )
        cost = turnover * cost_bps / 10000.0
        rows.append(
            {
                "date": dt,
                "gross_return": gross_ret,
                "turnover": turnover,
                "cost": cost,
                "net_return": gross_ret - cost,
                "n_positions": int((weights != 0).sum()),
                "gross_exposure": float(weights.abs().sum()),
                "net_exposure": float(weights.sum()),
            }
        )
        prev_w = weights
    out = pd.DataFrame(rows)
    if not out.empty:
        out["equity_gross"] = (1.0 + out["gross_return"]).cumprod()
        out["equity_net"] = (1.0 + out["net_return"]).cumprod()
    return out


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


def evaluate(frame: pd.DataFrame, score_col: str, cfg: SimpleNamespace, no_trade_band: float) -> dict[str, object]:
    ic = rmp.spearman_by_date(frame, score_col, rmp.EVAL_TARGET_COL, cfg.min_names_per_date)
    spread = rmp.decile_spread_by_date(
        frame, score_col, rmp.EVAL_TARGET_COL, cfg.long_short_pct, cfg.min_names_per_date
    )
    bt = run_backtest_with_band(
        frame,
        score_col,
        rmp.EVAL_RETURN_COL,
        cfg.long_short_pct,
        cfg.rebalance_every,
        cfg.transaction_cost_bps,
        cfg.min_names_per_date,
        cfg.sector_neutral,
        no_trade_band,
    )
    periods_per_year = 252.0 / cfg.rebalance_every
    return {
        **rmp.summarize_ic(ic, cfg.label_horizon_days),
        **rmp.summarize_spread(spread, periods_per_year),
        **rmp.summarize_backtest(bt, periods_per_year),
        "rows": int(len(frame)),
        "dates": int(frame["date"].nunique()),
    }


def strategy_scores(pred: pd.DataFrame, lam: float, ewma_span: int) -> pd.Series:
    work = pred[["date", "symbol", "baseline_score", "model_score"]].copy()
    work["baseline_z"] = zscore_by_date(work, "baseline_score")
    work["model_z"] = zscore_by_date(work, "model_score")
    work["model_resid_z"] = zscore_by_date(
        work.assign(model_resid=residualize_by_date(work, "model_z", "baseline_z")),
        "model_resid",
    )
    work["combo"] = work["baseline_z"] + float(lam) * work["model_resid_z"]
    work["combo_z"] = zscore_by_date(work, "combo")
    return ewma_by_symbol(work, "combo_z", ewma_span)


def candidate_run_dirs(out_root: Path, experiment_name: str, args: argparse.Namespace) -> list[Path]:
    pattern = re.compile(args.run_name_regex) if args.run_name_regex else None
    dirs = []
    for run_dir in sorted(out_root.glob(f"{experiment_name}__*")):
        config_path = run_dir / "config.json"
        pred_path = run_dir / "predictions_val_test.parquet"
        if not (config_path.exists() and pred_path.exists()):
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if args.target_cols and config.get("target_col") not in set(args.target_cols):
            continue
        model = str(config.get("model_resolved") or config.get("model"))
        if args.models and model not in set(args.models):
            continue
        if args.feature_variants and config.get("feature_variant") not in set(args.feature_variants):
            continue
        if pattern and not pattern.search(run_dir.name):
            continue
        dirs.append(run_dir)
    return dirs


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_dir)
    rows: list[dict[str, object]] = []
    best_predictions: list[pd.DataFrame] = []

    for run_dir in candidate_run_dirs(out_root, args.experiment_name, args):
        config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        cfg = eval_args(config)
        pred = pd.read_parquet(run_dir / "predictions_val_test.parquet")
        pred["date"] = pd.to_datetime(pred["date"])
        pred["_baseline_z"] = zscore_by_date(pred, "baseline_score")
        pred["_model_z"] = zscore_by_date(pred, "model_score")
        pred["_model_resid"] = residualize_by_date(pred, "_model_z", "_baseline_z")
        pred["_model_resid_z"] = zscore_by_date(pred, "_model_resid")
        val_end = pd.Timestamp(config.get("val_end", "2021-12-31"))
        split_masks = {"val": pred["date"] <= val_end, "test": pred["date"] > val_end}
        model = str(config.get("model_resolved") or config.get("model"))
        variant = str(config.get("feature_variant"))
        target = str(config.get("target_col"))
        for lam in args.lambdas:
            combo_col = f"_combo_lam_{lam:g}"
            pred[combo_col] = pred["_baseline_z"] + float(lam) * pred["_model_resid_z"]
            pred[combo_col] = zscore_by_date(pred, combo_col).to_numpy(dtype=np.float32)
            for ewma_span in args.ewma_spans:
                score_col = f"resid_combo_lam{lam:g}_ewma{ewma_span}"
                pred[score_col] = ewma_by_symbol(pred, combo_col, ewma_span).to_numpy(dtype=np.float32)
                for band in args.no_trade_bands:
                    for split, mask in split_masks.items():
                        frame = pred.loc[mask].copy()
                        if frame.empty:
                            continue
                        metrics = evaluate(frame, score_col, cfg, band)
                        rows.append(
                            {
                                "run_name": run_dir.name,
                                "target_col": target,
                                "model": model,
                                "feature_variant": variant,
                                "grid_tag": run_dir.name.split("__")[-1],
                                "lambda": lam,
                                "ewma_span": ewma_span,
                                "no_trade_band": band,
                                "split": split,
                                **metrics,
                            }
                        )
                pred.drop(columns=[score_col], inplace=True)
            pred.drop(columns=[combo_col], inplace=True)

    all_metrics = pd.DataFrame(rows)
    all_path = out_root / f"{args.experiment_name}_residual_turnover_all_metrics.csv"
    best_run_path = out_root / f"{args.experiment_name}_residual_turnover_best_by_run.csv"
    best_target_path = out_root / f"{args.experiment_name}_residual_turnover_best_by_target.csv"
    all_metrics.to_csv(all_path, index=False)
    if all_metrics.empty:
        print(json.dumps({"all_metrics": str(all_path), "rows": 0}, indent=2))
        return

    selected = all_metrics.loc[all_metrics["split"] == args.selection_split].copy()
    selected["_rank_key"] = pd.to_numeric(selected[args.selection_metric], errors="coerce").fillna(-1e9)
    group_cols = ["run_name"]
    idx = selected.groupby(group_cols, dropna=False)["_rank_key"].idxmax()
    best_by_run = selected.loc[idx].drop(columns=["_rank_key"])
    run_keys = set(
        zip(
            best_by_run["run_name"],
            best_by_run["lambda"],
            best_by_run["ewma_span"],
            best_by_run["no_trade_band"],
        )
    )
    best_run_rows = all_metrics.loc[
        [
            key in run_keys
            for key in zip(
                all_metrics["run_name"],
                all_metrics["lambda"],
                all_metrics["ewma_span"],
                all_metrics["no_trade_band"],
            )
        ]
    ].copy()
    best_run_rows.to_csv(best_run_path, index=False)

    val_best = best_run_rows.loc[best_run_rows["split"] == args.selection_split].copy()
    val_best["_rank_key"] = pd.to_numeric(val_best[args.selection_metric], errors="coerce").fillna(-1e9)
    idx = val_best.groupby("target_col", dropna=False)["_rank_key"].idxmax()
    best_targets = val_best.loc[idx].drop(columns=["_rank_key"])
    target_keys = set(
        zip(
            best_targets["run_name"],
            best_targets["lambda"],
            best_targets["ewma_span"],
            best_targets["no_trade_band"],
        )
    )
    best_target_rows = best_run_rows.loc[
        [
            key in target_keys
            for key in zip(
                best_run_rows["run_name"],
                best_run_rows["lambda"],
                best_run_rows["ewma_span"],
                best_run_rows["no_trade_band"],
            )
        ]
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
