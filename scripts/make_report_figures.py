#!/usr/bin/env python3
"""Generate the figures used in the S&P 500 case-study report.

Reads the walk-forward grid outputs produced by ``run_walk_forward.py`` /
``run_walk_forward_grid.sh`` / ``build_horizon_comparison.py`` and renders a
small set of publication-style PDF figures into ``report/figures``:

1. ``fig_horizon_icir.pdf``     - validation vs hold-out rank ICIR across
   horizons (best model per horizon), per target family.
2. ``fig_overlap_adjustment.pdf`` - overlap-adjusted hold-out ICIR vs the naive
   overlapping (raw) ICIR across horizons; documents the inflation the
   adjustment removes.
3. ``fig_model_comparison.pdf``  - validation mean ICIR by model family at the
   headline horizon (honest tree-vs-linear-vs-MLP comparison).
4. ``fig_fold_stability.pdf``    - per-fold rank ICIR across the expanding
   walk-forward folds for the headline run (regime stability).

The script is defensive: any figure whose inputs are missing is skipped with a
note rather than aborting the whole run, so it can be re-run as the grid fills
in results.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

MODEL_ORDER = ["ridge", "lightgbm", "xgboost", "mlp"]
MODEL_COLORS = {
    "ridge": "#4C72B0",
    "lightgbm": "#55A868",
    "xgboost": "#C44E52",
    "mlp": "#8172B3",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results-dir", default="output/walk_forward")
    p.add_argument("--comparison-csv", default="output/walk_forward/horizon_comparison.csv")
    p.add_argument("--out-dir", default="report/figures")
    p.add_argument("--headline-horizon", type=int, default=5)
    p.add_argument(
        "--headline-family",
        default=None,
        help="Target family for the headline fold-stability figure; if omitted, "
        "the family with the best validation ICIR at the headline horizon is used.",
    )
    return p.parse_args()


def load_comparison(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        print(f"[skip] comparison CSV not found: {path}")
        return None
    df = pd.read_csv(path)
    if df.empty:
        print(f"[skip] comparison CSV empty: {path}")
        return None
    return df


def best_per_horizon(df: pd.DataFrame, family: str) -> pd.DataFrame:
    sub = df[df["family"] == family].dropna(subset=["val_mean_icir"])
    if sub.empty:
        return sub
    idx = sub.groupby("horizon")["val_mean_icir"].idxmax()
    return df.loc[idx].sort_values("horizon").reset_index(drop=True)


def fig_horizon_icir(df: pd.DataFrame, out: Path) -> None:
    families = sorted(df["family"].dropna().unique())
    if not families:
        print("[skip] fig_horizon_icir: no families")
        return
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    plotted = False
    for fam in families:
        best = best_per_horizon(df, fam)
        if best.empty:
            continue
        ax.plot(best["horizon"], best["val_mean_icir"], marker="o", label=f"{fam} (val)")
        if "holdout_icir" in best and best["holdout_icir"].notna().any():
            ax.plot(
                best["horizon"],
                best["holdout_icir"],
                marker="s",
                linestyle="--",
                alpha=0.7,
                label=f"{fam} (hold-out)",
            )
        plotted = True
    if not plotted:
        plt.close(fig)
        print("[skip] fig_horizon_icir: nothing to plot")
        return
    ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Prediction horizon (trading days)")
    ax.set_ylabel("Rank ICIR (overlap-adjusted)")
    ax.set_title("Best-model rank ICIR by horizon")
    ax.legend(fontsize=7, frameon=False)
    fig.savefig(out)
    plt.close(fig)
    print(f"[ok] wrote {out}")


def fig_overlap_adjustment(df: pd.DataFrame, family: str, out: Path) -> None:
    best = best_per_horizon(df, family)
    if best.empty or "holdout_icir_raw" not in best:
        print("[skip] fig_overlap_adjustment: missing data")
        return
    sub = best.dropna(subset=["holdout_icir", "holdout_icir_raw"])
    if sub.empty:
        print("[skip] fig_overlap_adjustment: no hold-out ICIR pairs")
        return
    x = range(len(sub))
    width = 0.38
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.bar([i - width / 2 for i in x], sub["holdout_icir_raw"], width, label="Naive (overlapping)", color="#C44E52", alpha=0.85)
    ax.bar([i + width / 2 for i in x], sub["holdout_icir"], width, label="Overlap-adjusted", color="#4C72B0", alpha=0.85)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{int(h)}d" for h in sub["horizon"]])
    ax.set_xlabel("Prediction horizon")
    ax.set_ylabel("Hold-out rank ICIR")
    ax.set_title(f"Overlap inflation removed ({family})")
    ax.legend(fontsize=8, frameon=False)
    fig.savefig(out)
    plt.close(fig)
    print(f"[ok] wrote {out}")


def fig_model_comparison(df: pd.DataFrame, horizon: int, out: Path) -> None:
    sub = df[df["horizon"] == horizon].dropna(subset=["val_mean_icir"])
    if sub.empty:
        print(f"[skip] fig_model_comparison: no rows at horizon {horizon}")
        return
    families = sorted(sub["family"].dropna().unique())
    models = [m for m in MODEL_ORDER if m in sub["model"].unique()]
    models += [m for m in sorted(sub["model"].dropna().unique()) if m not in models]
    width = 0.8 / max(len(families), 1)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    for fi, fam in enumerate(families):
        fam_sub = sub[sub["family"] == fam].set_index("model")
        vals = [float(fam_sub.loc[m, "val_mean_icir"]) if m in fam_sub.index else 0.0 for m in models]
        xpos = [i + fi * width for i in range(len(models))]
        ax.bar(xpos, vals, width, label=fam, alpha=0.85)
    ax.set_xticks([i + (len(families) - 1) * width / 2 for i in range(len(models))])
    ax.set_xticklabels(models)
    ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Model")
    ax.set_ylabel("Validation mean rank ICIR")
    ax.set_title(f"Model comparison at {horizon}-day horizon")
    ax.legend(fontsize=8, frameon=False)
    fig.savefig(out)
    plt.close(fig)
    print(f"[ok] wrote {out}")


def pick_headline_run(df: pd.DataFrame, family: str, horizon: int) -> str | None:
    sub = df[(df["family"] == family) & (df["horizon"] == horizon)].dropna(subset=["val_mean_icir"])
    if sub.empty:
        return None
    row = sub.loc[sub["val_mean_icir"].idxmax()]
    return str(row["run_name"])


def fig_fold_stability(results_dir: Path, run_name: str, out: Path) -> None:
    meta = results_dir / run_name / "walk_forward_metrics.json"
    if not meta.exists():
        print(f"[skip] fig_fold_stability: {meta} not found")
        return
    data = json.loads(meta.read_text(encoding="utf-8"))
    folds = data.get("folds", []) or []
    if not folds:
        print("[skip] fig_fold_stability: no folds")
        return
    fdf = pd.DataFrame(folds)
    if "rank_ic_ir" not in fdf or "val_end" not in fdf:
        print("[skip] fig_fold_stability: missing fold columns")
        return
    years = pd.to_datetime(fdf["val_end"]).dt.year.astype(str)
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.bar(years, fdf["rank_ic_ir"], color="#4C72B0", alpha=0.85, label="validation fold ICIR")
    hold = (data.get("holdout", {}) or {}).get("rank_ic_ir")
    if hold is not None:
        ax.axhline(float(hold), color="#C44E52", linestyle="--", linewidth=1.2, label="hold-out ICIR")
    ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Validation fold (year)")
    ax.set_ylabel("Rank ICIR (overlap-adjusted)")
    ax.set_title(f"Walk-forward ICIR stability: {run_name}")
    ax.legend(fontsize=8, frameon=False)
    fig.savefig(out)
    plt.close(fig)
    print(f"[ok] wrote {out}")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir = Path(args.results_dir)

    df = load_comparison(Path(args.comparison_csv))
    if df is None:
        print("No comparison data yet; run the grid + build_horizon_comparison first.")
        return

    # Resolve the headline family at the headline horizon.
    family = args.headline_family
    if family is None:
        at_h = df[df["horizon"] == args.headline_horizon].dropna(subset=["val_mean_icir"])
        family = str(at_h.loc[at_h["val_mean_icir"].idxmax(), "family"]) if not at_h.empty else None
    if family is None and not df.empty:
        family = sorted(df["family"].dropna().unique())[0]
    print(f"Headline: family={family} horizon={args.headline_horizon}d")

    fig_horizon_icir(df, out_dir / "fig_horizon_icir.pdf")
    if family is not None:
        fig_overlap_adjustment(df, family, out_dir / "fig_overlap_adjustment.pdf")
    fig_model_comparison(df, args.headline_horizon, out_dir / "fig_model_comparison.pdf")
    if family is not None:
        run_name = pick_headline_run(df, family, args.headline_horizon)
        if run_name:
            fig_fold_stability(results_dir, run_name, out_dir / "fig_fold_stability.pdf")
        else:
            print("[skip] fig_fold_stability: no headline run resolved")


if __name__ == "__main__":
    main()
