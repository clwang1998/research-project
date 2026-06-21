#!/usr/bin/env python3
"""Build traded-horizon momentum portfolio uncertainty artifacts.

This paper-audit diagnostic recomputes the sector-neutral 12-1 momentum
baseline at traded horizons and adds uncertainty to the portfolio Sharpe point
estimates. It reuses the production walk-forward evaluator defaults for
execution lag, purge/embargo, liquidity, winsorization, transaction costs, and
sector-neutral decile long-short construction.
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
import run_model_pipeline as rmp  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-map", default="data/processed/feature_columns_by_group.csv")
    p.add_argument("--signal-col", default="cs_rank_mom_252d_skip_21d")
    p.add_argument("--horizons", nargs="*", type=int, default=[5, 20, 30])
    p.add_argument("--target-template", default="target_excess_sector_fwd_{h}d")
    p.add_argument("--return-template", default="target_ret_fwd_{h}d")
    p.add_argument("--start-date", default="2008-01-01")
    p.add_argument("--end-date", default=None)
    p.add_argument("--holdout-start", default="2022-01-01")
    p.add_argument("--sector-neutral", action="store_true", default=True)
    p.add_argument("--bootstrap-samples", type=int, default=20000)
    p.add_argument("--seed", type=int, default=20260621)
    p.add_argument("--out-dir", default="report/artifacts/momentum_portfolio_uncertainty")
    return p.parse_args()


def production_cfg(args: argparse.Namespace, target_col: str, return_col: str) -> SimpleNamespace:
    saved = sys.argv
    try:
        sys.argv = [saved[0]]
        cfg = rmp.parse_args()
    finally:
        sys.argv = saved
    cfg.target_col = target_col
    cfg.return_col = return_col
    cfg.start_date = args.start_date
    cfg.end_date = args.end_date
    cfg.feature_map = args.feature_map
    cfg.sector_neutral = bool(args.sector_neutral)
    return cfg


def momentum_backtest(args: argparse.Namespace, horizon: int) -> tuple[dict[str, float], pd.DataFrame]:
    target_col = args.target_template.format(h=horizon)
    return_col = args.return_template.format(h=horizon)
    cfg = production_cfg(args, target_col, return_col)

    fmap = rmp.read_feature_map(args.feature_map)
    feature_cols = rmp.select_feature_columns(cfg, fmap)
    if args.signal_col not in feature_cols:
        feature_cols = list(dict.fromkeys(feature_cols + [args.signal_col]))

    panel = rmp.load_panel(cfg, feature_cols, fmap)
    horizon_days = rmp.infer_horizon_days(target_col, return_col)
    if horizon_days != horizon:
        raise ValueError(f"Resolved horizon {horizon_days} from {target_col}, expected {horizon}")
    cfg.label_horizon_days = horizon_days
    embargo_days = rmp.resolve_embargo_days(horizon_days, cfg.embargo_days)

    panel = rmp.attach_effective_labels(
        panel, target_col, return_col, horizon_days, cfg.execution_lag_days
    )
    panel = rmp.apply_liquidity_universe(panel, "log_dollar_volume", cfg.min_dollar_volume_pct)
    panel = rmp.winsorize_by_date(panel, feature_cols, cfg.winsorize_pct)

    holdout_start = pd.Timestamp(args.holdout_start)
    holdout_train_end = holdout_start - pd.Timedelta(days=1)
    raw = rmp.split_masks(panel, str(holdout_train_end.date()), str(holdout_train_end.date()))
    masks = rmp.apply_purge_embargo(
        panel, raw, str(holdout_train_end.date()), str(holdout_train_end.date()), embargo_days
    )
    sub = panel.loc[masks["test"]].copy()
    sub["model_score"] = sub[args.signal_col]
    sub = sub.dropna(subset=["model_score", rmp.EVAL_TARGET_COL, rmp.EVAL_RETURN_COL])

    ic = rmp.spearman_by_date(sub, "model_score", rmp.EVAL_TARGET_COL, cfg.min_names_per_date)
    bt = rmp.run_backtest(
        sub,
        "model_score",
        rmp.EVAL_RETURN_COL,
        cfg.long_short_pct,
        horizon_days,
        cfg.transaction_cost_bps,
        cfg.min_names_per_date,
        cfg.sector_neutral,
    )
    periods_per_year = 252.0 / horizon_days
    metrics = {**rmp.summarize_ic(ic, horizon_days), **rmp.summarize_backtest(bt, periods_per_year)}
    return metrics, bt


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


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    readme_lines = [
        "# Momentum portfolio uncertainty",
        "",
        "Sector-neutral 12-1 momentum baseline recomputed with the production",
        "walk-forward evaluator controls. Sharpe intervals are deterministic iid",
        f"bootstrap resamples of non-overlapping net rebalance returns, seed {args.seed},",
        f"{args.bootstrap_samples:,} draws.",
        "",
    ]

    for horizon in args.horizons:
        metrics, bt = momentum_backtest(args, horizon)
        periods_per_year = 252.0 / horizon
        returns = bt["net_return"].to_numpy(dtype=float)
        rng = np.random.default_rng(args.seed)
        boot = bootstrap_sharpe(returns, periods_per_year, args.bootstrap_samples, rng)
        row = {
            "horizon_days": horizon,
            "target_col": args.target_template.format(h=horizon),
            "n_periods": int(len(returns)),
            "annualization_rebalances_per_year": periods_per_year,
            "rank_ic": metrics.get("mean_rank_ic"),
            "rank_ic_ir": metrics.get("rank_ic_ir"),
            "rank_ic_ir_raw": metrics.get("rank_ic_ir_raw"),
            "sharpe_net": metrics.get("sharpe_net"),
            "ann_return_net": metrics.get("ann_return_net"),
            "ann_vol_net": metrics.get("ann_vol_net"),
            "max_drawdown_net": metrics.get("max_drawdown_net"),
            "avg_turnover": metrics.get("avg_turnover"),
            "mean_return_t_stat": mean_t_stat(returns),
            "bootstrap_samples": int(len(boot)),
            "bootstrap_sharpe_ci_2p5": float(np.quantile(boot, 0.025)),
            "bootstrap_sharpe_ci_97p5": float(np.quantile(boot, 0.975)),
            "bootstrap_prob_sharpe_positive": float(np.mean(boot > 0.0)),
        }
        rows.append(row)
        bt.to_csv(out_dir / f"momentum_{horizon}d_returns.csv", index=False)
        readme_lines.extend(
            [
                f"- {horizon}d: n={row['n_periods']}, Sharpe={row['sharpe_net']:.6f}, "
                f"mean-return t={row['mean_return_t_stat']:.6f}, "
                f"bootstrap Sharpe CI=[{row['bootstrap_sharpe_ci_2p5']:.6f}, "
                f"{row['bootstrap_sharpe_ci_97p5']:.6f}], "
                f"turnover={row['avg_turnover']:.6f}",
            ]
        )

    summary = pd.DataFrame(rows)
    summary_path = out_dir / "momentum_portfolio_uncertainty.csv"
    summary.to_csv(summary_path, index=False)
    metadata = {
        "signal_col": args.signal_col,
        "holdout_start": args.holdout_start,
        "sector_neutral": bool(args.sector_neutral),
        "bootstrap_samples_requested": args.bootstrap_samples,
        "seed": args.seed,
        "horizons": args.horizons,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"\nWrote {summary_path}")


if __name__ == "__main__":
    main()
