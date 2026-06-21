#!/usr/bin/env python3
"""Build short-borrow haircut sensitivity for reported long-short books."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


BOOKS = [
    (
        "momentum_5d",
        5,
        "report/artifacts/momentum_portfolio_uncertainty/momentum_5d_returns.csv",
        "net_return",
    ),
    (
        "momentum_20d",
        20,
        "report/artifacts/momentum_portfolio_uncertainty/momentum_20d_returns.csv",
        "net_return",
    ),
    (
        "momentum_30d",
        30,
        "report/artifacts/momentum_portfolio_uncertainty/momentum_30d_returns.csv",
        "net_return",
    ),
    (
        "route_b_overlay_30d",
        30,
        "report/artifacts/route_b_paired_increment/paired_returns.csv",
        "overlay_net_return",
    ),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", default="report/artifacts/borrow_sensitivity")
    p.add_argument("--borrow-bps", nargs="*", type=float, default=[0.0, 25.0, 50.0, 100.0])
    p.add_argument(
        "--short-notional",
        type=float,
        default=0.5,
        help="Short-side notional as a fraction of reported book capital.",
    )
    return p.parse_args()


def summarize(returns: np.ndarray, periods_per_year: float) -> dict[str, float]:
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return {
            "n_periods": int(len(x)),
            "ann_return_arithmetic": math.nan,
            "ann_return_geometric": math.nan,
            "ann_vol": math.nan,
            "sharpe": math.nan,
            "max_drawdown": math.nan,
        }
    mean = float(x.mean())
    vol_period = float(x.std(ddof=1))
    equity = np.cumprod(1.0 + x)
    peak = np.maximum.accumulate(equity)
    drawdown = equity / peak - 1.0
    terminal = float(equity[-1])
    ann_return_geometric = terminal ** (periods_per_year / len(x)) - 1.0
    ann_vol = vol_period * math.sqrt(periods_per_year)
    return {
        "n_periods": int(len(x)),
        "ann_return_arithmetic": mean * periods_per_year,
        "ann_return_geometric": ann_return_geometric,
        "ann_vol": ann_vol,
        "sharpe": (mean / vol_period * math.sqrt(periods_per_year)) if vol_period > 0 else math.nan,
        "max_drawdown": float(drawdown.min()),
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | str | int]] = []
    for book, horizon, path_str, return_col in BOOKS:
        path = Path(path_str)
        df = pd.read_csv(path)
        if return_col not in df.columns:
            raise ValueError(f"{path} missing required column {return_col}")
        periods_per_year = 252.0 / horizon
        base = df[return_col].to_numpy(dtype=float)
        for borrow_bps in args.borrow_bps:
            period_haircut = (borrow_bps / 10000.0) * args.short_notional / periods_per_year
            adjusted = base - period_haircut
            row = {
                "book": book,
                "horizon_days": horizon,
                "source_file": path_str,
                "return_column": return_col,
                "borrow_bps_annual": borrow_bps,
                "short_notional_assumption": args.short_notional,
                "period_borrow_haircut": period_haircut,
            }
            row.update(summarize(adjusted, periods_per_year))
            rows.append(row)

    summary = pd.DataFrame(rows)
    summary_path = out_dir / "borrow_sensitivity.csv"
    summary.to_csv(summary_path, index=False)

    metadata = {
        "description": (
            "Sensitivity deducts annual stock-borrow cost from the assumed short "
            "notional and prorates it by rebalance horizon. Reported returns "
            "already include explicit 5 bps/side trading costs."
        ),
        "short_notional_assumption": args.short_notional,
        "borrow_bps_annual": args.borrow_bps,
        "books": [
            {
                "book": book,
                "horizon_days": horizon,
                "source_file": path,
                "return_column": return_col,
            }
            for book, horizon, path, return_col in BOOKS
        ],
    }
    (out_dir / "run_summary.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"\nWrote {summary_path}")


if __name__ == "__main__":
    main()
