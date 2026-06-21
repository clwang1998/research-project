#!/usr/bin/env python3
"""Build calendar-regime diagnostics for the momentum benchmark.

This paper diagnostic recomputes the sector-neutral 12-1 momentum book over
calendar slices using the same production evaluator controls as the main
hold-out table: T+1 effective labels, liquidity filter, within-date
winsorization, sector-neutral decile construction, non-overlapping h-day
rebalances, and 5 bps/side transaction costs. It does not retrain models.
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


DEFAULT_REGIMES = {
    "GFC+recovery_2008_2011": ("2008-01-01", "2011-12-31"),
    "QE_lowvol_2012_2016": ("2012-01-01", "2016-12-31"),
    "latecycle_covid_2017_2021": ("2017-01-01", "2021-12-31"),
    "post2022_holdout_2022_2026": ("2022-01-01", "2026-12-31"),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-map", default="data/processed/feature_columns_by_group.csv")
    p.add_argument("--signal-col", default="cs_rank_mom_252d_skip_21d")
    p.add_argument("--horizons", nargs="*", type=int, default=[5, 30])
    p.add_argument("--target-template", default="target_excess_sector_fwd_{h}d")
    p.add_argument("--return-template", default="target_ret_fwd_{h}d")
    p.add_argument("--start-date", default="2008-01-01")
    p.add_argument("--end-date", default=None)
    p.add_argument("--sector-neutral", action="store_true", default=True)
    p.add_argument("--bootstrap-samples", type=int, default=10000)
    p.add_argument("--seed", type=int, default=20260622)
    p.add_argument("--regimes-json", default=None)
    p.add_argument("--out-dir", default="report/artifacts/momentum_regime_diagnostics")
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


def load_momentum_panel(args: argparse.Namespace, horizon: int) -> tuple[pd.DataFrame, SimpleNamespace]:
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

    panel = rmp.attach_effective_labels(
        panel, target_col, return_col, horizon_days, cfg.execution_lag_days
    )
    panel = rmp.apply_liquidity_universe(panel, "log_dollar_volume", cfg.min_dollar_volume_pct)
    panel = rmp.winsorize_by_date(panel, feature_cols, cfg.winsorize_pct)
    panel["model_score"] = panel[args.signal_col]
    panel = panel.dropna(subset=["model_score", rmp.EVAL_TARGET_COL, rmp.EVAL_RETURN_COL]).copy()
    return panel, cfg


def bootstrap_sharpe(
    returns: np.ndarray, periods_per_year: float, n_boot: int, rng: np.random.Generator
) -> np.ndarray:
    x = np.asarray(returns, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return np.array([])
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
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


def regime_metrics(
    panel: pd.DataFrame,
    cfg: SimpleNamespace,
    regime_name: str,
    start: str,
    end: str,
    n_boot: int,
    rng: np.random.Generator,
) -> tuple[dict[str, object], pd.DataFrame]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    sub = panel.loc[(panel["date"] >= start_ts) & (panel["date"] <= end_ts)].copy()
    horizon = int(cfg.label_horizon_days)
    periods_per_year = 252.0 / horizon
    ic = rmp.spearman_by_date(sub, "model_score", rmp.EVAL_TARGET_COL, cfg.min_names_per_date)
    bt = rmp.run_backtest(
        sub,
        "model_score",
        rmp.EVAL_RETURN_COL,
        cfg.long_short_pct,
        horizon,
        cfg.transaction_cost_bps,
        cfg.min_names_per_date,
        cfg.sector_neutral,
    )
    metrics = {**rmp.summarize_ic(ic, horizon), **rmp.summarize_backtest(bt, periods_per_year)}
    returns = bt["net_return"].to_numpy(dtype=float) if not bt.empty else np.array([])
    boot = bootstrap_sharpe(returns, periods_per_year, n_boot, rng)
    row = {
        "regime": regime_name,
        "start": start,
        "end": end,
        "horizon_days": horizon,
        "rows": int(len(sub)),
        "dates": int(sub["date"].nunique()) if not sub.empty else 0,
        "n_rebalance_periods": int(len(returns)),
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
        "bootstrap_sharpe_ci_2p5": float(np.quantile(boot, 0.025)) if len(boot) else math.nan,
        "bootstrap_sharpe_ci_97p5": float(np.quantile(boot, 0.975)) if len(boot) else math.nan,
        "bootstrap_prob_sharpe_positive": float(np.mean(boot > 0.0)) if len(boot) else math.nan,
    }
    return row, bt


def main() -> None:
    args = parse_args()
    regimes = DEFAULT_REGIMES
    if args.regimes_json:
        regimes = json.loads(Path(args.regimes_json).read_text(encoding="utf-8"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []

    for horizon in args.horizons:
        panel, cfg = load_momentum_panel(args, horizon)
        for regime_name, bounds in regimes.items():
            start, end = bounds
            rng = np.random.default_rng(args.seed + horizon + len(rows))
            row, bt = regime_metrics(
                panel, cfg, str(regime_name), str(start), str(end), args.bootstrap_samples, rng
            )
            rows.append(row)
            bt.to_csv(out_dir / f"momentum_{horizon}d_{regime_name}_returns.csv", index=False)

    summary = pd.DataFrame(rows)
    summary_path = out_dir / "momentum_regime_diagnostics.csv"
    summary.to_csv(summary_path, index=False)
    metadata = {
        "signal_col": args.signal_col,
        "sector_neutral": bool(args.sector_neutral),
        "bootstrap_samples_requested": args.bootstrap_samples,
        "seed": args.seed,
        "horizons": args.horizons,
        "regimes": regimes,
        "interpretation": (
            "Calendar-slice diagnostic for a no-fit momentum signal. This is not "
            "a CPCV distribution or independent model retraining exercise."
        ),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out_dir / "README.md").write_text(
        "# Momentum regime diagnostics\n\n"
        "Calendar-slice sector-neutral 12-1 momentum diagnostics using production "
        "evaluation controls. These rows stress the benchmark's regime dependence; "
        "they do not supply pre-2022 Route B overlay evidence because saved Route B "
        "post-training predictions are only available for validation/test windows.\n",
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(f"\nWrote {summary_path}")


if __name__ == "__main__":
    main()
