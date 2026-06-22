#!/usr/bin/env python3
"""Reconcile Route B overlay IC under the canonical raw-label convention.

The robustness audit reports economics for the residual overlay using the
residualized evaluation label. The paper's momentum baseline IC is reported
against the raw forward relative-return label. This focused audit recomputes
baseline/model/overlay Rank IC under both conventions for the selected Route B
prediction stream and writes a small traceability artifact.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_alpha_robustness_audit as audit  # noqa: E402
import run_model_pipeline as rmp  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--prediction-path",
        default=(
            "output/model_search/"
            "route_b_factor_residual_alpha_core_20260622__"
            "target_excess_sector_fwd_30d__tabular__xgboost__xgb_balanced/"
            "predictions_val_test.parquet"
        ),
    )
    p.add_argument("--overlay-lambda", type=float, default=0.2)
    p.add_argument("--val-end", default="2021-12-31")
    p.add_argument("--horizon-days", type=int, default=30)
    p.add_argument("--min-names", type=int, default=100)
    p.add_argument("--out-dir", default="report/artifacts/route_b_canonical_ic")
    return p.parse_args()


def lambda_label(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def main() -> None:
    args = parse_args()
    pred = pd.read_parquet(args.prediction_path)
    pred["date"] = pd.to_datetime(pred["date"])
    pred = audit.add_residual_overlay_score(pred, args.overlay_lambda)
    test = pred.loc[pred["date"] > pd.Timestamp(args.val_end)].copy()

    score_cols = [
        ("baseline_score", "momentum_baseline"),
        ("model_score", "residual_model"),
        ("residual_overlay_score", f"route_b_overlay_lambda_{lambda_label(args.overlay_lambda)}"),
    ]
    target_cols = [
        (rmp.RAW_EVAL_TARGET_COL, "canonical_raw_label"),
        (rmp.EVAL_TARGET_COL, "residualized_eval_label"),
    ]
    rows = []
    for score_col, signal in score_cols:
        for target_col, convention in target_cols:
            ic = rmp.spearman_by_date(test, score_col, target_col, args.min_names)
            summary = rmp.summarize_ic(ic, args.horizon_days)
            rows.append(
                {
                    "split": "test",
                    "signal": signal,
                    "label_convention": convention,
                    "mean_rank_ic": summary["mean_rank_ic"],
                    "rank_ic_ir": summary["rank_ic_ir"],
                    "rank_ic_ir_raw": summary["rank_ic_ir_raw"],
                    "ic_dates": summary["ic_dates"],
                    "ic_dates_nonoverlap": summary["ic_dates_nonoverlap"],
                    "prediction_path": args.prediction_path,
                }
            )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "route_b_overlay_canonical_ic.csv"
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
