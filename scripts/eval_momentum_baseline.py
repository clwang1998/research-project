#!/usr/bin/env python3
"""Evaluate a single-factor momentum baseline on the walk-forward hold-out.

The baseline ranks stocks by a single cross-sectional momentum factor
(``cs_rank_mom_252d_skip_21d``, i.e. 12-month-minus-1-month momentum) with no
fitting, and is evaluated on exactly the same untouched hold-out window,
liquidity universe, winsorization, execution lag, purge, and embargo as the
trained models in ``run_walk_forward.py``. This gives the
``single-factor baseline vs multivariate model`` comparison the report needs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-map", default="data/processed/feature_columns_by_group.csv")
    p.add_argument("--signal-col", default="cs_rank_mom_252d_skip_21d")
    p.add_argument("--target-col", default="target_excess_sector_fwd_5d")
    p.add_argument("--return-col", default="target_ret_fwd_5d")
    p.add_argument("--start-date", default="2008-01-01")
    p.add_argument("--end-date", default=None)
    p.add_argument("--holdout-start", default="2022-01-01")
    p.add_argument("--sector-neutral", action="store_true")
    p.add_argument("--out-json", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    # Reuse the pipeline defaults for all leakage / backtest knobs.
    saved = sys.argv
    try:
        sys.argv = [saved[0]]
        cfg = rmp.parse_args()
    finally:
        sys.argv = saved
    cfg.target_col = args.target_col
    cfg.return_col = args.return_col
    cfg.start_date = args.start_date
    cfg.end_date = args.end_date
    cfg.feature_map = args.feature_map
    cfg.sector_neutral = bool(args.sector_neutral)

    fmap = rmp.read_feature_map(args.feature_map)
    feature_cols = rmp.select_feature_columns(cfg, fmap)
    if args.signal_col not in feature_cols:
        feature_cols = list(dict.fromkeys(feature_cols + [args.signal_col]))

    panel = rmp.load_panel(cfg, feature_cols, fmap)
    horizon_days = rmp.infer_horizon_days(args.target_col, args.return_col)
    embargo_days = rmp.resolve_embargo_days(horizon_days, cfg.embargo_days)
    rebalance_every = horizon_days
    cfg.label_horizon_days = horizon_days

    panel = rmp.attach_effective_labels(
        panel, args.target_col, args.return_col, horizon_days, cfg.execution_lag_days
    )
    panel = rmp.apply_liquidity_universe(panel, "log_dollar_volume", cfg.min_dollar_volume_pct)
    panel = rmp.winsorize_by_date(panel, feature_cols, cfg.winsorize_pct)

    holdout_start = pd.Timestamp(args.holdout_start)
    holdout_train_end = holdout_start - pd.Timedelta(days=1)
    raw = rmp.split_masks(panel, str(holdout_train_end.date()), str(holdout_train_end.date()))
    masks = rmp.apply_purge_embargo(
        panel, raw, str(holdout_train_end.date()), str(holdout_train_end.date()), embargo_days
    )
    test_mask = masks["test"]
    if not test_mask.any():
        print("No hold-out rows.")
        return
    sub = panel.loc[test_mask].copy()
    sub["model_score"] = sub[args.signal_col]
    sub = sub.dropna(subset=["model_score", rmp.EVAL_TARGET_COL])

    ic = rmp.spearman_by_date(sub, "model_score", rmp.EVAL_TARGET_COL, cfg.min_names_per_date)
    bt = rmp.run_backtest(
        sub, "model_score", rmp.EVAL_RETURN_COL, cfg.long_short_pct, rebalance_every,
        cfg.transaction_cost_bps, cfg.min_names_per_date, cfg.sector_neutral,
    )
    periods_per_year = 252.0 / rebalance_every
    metrics = {**rmp.summarize_ic(ic, horizon_days), **rmp.summarize_backtest(bt, periods_per_year)}
    out = {
        "baseline": "single_factor_momentum",
        "signal_col": args.signal_col,
        "target_col": args.target_col,
        "horizon_days": horizon_days,
        "holdout_start": args.holdout_start,
        "holdout_ic": metrics.get("mean_rank_ic"),
        "holdout_icir": metrics.get("rank_ic_ir"),
        "holdout_icir_raw": metrics.get("rank_ic_ir_raw"),
        "holdout_sharpe": metrics.get("sharpe_net"),
        "holdout_ann_return": metrics.get("ann_return_net"),
        "holdout_max_dd": metrics.get("max_drawdown_net"),
        "holdout_turnover": metrics.get("avg_turnover"),
        "sector_neutral": bool(cfg.sector_neutral),
    }
    print(json.dumps(out, indent=2))
    if args.out_json:
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"Wrote {args.out_json}")


if __name__ == "__main__":
    main()
