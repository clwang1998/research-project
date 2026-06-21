#!/usr/bin/env python3
"""Build point-in-time S&P 500 inclusion sensitivity artifacts.

This is a focused paper-audit script. It does not train any model. It compares
the current-membership backtest convention with a filter that only keeps rows
where ``sp500_member_asof == 1``. For Route B, the selected model predictions
are filtered post-training and the already selected residual-overlay score is
rebuilt on the filtered cross-section.
"""

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
import run_alpha_robustness_audit as audit  # noqa: E402
import run_model_pipeline as rmp  # noqa: E402


DEFAULT_SELECTED_RUN = (
    "output/model_search/"
    "route_b_factor_residual_alpha_core_20260622__target_excess_sector_fwd_30d__"
    "tabular__xgboost__xgb_balanced"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", default="data/processed/features_by_group")
    parser.add_argument("--feature-map", default="data/processed/feature_columns_by_group.csv")
    parser.add_argument("--companies-csv", default="data/raw/sp500_companies.csv")
    parser.add_argument("--selected-run-dir", default=DEFAULT_SELECTED_RUN)
    parser.add_argument("--out-dir", default="report/artifacts/pit_inclusion_sensitivity")
    parser.add_argument("--signal-col", default="cs_rank_mom_252d_skip_21d")
    parser.add_argument("--target-col", default="target_excess_sector_fwd_30d")
    parser.add_argument("--return-col", default="target_ret_fwd_30d")
    parser.add_argument("--start-date", default="2008-01-01")
    parser.add_argument("--holdout-start", default="2022-01-01")
    parser.add_argument("--val-end", default="2021-12-31")
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--overlay-lambda", type=float, default=0.2)
    parser.add_argument("--long-short-pct", type=float, default=0.10)
    parser.add_argument("--min-names-per-date", type=int, default=100)
    parser.add_argument("--transaction-cost-bps", type=float, default=5.0)
    parser.add_argument("--sector-neutral", action="store_true", default=True)
    parser.add_argument("--bootstrap-samples", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=20260621)
    return parser.parse_args()


def eval_frame(
    frame: pd.DataFrame,
    score_col: str,
    args: argparse.Namespace,
) -> tuple[dict[str, float], pd.DataFrame]:
    cfg = SimpleNamespace(
        min_names_per_date=args.min_names_per_date,
        long_short_pct=args.long_short_pct,
        rebalance_every=args.horizon_days,
        transaction_cost_bps=args.transaction_cost_bps,
        sector_neutral=args.sector_neutral,
        label_horizon_days=args.horizon_days,
    )
    ic = rmp.spearman_by_date(frame, score_col, rmp.EVAL_TARGET_COL, cfg.min_names_per_date)
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
    periods = 252.0 / cfg.rebalance_every
    metrics = {
        **rmp.summarize_ic(ic, cfg.label_horizon_days),
        **rmp.summarize_backtest(bt, periods),
    }
    return metrics, bt


def load_membership(feature_dir: Path, start_date: str | None) -> pd.DataFrame:
    path = feature_dir / "calendar_metadata.parquet"
    membership = pd.read_parquet(path, columns=rmp.KEY_COLS + ["sp500_member_asof"])
    membership["date"] = pd.to_datetime(membership["date"])
    if start_date:
        membership = membership.loc[membership["date"] >= pd.Timestamp(start_date)]
    return membership


def load_momentum_panel(args: argparse.Namespace) -> pd.DataFrame:
    saved = sys.argv
    try:
        sys.argv = [saved[0]]
        cfg = rmp.parse_args()
    finally:
        sys.argv = saved
    cfg.feature_dir = args.feature_dir
    cfg.feature_map = args.feature_map
    cfg.target_col = args.target_col
    cfg.return_col = args.return_col
    cfg.start_date = args.start_date
    cfg.end_date = None
    cfg.sector_neutral = bool(args.sector_neutral)

    fmap = rmp.read_feature_map(args.feature_map)
    feature_cols = rmp.select_feature_columns(cfg, fmap)
    for col in [args.signal_col, "sp500_member_asof"]:
        if col not in feature_cols:
            feature_cols.append(col)

    panel = rmp.load_panel(cfg, feature_cols, fmap)
    panel = rmp.attach_effective_labels(
        panel,
        args.target_col,
        args.return_col,
        args.horizon_days,
        cfg.execution_lag_days,
    )

    holdout_start = pd.Timestamp(args.holdout_start)
    train_end = str((holdout_start - pd.Timedelta(days=1)).date())
    raw = rmp.split_masks(panel, train_end, train_end)
    embargo_days = rmp.resolve_embargo_days(args.horizon_days, cfg.embargo_days)
    masks = rmp.apply_purge_embargo(panel, raw, train_end, train_end, embargo_days)
    out = panel.loc[masks["test"]].copy()
    out["model_score"] = out[args.signal_col]
    out = out.dropna(subset=["model_score", rmp.EVAL_TARGET_COL, rmp.EVAL_RETURN_COL])
    return out


def eval_momentum(args: argparse.Namespace, require_pit: bool) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    frame = load_momentum_panel(args)
    if require_pit:
        frame = frame.loc[frame["sp500_member_asof"].eq(1)].copy()

    saved = sys.argv
    try:
        sys.argv = [saved[0]]
        cfg = rmp.parse_args()
    finally:
        sys.argv = saved
    frame = rmp.apply_liquidity_universe(frame, "log_dollar_volume", cfg.min_dollar_volume_pct)
    frame = rmp.winsorize_by_date(frame, [args.signal_col], cfg.winsorize_pct)
    frame["model_score"] = frame[args.signal_col]
    metrics, bt = eval_frame(frame, "model_score", args)
    return metrics, bt, frame


def eval_overlay(args: argparse.Namespace, membership: pd.DataFrame, require_pit: bool) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    pred_path = Path(args.selected_run_dir) / "predictions_val_test.parquet"
    pred = pd.read_parquet(pred_path)
    pred["date"] = pd.to_datetime(pred["date"])
    pred = pred.loc[pred["date"] > pd.Timestamp(args.val_end)].copy()
    pred = pred.merge(membership, on=rmp.KEY_COLS, how="left", sort=False)
    if require_pit:
        pred = pred.loc[pred["sp500_member_asof"].eq(1)].copy()
    pred = audit.add_residual_overlay_score(pred, args.overlay_lambda)
    metrics, bt = eval_frame(pred, "residual_overlay_score", args)
    return metrics, bt, pred


def bootstrap_sharpe(
    returns: np.ndarray, periods_per_year: float, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return np.array([])
    idx = rng.integers(0, n, size=(n_boot, n))
    samples = x[idx]
    means = samples.mean(axis=1)
    vols = samples.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sharpes = means / vols * math.sqrt(periods_per_year)
    return sharpes[np.isfinite(sharpes)]


def mean_t_stat(returns: np.ndarray) -> float:
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return math.nan
    se = float(x.std(ddof=1) / math.sqrt(len(x)))
    return float(x.mean() / se) if se > 0 else math.nan


def row(
    label: str,
    variant: str,
    metrics: dict[str, float],
    frame: pd.DataFrame,
    bt: pd.DataFrame,
    args: argparse.Namespace,
    seed_offset: int,
) -> dict[str, object]:
    periods_per_year = 252.0 / args.horizon_days
    returns = bt["net_return"].to_numpy(dtype=float)
    rng = np.random.default_rng(args.seed + seed_offset)
    boot = bootstrap_sharpe(returns, periods_per_year, args.bootstrap_samples, rng)
    return {
        "signal": label,
        "universe": variant,
        "rows": int(len(frame)),
        "dates": int(frame["date"].nunique()),
        "symbols": int(frame["symbol"].nunique()),
        "mean_names_per_date": float(frame.groupby("date", observed=True)["symbol"].nunique().mean()),
        "mean_rank_ic": metrics.get("mean_rank_ic"),
        "rank_ic_ir": metrics.get("rank_ic_ir"),
        "rank_ic_ir_raw": metrics.get("rank_ic_ir_raw"),
        "sharpe_net": metrics.get("sharpe_net"),
        "ann_return_net": metrics.get("ann_return_net"),
        "max_drawdown_net": metrics.get("max_drawdown_net"),
        "avg_turnover": metrics.get("avg_turnover"),
        "n_rebalance_periods": int(len(returns)),
        "mean_return_t_stat": mean_t_stat(returns),
        "bootstrap_samples": int(len(boot)),
        "bootstrap_sharpe_ci_2p5": float(np.quantile(boot, 0.025)) if len(boot) else math.nan,
        "bootstrap_sharpe_ci_97p5": float(np.quantile(boot, 0.975)) if len(boot) else math.nan,
        "bootstrap_prob_sharpe_positive": float(np.mean(boot > 0.0)) if len(boot) else math.nan,
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    membership = load_membership(Path(args.feature_dir), args.start_date)

    current_mom_metrics, current_mom_bt, current_mom = eval_momentum(args, require_pit=False)
    pit_mom_metrics, pit_mom_bt, pit_mom = eval_momentum(args, require_pit=True)
    current_overlay_metrics, current_overlay_bt, current_overlay = eval_overlay(args, membership, require_pit=False)
    pit_overlay_metrics, pit_overlay_bt, pit_overlay = eval_overlay(args, membership, require_pit=True)

    rows = [
        row("momentum", "current_membership", current_mom_metrics, current_mom, current_mom_bt, args, 0),
        row("momentum", "pit_inclusion", pit_mom_metrics, pit_mom, pit_mom_bt, args, 1),
        row(
            "route_b_overlay",
            "current_membership_post_training",
            current_overlay_metrics,
            current_overlay,
            current_overlay_bt,
            args,
            2,
        ),
        row(
            "route_b_overlay",
            "pit_inclusion_post_training",
            pit_overlay_metrics,
            pit_overlay,
            pit_overlay_bt,
            args,
            3,
        ),
    ]
    summary = pd.DataFrame(rows)
    summary.to_csv(out_dir / "pit_inclusion_summary.csv", index=False)
    current_mom_bt.to_csv(out_dir / "momentum_current_membership_backtest.csv", index=False)
    pit_mom_bt.to_csv(out_dir / "momentum_pit_inclusion_backtest.csv", index=False)
    current_overlay_bt.to_csv(out_dir / "overlay_current_membership_backtest.csv", index=False)
    pit_overlay_bt.to_csv(out_dir / "overlay_pit_inclusion_backtest.csv", index=False)

    excluded = current_mom.loc[current_mom["sp500_member_asof"].ne(1)]
    companies_added_2022_plus = None
    companies_path = Path(args.companies_csv)
    if companies_path.exists():
        companies = pd.read_csv(companies_path, usecols=["symbol", "date_added"])
        date_added = pd.to_datetime(companies["date_added"], errors="coerce")
        companies_added_2022_plus = int((date_added >= pd.Timestamp(args.holdout_start)).sum())
    metadata = {
        "selected_run_dir": args.selected_run_dir,
        "target_col": args.target_col,
        "return_col": args.return_col,
        "holdout_start": args.holdout_start,
        "horizon_days": args.horizon_days,
        "overlay_lambda": args.overlay_lambda,
        "bootstrap_samples_requested": args.bootstrap_samples,
        "seed": args.seed,
        "current_members_added_on_or_after_holdout_start": companies_added_2022_plus,
        "excluded_holdout_symbols": int(excluded["symbol"].nunique()),
        "excluded_holdout_rows_after_baseline_controls": int(len(excluded)),
        "note": (
            "PIT inclusion keeps only rows where sp500_member_asof == 1. "
            "Overlay figures are post-training sensitivities: predictions are filtered and the "
            "selected overlay score is rebuilt on the filtered cross-section, but models are not retrained. "
            "Sharpe intervals are deterministic iid bootstraps of non-overlapping net rebalance returns."
        ),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    readme = [
        "# PIT inclusion sensitivity",
        "",
        "This artifact compares current-membership-on-history results with a",
        "point-in-time inclusion filter using `sp500_member_asof == 1` from",
        "`calendar_metadata.parquet`.",
        "",
        "The momentum rows are recomputed from the processed feature panel. The",
        "Route B rows are post-training sensitivities: the selected validation/test",
        "prediction file is filtered to the PIT cross-section, and the already",
        "selected `z(momentum) + 0.2 z(residual model)` overlay score is rebuilt",
        "inside that filtered cross-section. No model is retrained.",
        "",
        "```json",
        json.dumps(metadata, indent=2),
        "```",
    ]
    (out_dir / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(summary.to_string(index=False))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
