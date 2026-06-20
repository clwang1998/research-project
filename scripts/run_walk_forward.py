#!/usr/bin/env python3
"""Expanding walk-forward evaluation for the cross-sectional S&P 500 model.

This orchestrates the single-split building blocks in ``run_model_pipeline`` over
an expanding, yearly-rolling set of folds, then reports a final untouched
hold-out period. For each fold the model is fit only on past data, the
preprocessor statistics are fit only on that fold's training rows, and labels
that cross the fold boundary are purged with a horizon embargo. Model selection
is meant to use the across-fold mean validation rank ICIR; the hold-out is
reported once and never used for selection.

Why walk-forward instead of one static split: factor efficacy is regime
dependent, so a single validation window can be a lucky or unlucky regime.
Evaluating across many expanding folds gives a more reliable estimate of whether
the signal has stable predictive power across time.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument("--feature-map", default="data/processed/feature_columns_by_group.csv")
    parser.add_argument("--out-dir", default="output/walk_forward")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--target-col", default="target_excess_sector_fwd_5d")
    parser.add_argument("--return-col", default="target_ret_fwd_5d")
    parser.add_argument("--feature-set", choices=["core", "all"], default="core")
    parser.add_argument("--feature-groups", nargs="*", default=None)
    parser.add_argument("--include-graph-embeddings", action="store_true")
    parser.add_argument(
        "--graph-embedding-path",
        default="data/processed/graph_embeddings/gat_embeddings_daily.parquet",
    )
    # Walk-forward schedule.
    parser.add_argument("--start-date", default="2005-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--first-train-end", default="2012-12-31")
    parser.add_argument("--holdout-start", default="2023-01-01")
    parser.add_argument("--val-years", type=int, default=1)
    parser.add_argument("--step-years", type=int, default=1)
    # Model + hyperparameters (mirrors run_model_pipeline so rmp.fit_model works).
    parser.add_argument(
        "--model",
        choices=["ridge", "sklearn-hgb", "xgboost", "lightgbm", "mlp", "auto"],
        default="ridge",
    )
    parser.add_argument("--ridge-alpha", type=float, default=25.0)
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--num-leaves", type=int, default=63)
    parser.add_argument("--min-child-samples", type=int, default=100)
    parser.add_argument("--min-child-weight", type=float, default=20.0)
    parser.add_argument("--subsample", type=float, default=0.8)
    parser.add_argument("--colsample-bytree", type=float, default=0.8)
    parser.add_argument("--reg-alpha", type=float, default=0.0)
    parser.add_argument("--reg-lambda", type=float, default=5.0)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--sample-seed", type=int, default=42)
    # MLP-specific (used by rmp.fit_model when --model mlp).
    parser.add_argument("--mlp-hidden", default="128,64")
    parser.add_argument("--mlp-dropout", type=float, default=0.1)
    parser.add_argument("--mlp-weight-decay", type=float, default=1e-4)
    parser.add_argument("--mlp-lr", type=float, default=1e-3)
    parser.add_argument("--mlp-epochs", type=int, default=30)
    parser.add_argument("--mlp-batch-size", type=int, default=8192)
    parser.add_argument("--mlp-patience", type=int, default=5)
    # Evaluation / universe controls.
    parser.add_argument("--execution-lag-days", type=int, default=1)
    parser.add_argument("--embargo-days", type=int, default=None)
    parser.add_argument("--rebalance-every", type=int, default=None)
    parser.add_argument("--long-short-pct", type=float, default=0.10)
    parser.add_argument("--min-names-per-date", type=int, default=100)
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0)
    parser.add_argument("--winsorize-pct", type=float, default=0.01)
    parser.add_argument("--min-dollar-volume-pct", type=float, default=0.10)
    parser.add_argument("--sector-neutral", action="store_true")
    parser.add_argument("--max-train-rows", type=int, default=None)
    parser.add_argument("--max-eval-rows", type=int, default=None)
    return parser.parse_args()


def build_fit_args(args: argparse.Namespace) -> argparse.Namespace:
    """Build model-fitting args from run_model_pipeline's own defaults.

    Starting from the pipeline defaults keeps the walk-forward compatible with any
    pipeline-only model arguments (for example LightGBM/XGBoost device flags) that
    ``rmp.fit_model`` may read, then we override only the hyperparameters this
    orchestrator controls.
    """
    saved = sys.argv
    try:
        sys.argv = [saved[0] if saved else "run_walk_forward"]
        fit_args = rmp.parse_args()
    finally:
        sys.argv = saved
    for key in [
        "model", "ridge_alpha", "n_estimators", "learning_rate", "max_depth",
        "num_leaves", "min_child_samples", "min_child_weight", "subsample",
        "colsample_bytree", "reg_alpha", "reg_lambda", "n_jobs", "sample_seed",
        "mlp_hidden", "mlp_dropout", "mlp_weight_decay", "mlp_lr", "mlp_epochs",
        "mlp_batch_size", "mlp_patience",
    ]:
        if hasattr(args, key):
            setattr(fit_args, key, getattr(args, key))
    return fit_args


def build_folds(
    first_train_end: str,
    holdout_start: str,
    val_years: int,
    step_years: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Yearly-rolling expanding folds; each val block ends on/before the hold-out."""
    folds: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    holdout = pd.Timestamp(holdout_start)
    t_end = pd.Timestamp(first_train_end)
    while True:
        val_end = t_end + pd.DateOffset(years=val_years)
        if val_end > holdout:
            break
        folds.append((t_end, val_end))
        t_end = t_end + pd.DateOffset(years=step_years)
    return folds


def evaluate_model_on_mask(
    panel: pd.DataFrame,
    mask: np.ndarray,
    model,
    prep: rmp.Preprocessor,
    feature_cols: list[str],
    horizon_days: int,
    rebalance_every: int,
    args: argparse.Namespace,
) -> dict[str, float]:
    """Predict on ``mask`` rows and return overlap-adjusted IC + backtest metrics."""
    if not mask.any():
        return {}
    sub = panel.loc[mask].copy()
    sub["model_score"] = model.predict(prep.transform(sub))
    ic = rmp.spearman_by_date(sub, "model_score", rmp.EVAL_TARGET_COL, args.min_names_per_date)
    bt = rmp.run_backtest(
        sub,
        "model_score",
        rmp.EVAL_RETURN_COL,
        args.long_short_pct,
        rebalance_every,
        args.transaction_cost_bps,
        args.min_names_per_date,
        args.sector_neutral,
    )
    periods_per_year = 252.0 / rebalance_every
    metrics = {
        **rmp.summarize_ic(ic, horizon_days),
        **rmp.summarize_backtest(bt, periods_per_year),
    }
    metrics["rows"] = int(len(sub))
    metrics["dates"] = int(sub["date"].nunique())
    sharpe = metrics.get("sharpe_net", float("nan"))
    icir = metrics.get("rank_ic_ir", float("nan"))
    metrics["suspect_overfit_or_leak"] = bool(
        (isinstance(sharpe, float) and np.isfinite(sharpe) and sharpe > 3.0)
        or (isinstance(icir, float) and np.isfinite(icir) and icir > 5.0)
    )
    return metrics


def fit_eval_fold(
    panel: pd.DataFrame,
    feature_cols: list[str],
    train_end: pd.Timestamp,
    val_end: pd.Timestamp,
    horizon_days: int,
    embargo_days: int,
    rebalance_every: int,
    args: argparse.Namespace,
    fit_args: argparse.Namespace,
) -> dict[str, float] | None:
    """Fit the preprocessor + model on the expanding train block, evaluate on val."""
    raw = rmp.split_masks(panel, str(train_end.date()), str(val_end.date()))
    masks = rmp.apply_purge_embargo(panel, raw, str(train_end.date()), str(val_end.date()), embargo_days)
    if not masks["train"].any() or not masks["val"].any():
        return None
    train_fit_mask = rmp.sample_mask(panel, masks["train"], args.max_train_rows, args.sample_seed)
    prep = rmp.fit_preprocessor(panel, feature_cols, train_fit_mask)
    x_train = prep.transform(panel.loc[train_fit_mask])
    y_train = panel.loc[train_fit_mask, rmp.EVAL_TARGET_COL].to_numpy(dtype=np.float32)
    _, model = rmp.fit_model(fit_args, x_train, y_train)
    del x_train, y_train
    eval_mask = rmp.limit_eval_mask_by_date(panel, masks["val"], args.max_eval_rows)
    metrics = evaluate_model_on_mask(
        panel, eval_mask, model, prep, feature_cols, horizon_days, rebalance_every, args
    )
    metrics["train_rows"] = int(train_fit_mask.sum())
    metrics["train_end"] = str(train_end.date())
    metrics["val_end"] = str(val_end.date())
    return metrics


def aggregate(rows: list[dict[str, float]], keys: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    if not rows:
        return out
    df = pd.DataFrame(rows)
    for key in keys:
        if key in df.columns:
            vals = pd.to_numeric(df[key], errors="coerce").dropna()
            if not vals.empty:
                out[f"mean_{key}"] = float(vals.mean())
                out[f"median_{key}"] = float(vals.median())
                out[f"std_{key}"] = float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
    return out


def main() -> None:
    args = parse_args()
    run_name = args.run_name or time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    fmap = rmp.read_feature_map(args.feature_map)
    feature_cols = rmp.select_feature_columns(args, fmap)
    if args.include_graph_embeddings:
        feature_cols = list(dict.fromkeys(feature_cols + rmp.GRAPH_FEATURES))

    panel = rmp.load_panel(args, feature_cols, fmap)
    horizon_days = rmp.infer_horizon_days(args.target_col, args.return_col)
    embargo_days = rmp.resolve_embargo_days(horizon_days, args.embargo_days)
    rebalance_every = args.rebalance_every if args.rebalance_every is not None else horizon_days
    args.label_horizon_days = horizon_days

    panel = rmp.attach_effective_labels(
        panel, args.target_col, args.return_col, horizon_days, args.execution_lag_days
    )
    panel = rmp.apply_liquidity_universe(panel, "log_dollar_volume", args.min_dollar_volume_pct)
    panel = rmp.winsorize_by_date(panel, feature_cols, args.winsorize_pct)

    folds = build_folds(args.first_train_end, args.holdout_start, args.val_years, args.step_years)
    fit_args = build_fit_args(args)
    print(
        json.dumps(
            {
                "model": args.model,
                "target_col": args.target_col,
                "horizon_days": horizon_days,
                "embargo_days": embargo_days,
                "rebalance_every": rebalance_every,
                "n_folds": len(folds),
                "holdout_start": args.holdout_start,
                "rows": int(len(panel)),
            },
            indent=2,
        )
    )

    fold_rows: list[dict[str, float]] = []
    for i, (train_end, val_end) in enumerate(folds):
        metrics = fit_eval_fold(
            panel, feature_cols, train_end, val_end, horizon_days, embargo_days, rebalance_every, args, fit_args
        )
        if metrics is None:
            print(f"Fold {i}: skipped (empty train/val).")
            continue
        metrics["fold"] = i
        fold_rows.append(metrics)
        print(
            f"Fold {i} val {metrics['val_end']}: "
            f"IC={metrics.get('mean_rank_ic', float('nan')):.4f} "
            f"ICIR={metrics.get('rank_ic_ir', float('nan')):.2f} "
            f"Sharpe={metrics.get('sharpe_net', float('nan')):.2f}"
        )

    # Final untouched hold-out: train through the day before hold-out start.
    holdout_start = pd.Timestamp(args.holdout_start)
    holdout_train_end = holdout_start - pd.Timedelta(days=1)
    raw = rmp.split_masks(panel, str(holdout_train_end.date()), str(holdout_train_end.date()))
    masks = rmp.apply_purge_embargo(
        panel, raw, str(holdout_train_end.date()), str(holdout_train_end.date()), embargo_days
    )
    holdout_metrics: dict[str, float] = {}
    if masks["train"].any() and masks["test"].any():
        train_fit_mask = rmp.sample_mask(panel, masks["train"], args.max_train_rows, args.sample_seed)
        prep = rmp.fit_preprocessor(panel, feature_cols, train_fit_mask)
        x_train = prep.transform(panel.loc[train_fit_mask])
        y_train = panel.loc[train_fit_mask, rmp.EVAL_TARGET_COL].to_numpy(dtype=np.float32)
        _, model = rmp.fit_model(fit_args, x_train, y_train)
        del x_train, y_train
        eval_mask = rmp.limit_eval_mask_by_date(panel, masks["test"], args.max_eval_rows)
        holdout_metrics = evaluate_model_on_mask(
            panel, eval_mask, model, prep, feature_cols, horizon_days, rebalance_every, args
        )
        holdout_metrics["train_rows"] = int(train_fit_mask.sum())
        print(
            f"Hold-out >= {args.holdout_start}: "
            f"IC={holdout_metrics.get('mean_rank_ic', float('nan')):.4f} "
            f"ICIR={holdout_metrics.get('rank_ic_ir', float('nan')):.2f} "
            f"Sharpe={holdout_metrics.get('sharpe_net', float('nan')):.2f}"
        )

    agg = aggregate(fold_rows, ["mean_rank_ic", "rank_ic_ir", "sharpe_net", "ann_return_net", "avg_turnover"])

    if fold_rows:
        pd.DataFrame(fold_rows).to_csv(out_dir / "fold_metrics.csv", index=False)
    summary = {
        "run_name": run_name,
        "model": args.model,
        "target_col": args.target_col,
        "return_col": args.return_col,
        "horizon_days": horizon_days,
        "execution_lag_days": args.execution_lag_days,
        "embargo_days": embargo_days,
        "rebalance_every": rebalance_every,
        "winsorize_pct": args.winsorize_pct,
        "min_dollar_volume_pct": args.min_dollar_volume_pct,
        "n_folds": len(fold_rows),
        "fold_aggregate": agg,
        "holdout": holdout_metrics,
        "folds": fold_rows,
    }
    (out_dir / "walk_forward_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    config = vars(args).copy()
    config["run_name"] = run_name
    (out_dir / "config.json").write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    print(f"Done. Walk-forward results written to {out_dir}")
    print(json.dumps({"fold_aggregate": agg, "holdout": holdout_metrics}, indent=2))


if __name__ == "__main__":
    main()
