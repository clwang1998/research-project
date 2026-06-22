#!/usr/bin/env python3
"""Build a naive volatility-timing control for Route B paired returns.

The control uses only the archived non-overlapping 30-day momentum return stream.
It scales the next rebalance return by inverse trailing realized volatility of
that same stream, shifted by one period to avoid using the current return. This
does not reproduce implementable single-name execution, but it is a lightweight
negative control for the paper question: can a trivial risk-scaling rule explain
the Route B Sharpe lift?
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--paired-returns",
        default="report/artifacts/route_b_paired_increment/paired_returns.csv",
    )
    p.add_argument("--lookback-periods", type=int, default=6)
    p.add_argument("--min-periods", type=int, default=3)
    p.add_argument("--annualization", type=float, default=8.4)
    p.add_argument("--target-period-vol", type=float, default=None)
    p.add_argument("--max-leverage", type=float, default=1.5)
    p.add_argument("--out-dir", default="report/artifacts/route_b_vol_timing_control")
    return p.parse_args()


def perf(x: pd.Series, periods_per_year: float) -> dict[str, float]:
    r = x.dropna().astype(float)
    ann_return = float(r.mean() * periods_per_year)
    ann_vol = float(r.std(ddof=1) * math.sqrt(periods_per_year))
    sharpe = ann_return / ann_vol if ann_vol > 0 else math.nan
    equity = (1.0 + r).cumprod()
    max_dd = float((equity / equity.cummax() - 1.0).min())
    return {
        "n_periods": int(r.size),
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
    }


def paired_t(diff: pd.Series) -> float:
    d = diff.dropna().astype(float)
    if d.size < 3:
        return math.nan
    se = float(d.std(ddof=1) / math.sqrt(d.size))
    return float(d.mean() / se) if se > 0 else math.nan


def main() -> None:
    args = parse_args()
    paired = pd.read_csv(args.paired_returns, parse_dates=["date"]).sort_values("date")
    mom = paired["momentum_net_return"].astype(float)
    target_vol = (
        float(args.target_period_vol)
        if args.target_period_vol is not None
        else float(mom.std(ddof=1))
    )
    trailing_vol = mom.rolling(args.lookback_periods, min_periods=args.min_periods).std(ddof=1)
    scale = (target_vol / trailing_vol.shift(1)).clip(upper=args.max_leverage)
    vol_timed = mom * scale

    out = paired.copy()
    out["trailing_momentum_vol_shifted"] = trailing_vol.shift(1)
    out["vol_timing_scale"] = scale
    out["vol_timed_momentum_net_return"] = vol_timed
    out["vol_timed_minus_momentum"] = out["vol_timed_momentum_net_return"] - out["momentum_net_return"]
    out["overlay_minus_vol_timed"] = out["overlay_net_return"] - out["vol_timed_momentum_net_return"]

    rows = []
    for label, col in [
        ("momentum", "momentum_net_return"),
        ("route_b_overlay", "overlay_net_return"),
        ("vol_timed_momentum", "vol_timed_momentum_net_return"),
    ]:
        row = {"sample": "available", "series": label, **perf(out[col], args.annualization)}
        rows.append(row)

    valid = out.dropna(
        subset=["momentum_net_return", "overlay_net_return", "vol_timed_momentum_net_return"]
    ).copy()
    for label, col in [
        ("momentum", "momentum_net_return"),
        ("route_b_overlay", "overlay_net_return"),
        ("vol_timed_momentum", "vol_timed_momentum_net_return"),
    ]:
        row = {"sample": "aligned_vol_control", "series": label, **perf(valid[col], args.annualization)}
        rows.append(row)
    summary = pd.DataFrame(rows)

    aligned_sharpes = summary.loc[summary["sample"].eq("aligned_vol_control")].set_index("series")[
        "sharpe"
    ]
    comparisons = {
        "lookback_periods": args.lookback_periods,
        "min_periods": args.min_periods,
        "annualization_rebalances_per_year": args.annualization,
        "target_period_vol": target_vol,
        "max_leverage": args.max_leverage,
        "n_valid_comparison_periods": int(valid.shape[0]),
        "mean_scale": float(valid["vol_timing_scale"].mean()),
        "min_scale": float(valid["vol_timing_scale"].min()),
        "max_scale": float(valid["vol_timing_scale"].max()),
        "corr_overlay_vol_timed": float(
            valid["overlay_net_return"].corr(valid["vol_timed_momentum_net_return"])
        ),
        "paired_t_overlay_minus_vol_timed": paired_t(valid["overlay_minus_vol_timed"]),
        "paired_t_vol_timed_minus_momentum": paired_t(valid["vol_timed_minus_momentum"]),
        "aligned_sharpe_gap_overlay_minus_vol_timed": float(
            aligned_sharpes["route_b_overlay"] - aligned_sharpes["vol_timed_momentum"]
        ),
        "aligned_sharpe_gap_vol_timed_minus_momentum": float(
            aligned_sharpes["vol_timed_momentum"] - aligned_sharpes["momentum"]
        ),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_dir / "vol_timing_returns.csv", index=False)
    summary.to_csv(out_dir / "vol_timing_summary.csv", index=False)
    (out_dir / "run_summary.json").write_text(json.dumps(comparisons, indent=2), encoding="utf-8")

    print(summary.to_string(index=False))
    print(json.dumps(comparisons, indent=2))
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
