#!/usr/bin/env python3
"""Robust inference for the hold-out daily momentum Rank IC.

This is a focused paper-audit diagnostic for the pre-registered 12-1 momentum
factor at its discovered 1-day confirmation horizon. It reuses the same
execution lag, liquidity filter, winsorization, and rank-IC convention as
``build_signal_horizon_ic_surface.py``, then reports HAC and moving-block
bootstrap inference for the daily IC series.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-dir", default="data/processed/features_by_group")
    p.add_argument("--signal-col", default="mom_252d_skip_21d")
    p.add_argument("--target-col", default="target_excess_sector_fwd_1d")
    p.add_argument("--return-col", default="target_ret_fwd_1d")
    p.add_argument("--start-date", default="2008-01-01")
    p.add_argument("--holdout-start", default="2022-01-01")
    p.add_argument("--execution-lag-days", type=int, default=1)
    p.add_argument("--liquidity-drop-pct", type=float, default=0.10)
    p.add_argument("--winsorize-pct", type=float, default=0.01)
    p.add_argument("--min-names", type=int, default=100)
    p.add_argument("--nw-lags", nargs="*", type=int, default=[5, 21, 63])
    p.add_argument("--block-length", type=int, default=21)
    p.add_argument("--bootstrap-samples", type=int, default=10000)
    p.add_argument("--seed", type=int, default=20260621)
    p.add_argument("--out-dir", default="report/artifacts/momentum_ic_robustness")
    return p.parse_args()


def load_panel(args: argparse.Namespace) -> pd.DataFrame:
    feature_dir = Path(args.feature_dir)
    targets = pd.read_parquet(
        feature_dir / "targets.parquet",
        columns=rmp.KEY_COLS + ["sector", args.target_col, args.return_col],
    )
    targets["date"] = pd.to_datetime(targets["date"])
    targets = targets.loc[targets["date"] >= pd.Timestamp(args.start_date)]
    signals = pd.read_parquet(
        feature_dir / "price_momentum.parquet",
        columns=rmp.KEY_COLS + [args.signal_col, "dollar_volume"],
    )
    signals["date"] = pd.to_datetime(signals["date"])
    panel = targets.merge(signals, on=rmp.KEY_COLS, how="inner")
    horizon_days = rmp.infer_horizon_days(args.target_col, args.return_col)
    panel = rmp.attach_effective_labels(
        panel,
        args.target_col,
        args.return_col,
        horizon_days=horizon_days,
        execution_lag_days=args.execution_lag_days,
    )
    panel = rmp.apply_liquidity_universe(
        panel, "dollar_volume", args.liquidity_drop_pct
    )
    return rmp.winsorize_by_date(panel, [args.signal_col], args.winsorize_pct)


def daily_rank_ic(
    panel: pd.DataFrame, signal_col: str, min_names: int
) -> pd.DataFrame:
    rows = []
    for dt, g in panel.groupby("date", sort=True, observed=True):
        mask = g[signal_col].notna() & g[rmp.EVAL_TARGET_COL].notna()
        if int(mask.sum()) < min_names:
            continue
        ic = rmp.safe_corrcoef(
            g.loc[mask, signal_col].rank(), g.loc[mask, rmp.EVAL_TARGET_COL].rank()
        )
        rows.append({"date": dt, "rank_ic": ic, "n": int(mask.sum())})
    return pd.DataFrame(rows).dropna(subset=["rank_ic"])


def newey_west_t(values: np.ndarray, lag: int) -> tuple[float, float]:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 3:
        return math.nan, math.nan
    demeaned = x - x.mean()
    max_lag = min(lag, n - 1)
    gamma0 = float(np.dot(demeaned, demeaned) / n)
    long_run_var = gamma0
    for k in range(1, max_lag + 1):
        gamma = float(np.dot(demeaned[k:], demeaned[:-k]) / n)
        weight = 1.0 - k / (max_lag + 1.0)
        long_run_var += 2.0 * weight * gamma
    long_run_var = max(long_run_var, 0.0)
    se_mean = math.sqrt(long_run_var / n) if long_run_var > 0 else math.nan
    t_stat = float(x.mean() / se_mean) if se_mean and se_mean > 0 else math.nan
    return t_stat, se_mean


def circular_block_bootstrap_means(
    values: np.ndarray, block_length: int, n_boot: int, seed: int
) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n == 0:
        return np.array([])
    block_length = max(1, min(block_length, n))
    n_blocks = int(math.ceil(n / block_length))
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    offsets = np.arange(block_length)
    means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = (starts[i, :, None] + offsets[None, :]).reshape(-1)[:n] % n
        means[i] = float(x[idx].mean())
    return means


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    panel = load_panel(args)
    panel["split"] = np.where(
        panel["date"] >= pd.Timestamp(args.holdout_start), "test", "discovery"
    )

    daily_rows = []
    summary_rows = []
    horizon_days = rmp.infer_horizon_days(args.target_col, args.return_col)
    for split in ("discovery", "test"):
        ic = daily_rank_ic(
            panel.loc[panel["split"] == split], args.signal_col, args.min_names
        )
        ic["split"] = split
        daily_rows.append(ic)
        values = ic["rank_ic"].to_numpy(dtype=float)
        base = rmp.summarize_ic(
            ic[["date", "rank_ic"]], horizon_days=horizon_days
        )
        boot = circular_block_bootstrap_means(
            values, args.block_length, args.bootstrap_samples, args.seed
        )
        row: dict[str, object] = {
            "split": split,
            "signal": args.signal_col,
            "target_col": args.target_col,
            "n_dates": int(len(values)),
            "mean_rank_ic": base["mean_rank_ic"],
            "rank_ic_ir": base["rank_ic_ir"],
            "plain_t": float(
                np.mean(values) / (np.std(values, ddof=1) / math.sqrt(len(values)))
            ),
            "block_length": args.block_length,
            "bootstrap_samples": args.bootstrap_samples,
            "block_boot_mean_ci_low": float(np.quantile(boot, 0.025)),
            "block_boot_mean_ci_high": float(np.quantile(boot, 0.975)),
            "block_boot_mean_se": float(np.std(boot, ddof=1)),
            "block_boot_t": float(np.mean(values) / np.std(boot, ddof=1)),
            "block_boot_p_mean_le_zero": float(np.mean(boot <= 0.0)),
        }
        for lag in args.nw_lags:
            t_stat, se_mean = newey_west_t(values, lag)
            row[f"newey_west_lag{lag}_t"] = t_stat
            row[f"newey_west_lag{lag}_se_mean"] = se_mean
        summary_rows.append(row)

    daily = pd.concat(daily_rows, ignore_index=True)
    summary = pd.DataFrame(summary_rows)
    daily_path = out_dir / "momentum_daily_rank_ic.csv"
    summary_path = out_dir / "momentum_daily_ic_robustness.csv"
    daily.to_csv(daily_path, index=False)
    summary.to_csv(summary_path, index=False)
    print(summary.to_string(index=False))
    print(f"\nWrote:\n  {daily_path}\n  {summary_path}")


if __name__ == "__main__":
    main()
