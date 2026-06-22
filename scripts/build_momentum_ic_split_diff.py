#!/usr/bin/env python3
"""Bootstrap the momentum IC difference between discovery and hold-out.

This is a lightweight paper diagnostic that consumes the archived daily IC file
from ``build_momentum_ic_robustness.py`` and tests whether the post-2022
hold-out IC is statistically larger than the 2008--2021 discovery IC. The
bootstrap resamples each split with circular moving blocks and compares the
independent split means.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--daily-ic",
        default=(
            "report/artifacts/momentum_ic_traded_horizons_5d_split/"
            "momentum_daily_rank_ic.csv"
        ),
    )
    p.add_argument("--block-length", type=int, default=5)
    p.add_argument("--bootstrap-samples", type=int, default=20000)
    p.add_argument("--seed", type=int, default=20260622)
    p.add_argument(
        "--out-dir",
        default="report/artifacts/momentum_ic_traded_horizons_5d_split",
    )
    p.add_argument("--out-file", default="momentum_5d_ic_split_diff.csv")
    return p.parse_args()


def circular_block_means(
    values: np.ndarray, block_length: int, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n == 0:
        raise ValueError("Cannot bootstrap an empty IC series")
    block_length = max(1, min(block_length, n))
    n_blocks = int(math.ceil(n / block_length))
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    offsets = np.arange(block_length)
    out = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = (starts[i, :, None] + offsets[None, :]).reshape(-1)[:n] % n
        out[i] = float(x[idx].mean())
    return out


def main() -> None:
    args = parse_args()
    daily = pd.read_csv(args.daily_ic)
    required = {"split", "rank_ic"}
    missing = required.difference(daily.columns)
    if missing:
        raise ValueError(f"{args.daily_ic} missing columns: {sorted(missing)}")

    discovery = daily.loc[daily["split"] == "discovery", "rank_ic"].to_numpy()
    test = daily.loc[daily["split"] == "test", "rank_ic"].to_numpy()
    if len(discovery) == 0 or len(test) == 0:
        raise ValueError("Expected both discovery and test split rows")

    rng = np.random.default_rng(args.seed)
    discovery_boot = circular_block_means(
        discovery, args.block_length, args.bootstrap_samples, rng
    )
    test_boot = circular_block_means(
        test, args.block_length, args.bootstrap_samples, rng
    )
    diff_boot = test_boot - discovery_boot
    observed_diff = float(np.mean(test) - np.mean(discovery))
    summary = pd.DataFrame(
        [
            {
                "comparison": "test_minus_discovery",
                "n_discovery": int(len(discovery)),
                "n_test": int(len(test)),
                "mean_ic_discovery": float(np.mean(discovery)),
                "mean_ic_test": float(np.mean(test)),
                "mean_ic_diff": observed_diff,
                "block_length": int(args.block_length),
                "bootstrap_samples": int(args.bootstrap_samples),
                "diff_ci_2p5": float(np.quantile(diff_boot, 0.025)),
                "diff_ci_97p5": float(np.quantile(diff_boot, 0.975)),
                "diff_boot_se": float(np.std(diff_boot, ddof=1)),
                "diff_boot_t": observed_diff / float(np.std(diff_boot, ddof=1)),
                "p_diff_le_zero": float(np.mean(diff_boot <= 0.0)),
            }
        ]
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / args.out_file
    summary.to_csv(out_path, index=False)
    print(summary.to_string(index=False))
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()
