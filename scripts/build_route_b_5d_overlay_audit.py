#!/usr/bin/env python3
"""Audit the endorsed-horizon 5-day Route B residual overlay.

This is a focused post-training paper diagnostic. It consumes the existing
5-day Route B prediction stream, selects the residual-overlay weight on
2019--2021 validation Sharpe, and evaluates the selected overlay against the
standalone momentum baseline on the 2022--2026 hold-out.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_alpha_robustness_audit as audit  # noqa: E402
import run_model_pipeline as rmp  # noqa: E402


DEFAULT_PREDICTION_PATH = (
    "output/model_search/"
    "route_b_factor_residual_alpha_core_20260622__"
    "target_excess_sector_fwd_5d__tabular__xgboost__xgb_balanced/"
    "predictions_val_test.parquet"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prediction-path", default=DEFAULT_PREDICTION_PATH)
    p.add_argument("--model-search-dir", default="output/model_search")
    p.add_argument("--target-col", default="target_excess_sector_fwd_5d")
    p.add_argument("--return-col", default="target_ret_fwd_5d")
    p.add_argument("--val-end", default="2021-12-31")
    p.add_argument("--horizon-days", type=int, default=5)
    p.add_argument("--long-short-pct", type=float, default=0.10)
    p.add_argument("--min-names-per-date", type=int, default=100)
    p.add_argument("--transaction-cost-bps", type=float, default=5.0)
    p.add_argument("--sector-neutral", action="store_true", default=True)
    p.add_argument(
        "--lambdas",
        nargs="*",
        type=float,
        default=[0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0],
    )
    p.add_argument("--bootstrap-samples", type=int, default=10000)
    p.add_argument("--bootstrap-blocks", type=int, default=5)
    p.add_argument("--seed", type=int, default=20260622)
    p.add_argument("--out-dir", default="report/artifacts/route_b_5d_overlay_audit")
    return p.parse_args()


def eval_score(
    frame: pd.DataFrame, score_col: str, args: argparse.Namespace
) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
    cfg = argparse.Namespace(
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
    periods_per_year = 252.0 / cfg.rebalance_every
    metrics = {
        **rmp.summarize_ic(ic, cfg.label_horizon_days),
        **rmp.summarize_backtest(bt, periods_per_year),
    }
    return metrics, ic, bt


def paired_t(diff: pd.Series) -> float:
    d = diff.dropna().astype(float)
    if d.size < 3:
        return math.nan
    se = float(d.std(ddof=1) / math.sqrt(d.size))
    return float(d.mean() / se) if se > 0 else math.nan


def max_drawdown(returns: pd.Series) -> float:
    r = returns.dropna().astype(float)
    if r.empty:
        return math.nan
    equity = (1.0 + r).cumprod()
    return float((equity / equity.cummax() - 1.0).min())


def bootstrap_sharpe_gap(
    paired: pd.DataFrame,
    periods_per_year: float,
    samples: int,
    block_size: int,
    seed: int,
) -> tuple[float, float]:
    arr = paired[["momentum_net_return", "overlay_net_return"]].dropna().to_numpy(dtype=float)
    if len(arr) < 3:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    block_size = max(1, min(int(block_size), len(arr)))
    n_blocks = int(math.ceil(len(arr) / block_size))
    starts = np.arange(len(arr))
    gaps = np.empty(samples, dtype=float)
    for i in range(samples):
        chosen = rng.choice(starts, size=n_blocks, replace=True)
        idx = np.concatenate([(np.arange(s, s + block_size) % len(arr)) for s in chosen])[: len(arr)]
        sample = arr[idx]
        mom = audit.annualized_sharpe(sample[:, 0], periods_per_year)
        over = audit.annualized_sharpe(sample[:, 1], periods_per_year)
        gaps[i] = over - mom
    q = np.nanpercentile(gaps, [2.5, 97.5])
    return float(q[0]), float(q[1])


def write_readme(out_dir: Path, summary: pd.DataFrame, run_summary: dict[str, object]) -> None:
    lines = [
        "# Route B 5d overlay audit",
        "",
        "Focused post-training audit for the endorsed 5-day horizon. The script",
        "selects the residual-overlay lambda on validation Sharpe, then evaluates",
        "the selected overlay versus the standalone momentum baseline on the",
        "2022--2026 hold-out. It does not train models.",
        "",
        "## Paired summary",
        "",
        summary.to_markdown(index=False, floatfmt=".6f"),
        "",
        "## Run metadata",
        "",
        "```json",
        json.dumps(run_summary, indent=2, sort_keys=True),
        "```",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    pred = pd.read_parquet(args.prediction_path)
    pred["date"] = pd.to_datetime(pred["date"])
    val, test = audit.split_predictions(pred, args.val_end)

    rows: list[dict[str, object]] = []
    backtests: dict[tuple[str, float], pd.DataFrame] = {}
    for lam in args.lambdas:
        scored = audit.add_residual_overlay_score(pred, lam)
        val_l, test_l = audit.split_predictions(scored, args.val_end)
        for split_name, frame in [("val", val_l), ("test", test_l)]:
            metrics, _, bt = eval_score(frame, "residual_overlay_score", args)
            rows.append({"split": split_name, "signal": "residual_overlay", "lambda": lam, **metrics})
            backtests[(split_name, lam)] = bt

    for split_name, frame in [("val", val), ("test", test)]:
        metrics, _, bt = eval_score(frame, "baseline_score", args)
        rows.append({"split": split_name, "signal": "momentum_baseline", "lambda": 0.0, **metrics})
        backtests[(split_name, math.nan)] = bt

    metrics = pd.DataFrame(rows)
    val_overlays = metrics.loc[metrics["split"].eq("val") & metrics["signal"].eq("residual_overlay")]
    selected_lambda = float(val_overlays.loc[val_overlays["sharpe_net"].idxmax(), "lambda"])

    mom_bt = backtests[("test", math.nan)].rename(columns={"net_return": "momentum_net_return"})
    overlay_bt = backtests[("test", selected_lambda)].rename(columns={"net_return": "overlay_net_return"})
    paired = mom_bt[["date", "momentum_net_return"]].merge(
        overlay_bt[["date", "overlay_net_return"]], on="date", how="inner"
    )
    paired["increment_net_return"] = paired["overlay_net_return"] - paired["momentum_net_return"]
    periods_per_year = 252.0 / args.horizon_days
    low, high = bootstrap_sharpe_gap(
        paired, periods_per_year, args.bootstrap_samples, args.bootstrap_blocks, args.seed
    )

    selected = metrics.loc[
        metrics["split"].eq("test")
        & (
            metrics["signal"].eq("momentum_baseline")
            | (metrics["signal"].eq("residual_overlay") & metrics["lambda"].eq(selected_lambda))
        )
    ].copy()
    selected["selected_lambda"] = selected_lambda

    mom = paired["momentum_net_return"]
    over = paired["overlay_net_return"]
    diff = paired["increment_net_return"]
    summary = pd.DataFrame(
        [
            {
                "metric": "selected_lambda",
                "value": selected_lambda,
            },
            {"metric": "n_periods", "value": float(len(paired))},
            {"metric": "annualization_rebalances_per_year", "value": periods_per_year},
            {"metric": "momentum_ann_return", "value": float(mom.mean() * periods_per_year)},
            {"metric": "overlay_ann_return", "value": float(over.mean() * periods_per_year)},
            {"metric": "increment_ann_return_arithmetic", "value": float(diff.mean() * periods_per_year)},
            {"metric": "momentum_sharpe", "value": audit.annualized_sharpe(mom, periods_per_year)},
            {"metric": "overlay_sharpe", "value": audit.annualized_sharpe(over, periods_per_year)},
            {
                "metric": "sharpe_gap_overlay_minus_momentum",
                "value": audit.annualized_sharpe(over, periods_per_year)
                - audit.annualized_sharpe(mom, periods_per_year),
            },
            {"metric": "paired_return_diff_mean_per_period", "value": float(diff.mean())},
            {"metric": "paired_return_diff_t_stat", "value": paired_t(diff)},
            {"metric": "corr_overlay_momentum", "value": float(mom.corr(over))},
            {"metric": "momentum_max_drawdown", "value": max_drawdown(mom)},
            {"metric": "overlay_max_drawdown", "value": max_drawdown(over)},
            {"metric": "bootstrap_sharpe_gap_ci_2p5", "value": low},
            {"metric": "bootstrap_sharpe_gap_ci_97p5", "value": high},
        ]
    )

    returns = over.dropna()
    obs_sr = audit.annualized_sharpe(returns, periods_per_year)
    skewness, kurt = audit.skew_kurtosis(returns.to_numpy())
    trial_metrics = audit.load_trials_metrics(Path(args.model_search_dir))
    trial_counts = audit.infer_trial_counts(trial_metrics, args.target_col)
    trial_srs = trial_metrics.loc[
        (trial_metrics.get("split", pd.Series(dtype=object)).astype(str).eq("test"))
        & trial_metrics.get("sharpe_net", pd.Series(dtype=float)).notna(),
        "sharpe_net",
    ].astype(float)
    sr_std = (
        float(trial_srs.std(ddof=1))
        if len(trial_srs) > 1
        else 1.0 / math.sqrt(max(2, len(returns)))
    )
    ci = audit.bootstrap_sharpe_ci(
        returns, periods_per_year, args.bootstrap_samples, args.bootstrap_blocks, args.seed
    )
    mt_rows = []
    for key, n_trials in trial_counts.items():
        sr_star = audit.expected_max_sharpe_under_noise(sr_std, n_trials)
        mt_rows.append(
            {
                "trial_scope": key,
                "n_trials": n_trials,
                "observed_sharpe": obs_sr,
                "trial_sharpe_std": sr_std,
                "expected_max_null_sharpe": sr_star,
                "psr_vs_zero": audit.probabilistic_sharpe_ratio(obs_sr, 0.0, len(returns), skewness, kurt),
                "dsr": audit.probabilistic_sharpe_ratio(obs_sr, sr_star, len(returns), skewness, kurt),
                **ci,
            }
        )
    multiple_testing = pd.DataFrame(mt_rows)

    run_summary = {
        "prediction_path": args.prediction_path,
        "target_col": args.target_col,
        "return_col": args.return_col,
        "val_end": args.val_end,
        "horizon_days": args.horizon_days,
        "selected_lambda": selected_lambda,
        "lambda_selection": "maximum validation net Sharpe over supplied lambda grid",
        "lambdas": args.lambdas,
        "bootstrap_samples": args.bootstrap_samples,
        "bootstrap_blocks": args.bootstrap_blocks,
        "seed": args.seed,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(out_dir / "lambda_grid_metrics.csv", index=False)
    selected.to_csv(out_dir / "selected_signal_metrics.csv", index=False)
    paired.to_csv(out_dir / "paired_returns.csv", index=False)
    summary.to_csv(out_dir / "paired_increment_summary.csv", index=False)
    multiple_testing.to_csv(out_dir / "multiple_testing_dsr.csv", index=False)
    (out_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
    write_readme(out_dir, summary, run_summary)

    print(summary.to_string(index=False))
    print(multiple_testing.to_string(index=False))
    print(json.dumps({"out_dir": str(out_dir), **run_summary}, indent=2))


if __name__ == "__main__":
    main()
