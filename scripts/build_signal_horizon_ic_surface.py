#!/usr/bin/env python3
"""Signal x horizon ICIR surface (Step 1 of the frequency-band alignment plan).

Purpose
-------
Each cross-sectional signal has an *economic frequency band* -- the horizon over
which its mechanism actually pays (short-term reversal at 1-5d, 12-1 momentum at
20-60d, etc.). This script maps that band empirically by computing, for a small
*pre-registered* set of signals and a grid of horizons, the overlap-adjusted
rank-IC information ratio (ICIR) and a non-overlap t-stat.

Discipline
----------
* Signals and their candidate bands are chosen from economics, NOT grid-searched,
  so the multiple-testing burden stays tiny (keeps a later DSR honest).
* Bands are *discovered* on the pre-2022 split and *confirmed* on the untouched
  2022+ hold-out. The hold-out never selects the native horizon.
* Evaluation reuses the production pipeline (run_model_pipeline) for the T+1
  execution lag, the bottom-decile liquidity universe, per-date winsorization,
  and the overlap-adjusted ICIR, so numbers are comparable to the report.

This script does NOT train models. It is a read-only diagnostic over existing
feature/target parquet files.
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

# Pre-registered signals (one or two per economic family) -> source feature file.
# The expected sign is documented for interpretation only; |ICIR| locates the band.
SIGNAL_FILE = {
    "ret_1d": "price_momentum",            # very-short reversal (expect <0 at h=1)
    "ret_5d": "price_momentum",            # short reversal      (expect <0 at h=1-5)
    "mom_20d_skip_5d": "price_momentum",   # short momentum
    "mom_60d_skip_20d": "price_momentum",  # intermediate momentum
    "mom_252d_skip_21d": "price_momentum", # 12-1 momentum       (expect >0 at h=20-60)
    "vol_20d": "volatility",               # low-vol             (expect <0)
    "idio_vol_60d": "statistical_linkage", # idiosyncratic low-vol (expect <0)
    "beta_60d": "statistical_linkage",     # low-beta            (expect <0)
    "amihud_20d": "liquidity_volume",      # illiquidity premium (expect >0)
    "volume_z_20d": "liquidity_volume",    # volume shock
    "rsi_14d": "trend_technical",          # overbought reversal (expect <0)
    "sma_gap_20d": "trend_technical",      # trend / price-vs-SMA
}
DEFAULT_HORIZONS = [1, 5, 20, 40, 60, 90]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-dir", default="data/processed/features_by_group")
    p.add_argument("--out-dir", default="output/signal_horizon_surface")
    p.add_argument("--target-family", default="excess_sector",
                   choices=["excess_sector", "excess_market"])
    p.add_argument("--horizons", nargs="*", type=int, default=DEFAULT_HORIZONS)
    p.add_argument("--start-date", default="2008-01-01")
    p.add_argument("--val-end", default="2021-12-31")
    p.add_argument("--execution-lag-days", type=int, default=1)
    p.add_argument("--liquidity-drop-pct", type=float, default=0.10)
    p.add_argument("--winsorize-pct", type=float, default=0.01)
    p.add_argument("--min-names", type=int, default=100)
    return p.parse_args()


def load_panel(feature_dir: Path, horizons: list[int], family: str,
               start_date: str) -> pd.DataFrame:
    """Join the needed signal columns and (target, return) columns per horizon."""
    target_cols, return_cols = [], []
    for h in horizons:
        target_cols.append(f"target_{family}_fwd_{h}d")
        return_cols.append(f"target_ret_fwd_{h}d")

    base = pd.read_parquet(
        feature_dir / "targets.parquet",
        columns=rmp.KEY_COLS + ["sector"] + target_cols + return_cols,
    )
    base["date"] = pd.to_datetime(base["date"])
    base = base.loc[base["date"] >= pd.Timestamp(start_date)].reset_index(drop=True)

    # group signals by source file and merge once per file (+ dollar_volume for liquidity)
    by_file: dict[str, list[str]] = {}
    for sig, fname in SIGNAL_FILE.items():
        by_file.setdefault(fname, []).append(sig)
    for fname, sigs in by_file.items():
        cols = list(sigs)
        if fname == "price_momentum":
            cols = cols + ["dollar_volume"]
        part = pd.read_parquet(feature_dir / f"{fname}.parquet",
                               columns=rmp.KEY_COLS + cols)
        part["date"] = pd.to_datetime(part["date"])
        base = base.merge(part, on=rmp.KEY_COLS, how="inner")
    return base


def ic_table(df: pd.DataFrame, signals: list[str], target_col: str,
             min_names: int) -> pd.DataFrame:
    """One groupby pass: per-date rank-IC of every signal vs target_col."""
    out = []
    for dt, g in df.groupby("date", sort=True, observed=True):
        if len(g) < min_names:
            continue
        t = g[target_col]
        rec: dict[str, object] = {"date": dt, "n": int(len(g))}
        tvalid = t.notna()
        for s in signals:
            sv = g[s]
            mask = sv.notna() & tvalid
            if int(mask.sum()) < min_names:
                rec[s] = math.nan
                continue
            # Rank both on the common non-missing subset (matches spearman_by_date).
            rec[s] = rmp.safe_corrcoef(sv[mask].rank(), t[mask].rank())
        out.append(rec)
    return pd.DataFrame(out)


def nonoverlap_tstat(ic_series: pd.Series, horizon: int) -> tuple[float, int]:
    vals = ic_series.dropna()
    if vals.empty:
        return math.nan, 0
    no = vals.iloc[::max(1, horizon)]
    if len(no) < 3:
        return math.nan, int(len(no))
    t = float(no.mean() / (no.std(ddof=1) / math.sqrt(len(no)) + 1e-12))
    return t, int(len(no))


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    signals = [s for s in SIGNAL_FILE if s in SIGNAL_FILE]

    print(f"Loading panel: family={args.target_family} horizons={args.horizons} "
          f"start={args.start_date}")
    panel = load_panel(Path(args.feature_dir), args.horizons, args.target_family,
                       args.start_date)
    print(f"Panel rows={len(panel):,} dates={panel['date'].nunique()} "
          f"symbols={panel['symbol'].nunique()}")

    val_end = pd.Timestamp(args.val_end)
    long_rows = []
    for h in args.horizons:
        target_col = f"target_{args.target_family}_fwd_{h}d"
        return_col = f"target_ret_fwd_{h}d"
        keep = rmp.KEY_COLS + ["sector", "dollar_volume", target_col, return_col] + signals
        sub = panel[keep].copy()
        # T+1 execution lag + drop rows whose forward label is unavailable.
        sub = rmp.attach_effective_labels(
            sub, target_col, return_col, horizon_days=h,
            execution_lag_days=args.execution_lag_days,
        )
        # Tradable universe + outlier control, matching the production pipeline.
        sub = rmp.apply_liquidity_universe(sub, "dollar_volume", args.liquidity_drop_pct)
        sub = rmp.winsorize_by_date(sub, signals, args.winsorize_pct)
        sub["split"] = np.where(sub["date"] <= val_end, "discovery", "test")

        for split in ("discovery", "test"):
            part = sub.loc[sub["split"] == split]
            if part.empty:
                continue
            tbl = ic_table(part, signals, rmp.EVAL_TARGET_COL, args.min_names)
            if tbl.empty:
                continue
            for s in signals:
                ic_df = tbl[["date", s]].rename(columns={s: "rank_ic"})
                summ = rmp.summarize_ic(ic_df, horizon_days=h)
                tstat, n_no = nonoverlap_tstat(tbl[s], h)
                long_rows.append({
                    "signal": s,
                    "horizon": h,
                    "split": split,
                    "mean_rank_ic": summ["mean_rank_ic"],
                    "rank_ic_ir": summ["rank_ic_ir"],
                    "rank_ic_ir_raw": summ["rank_ic_ir_raw"],
                    "t_stat_nonoverlap": tstat,
                    "n_dates": summ["ic_dates"],
                    "n_nonoverlap": n_no,
                })
        print(f"  horizon {h:>2}d done.")

    long = pd.DataFrame(long_rows)
    long_path = out_dir / f"ic_surface_long_{args.target_family}.csv"
    long.to_csv(long_path, index=False)

    # Discovery ICIR pivot (the band-discovery heatmap source).
    disc = long.loc[long["split"] == "discovery"]
    pivot = disc.pivot(index="signal", columns="horizon", values="rank_ic_ir")
    pivot = pivot.reindex(signals)
    pivot_path = out_dir / f"ic_surface_pivot_discovery_icir_{args.target_family}.csv"
    pivot.to_csv(pivot_path)

    # Native horizon = argmax |ICIR| on discovery; report its test confirmation.
    native_rows = []
    for s in signals:
        d = disc.loc[disc["signal"] == s]
        if d.empty or d["rank_ic_ir"].abs().max() == 0:
            continue
        best = d.loc[d["rank_ic_ir"].abs().idxmax()]
        h = int(best["horizon"])
        t = long.loc[(long["signal"] == s) & (long["horizon"] == h)
                     & (long["split"] == "test")]
        native_rows.append({
            "signal": s,
            "native_horizon": h,
            "disc_icir": round(float(best["rank_ic_ir"]), 3),
            "disc_mean_ic": round(float(best["mean_rank_ic"]), 4),
            "disc_t": round(float(best["t_stat_nonoverlap"]), 2),
            "test_icir": round(float(t["rank_ic_ir"].iloc[0]), 3) if not t.empty else math.nan,
            "test_mean_ic": round(float(t["mean_rank_ic"].iloc[0]), 4) if not t.empty else math.nan,
            "test_t": round(float(t["t_stat_nonoverlap"].iloc[0]), 2) if not t.empty else math.nan,
            "sign_stable": bool(not t.empty and np.sign(best["rank_ic_ir"]) == np.sign(t["rank_ic_ir"].iloc[0])),
        })
    native = pd.DataFrame(native_rows)
    native_path = out_dir / f"native_horizon_summary_{args.target_family}.csv"
    native.to_csv(native_path, index=False)

    # Console summaries.
    try:
        from tabulate import tabulate
        print("\n=== Discovery ICIR surface (signal x horizon) ===")
        print(tabulate(pivot.round(2), headers=[f"{c}d" for c in pivot.columns],
                       tablefmt="github", floatfmt=".2f"))
        print("\n=== Native horizon (discovered <=2021, confirmed on 2022+) ===")
        print(tabulate(native, headers="keys", tablefmt="github", showindex=False))
    except Exception:
        print("\nDiscovery ICIR pivot:\n", pivot.round(2).to_string())
        print("\nNative horizon summary:\n", native.to_string(index=False))

    # Optional heatmap.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(1.4 * len(pivot.columns) + 2, 0.5 * len(pivot) + 2))
        data = pivot.to_numpy(dtype=float)
        vmax = np.nanmax(np.abs(data)) if np.isfinite(data).any() else 1.0
        im = ax.imshow(data, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"{c}d" for c in pivot.columns])
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(list(pivot.index))
        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                if np.isfinite(data[i, j]):
                    ax.text(j, i, f"{data[i, j]:.2f}", ha="center", va="center",
                            fontsize=8, color="black")
        ax.set_title(f"Discovery rank-ICIR surface ({args.target_family}, <=2021)")
        fig.colorbar(im, ax=ax, label="overlap-adjusted rank ICIR")
        fig.tight_layout()
        png = out_dir / f"ic_surface_heatmap_{args.target_family}.png"
        fig.savefig(png, dpi=150)
        print(f"\nHeatmap -> {png}")
    except Exception as exc:  # pragma: no cover - matplotlib optional
        print(f"\n(heatmap skipped: {exc})")

    print(f"\nWrote:\n  {long_path}\n  {pivot_path}\n  {native_path}")


if __name__ == "__main__":
    main()
