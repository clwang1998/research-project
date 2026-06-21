#!/usr/bin/env python3
"""Factor sleeve book (Steps 3-5 of the frequency-band alignment plan).

Builds a small, pre-registered multi-factor book from the signals that SURVIVED
the Step-1 hold-out (momentum + short reversal), combines them at the PORTFOLIO
level with inverse-vol weights (estimated on the pre-2022 split only), and judges
the result with the same rigor as the rest of the project:

* standalone vs combined net-of-cost Sharpe on discovery (<=2021) and the
  untouched 2022+ hold-out,
* the sleeve return-correlation matrix (the orthogonality / diversification
  evidence),
* a Deflated Sharpe Ratio for the combined book, computed in PER-OBSERVATION SR
  units (fixing the annualized-SR unit issue in run_alpha_robustness_audit),
  deflated against the full 12-signal scan as the trial distribution.

Read-only over existing parquet; trains nothing. Reuses run_model_pipeline for
the T+1 lag, liquidity universe, winsorization, and sector-neutral L/S weights.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_model_pipeline as rmp  # noqa: E402

# Economically-oriented sign for each scanned factor (long the side that should pay).
SIGN = {
    "ret_1d": -1, "ret_5d": -1,                       # short reversal
    "mom_20d_skip_5d": +1, "mom_60d_skip_20d": +1,    # momentum
    "mom_252d_skip_21d": +1,                          # 12-1 momentum
    "vol_20d": -1, "idio_vol_60d": -1, "beta_60d": -1,  # low-risk
    "amihud_20d": +1, "volume_z_20d": +1,             # illiquidity / volume
    "rsi_14d": -1, "sma_gap_20d": -1,                 # technical reversal
}
SIGNAL_FILE = {
    "ret_1d": "price_momentum", "ret_5d": "price_momentum",
    "mom_20d_skip_5d": "price_momentum", "mom_60d_skip_20d": "price_momentum",
    "mom_252d_skip_21d": "price_momentum", "vol_20d": "volatility",
    "idio_vol_60d": "statistical_linkage", "beta_60d": "statistical_linkage",
    "amihud_20d": "liquidity_volume", "volume_z_20d": "liquidity_volume",
    "rsi_14d": "trend_technical", "sma_gap_20d": "trend_technical",
}
# The book = the two signals that survived the Step-1 hold-out.
BOOK_SLEEVES = ["mom_252d_skip_21d", "ret_5d"]
GAMMA = 0.5772156649015329


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--feature-dir", default="data/processed/features_by_group")
    p.add_argument("--out-dir", default="output/factor_sleeve_book")
    p.add_argument("--target-family", default="excess_sector")
    p.add_argument("--rebalance-days", type=int, default=5)
    p.add_argument("--start-date", default="2008-01-01")
    p.add_argument("--val-end", default="2021-12-31")
    p.add_argument("--execution-lag-days", type=int, default=1)
    p.add_argument("--liquidity-drop-pct", type=float, default=0.10)
    p.add_argument("--winsorize-pct", type=float, default=0.01)
    p.add_argument("--long-short-pct", type=float, default=0.10)
    p.add_argument("--cost-bps", type=float, default=5.0)
    p.add_argument("--min-names", type=int, default=100)
    return p.parse_args()


def norm_cdf(x: float) -> float:
    return NormalDist().cdf(x)


def norm_ppf(p: float) -> float:
    return NormalDist().inv_cdf(min(max(p, 1e-12), 1 - 1e-12))


def load_panel(feature_dir: Path, family: str, horizon: int, start: str) -> pd.DataFrame:
    base = pd.read_parquet(
        feature_dir / "targets.parquet",
        columns=rmp.KEY_COLS + ["sector", f"target_{family}_fwd_{horizon}d",
                                f"target_ret_fwd_{horizon}d"],
    )
    base["date"] = pd.to_datetime(base["date"])
    base = base.loc[base["date"] >= pd.Timestamp(start)].reset_index(drop=True)
    by_file: dict[str, list[str]] = {}
    for sig, f in SIGNAL_FILE.items():
        by_file.setdefault(f, []).append(sig)
    for f, sigs in by_file.items():
        cols = list(sigs) + (["dollar_volume"] if f == "price_momentum" else [])
        part = pd.read_parquet(feature_dir / f"{f}.parquet", columns=rmp.KEY_COLS + cols)
        part["date"] = pd.to_datetime(part["date"])
        base = base.merge(part, on=rmp.KEY_COLS, how="inner")
    return base


def build_sleeve_weights(frame: pd.DataFrame, signals: list[str], pct: int,
                         min_names: int, rebalance_every: int):
    """Per rebalance date, sector-neutral L/S weights for every signal."""
    unique_dates = pd.Index(sorted(frame["date"].unique()))
    rdates = list(unique_dates[::rebalance_every])
    per_date: dict[pd.Timestamp, dict] = {}
    for dt in rdates:
        g = frame.loc[frame["date"] == dt]
        if len(g) < min_names:
            continue
        rec: dict[str, object] = {"_ret": g.dropna(subset=[rmp.EVAL_RETURN_COL])
                                  .set_index("symbol")[rmp.EVAL_RETURN_COL]}
        for s in signals:
            gg = g[["symbol", "sector", s]].dropna(subset=[s]).copy()
            gg["_score"] = SIGN[s] * gg[s]
            rec[s] = rmp.choose_weights(gg, "_score", pct, min_names, True)
        per_date[dt] = rec
    return rdates, per_date


def returns_from_combiner(rdates, per_date, combiner, cost_bps: float) -> pd.DataFrame:
    prev = pd.Series(dtype=np.float64)
    rows = []
    for dt in rdates:
        rec = per_date.get(dt)
        if rec is None:
            continue
        w = combiner(rec)
        if w is None or w.empty:
            continue
        ret = rec["_ret"]
        gross = float((w * ret.reindex(w.index)).fillna(0.0).sum())
        all_idx = w.index.union(prev.index)
        turn = 0.5 * float((w.reindex(all_idx, fill_value=0.0)
                            - prev.reindex(all_idx, fill_value=0.0)).abs().sum())
        cost = turn * cost_bps / 10000.0
        rows.append({"date": dt, "gross": gross, "turnover": turn, "net": gross - cost})
        prev = w
    return pd.DataFrame(rows)


def summarize(series: pd.DataFrame, ppy: float) -> dict:
    if series.empty:
        return {k: math.nan for k in ["sharpe_net", "ann_ret_net", "ann_vol_net",
                                      "max_dd_net", "avg_turnover", "periods"]}
    net = series["net"].to_numpy(dtype=np.float64)
    vol = net.std(ddof=1)
    eq = np.cumprod(1.0 + net)
    dd = float((eq / np.maximum.accumulate(eq) - 1.0).min())
    return {
        "sharpe_net": float(net.mean() / (vol + 1e-12) * math.sqrt(ppy)),
        "ann_ret_net": float(net.mean() * ppy),
        "ann_vol_net": float(vol * math.sqrt(ppy)),
        "max_dd_net": dd,
        "avg_turnover": float(series["turnover"].mean()),
        "periods": int(len(series)),
    }


def per_obs_sharpe(net: np.ndarray) -> float:
    net = net[np.isfinite(net)]
    if len(net) < 2 or net.std(ddof=1) == 0:
        return math.nan
    return float(net.mean() / net.std(ddof=1))


def deflated_sharpe(test_net: np.ndarray, trial_per_obs_sharpes: list[float]) -> dict:
    net = test_net[np.isfinite(test_net)]
    T = len(net)
    if T < 3:
        return {}
    sr = per_obs_sharpe(net)
    z = (net - net.mean()) / (net.std(ddof=0) + 1e-12)
    skew = float(np.mean(z**3))
    kurt = float(np.mean(z**4))
    trials = np.asarray([t for t in trial_per_obs_sharpes if math.isfinite(t)], dtype=float)
    N = len(trials)
    sr_std = float(trials.std(ddof=1)) if N > 1 else 0.0
    sr0 = (sr_std * ((1 - GAMMA) * norm_ppf(1 - 1.0 / N)
                     + GAMMA * norm_ppf(1 - 1.0 / (N * math.e)))) if (N > 1 and sr_std > 0) else 0.0
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurt - 1) / 4 * sr**2))
    psr = norm_cdf(sr * math.sqrt(T - 1) / denom)
    dsr = norm_cdf((sr - sr0) * math.sqrt(T - 1) / denom)
    return {"sr_per_obs": sr, "skew": skew, "kurtosis": kurt, "T": T,
            "n_trials": N, "trial_sr_std": sr_std, "expected_max_null_sr": sr0,
            "psr_vs_zero": psr, "dsr": dsr}


def block_bootstrap_sharpe_ci(net: np.ndarray, ppy: float, n: int = 2000,
                              block: int = 3, seed: int = 42) -> tuple[float, float]:
    net = net[np.isfinite(net)]
    if len(net) < 3:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    nb = int(math.ceil(len(net) / block))
    est = []
    for _ in range(n):
        starts = rng.integers(0, len(net), size=nb)
        s = np.concatenate([net[i:i + block] for i in starts])[:len(net)]
        if s.std(ddof=1) > 0:
            est.append(s.mean() / s.std(ddof=1) * math.sqrt(ppy))
    q = np.nanpercentile(est, [2.5, 97.5])
    return float(q[0]), float(q[1])


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    h = args.rebalance_days
    ppy = 252.0 / h
    val_end = pd.Timestamp(args.val_end)
    signals = list(SIGN)

    panel = load_panel(Path(args.feature_dir), args.target_family, h, args.start_date)
    panel = rmp.attach_effective_labels(
        panel, f"target_{args.target_family}_fwd_{h}d", f"target_ret_fwd_{h}d",
        horizon_days=h, execution_lag_days=args.execution_lag_days)
    panel = rmp.apply_liquidity_universe(panel, "dollar_volume", args.liquidity_drop_pct)
    panel = rmp.winsorize_by_date(panel, signals, args.winsorize_pct)
    print(f"Book panel rows={len(panel):,} dates={panel['date'].nunique()} rebalance={h}d")

    rdates, per_date = build_sleeve_weights(panel, signals, args.long_short_pct,
                                            args.min_names, h)

    # Standalone net series for every scanned signal (also the DSR trial set).
    standalone = {s: returns_from_combiner(rdates, per_date, (lambda s_: (lambda rec: rec[s_]))(s),
                                           args.cost_bps) for s in signals}

    def split(df):
        return (df.loc[df["date"] <= val_end], df.loc[df["date"] > val_end])

    # Inverse-vol sleeve weights from DISCOVERY only (no look-ahead).
    alpha = {}
    for s in BOOK_SLEEVES:
        disc, _ = split(standalone[s])
        v = disc["net"].std(ddof=1)
        alpha[s] = 1.0 / (v + 1e-12)
    asum = sum(alpha.values())
    alpha = {s: alpha[s] / asum for s in BOOK_SLEEVES}
    equal = {s: 1.0 / len(BOOK_SLEEVES) for s in BOOK_SLEEVES}

    def combine(weights):
        def _c(rec):
            parts = [weights[s] * rec[s] for s in BOOK_SLEEVES
                     if s in rec and not rec[s].empty]
            return pd.concat(parts).groupby(level=0).sum() if parts else pd.Series(dtype=float)
        return _c

    books = {
        "momentum_only": standalone["mom_252d_skip_21d"],
        "reversal_only": standalone["ret_5d"],
        "combined_inverse_vol": returns_from_combiner(rdates, per_date, combine(alpha), args.cost_bps),
        "combined_equal": returns_from_combiner(rdates, per_date, combine(equal), args.cost_bps),
    }

    # Performance table (discovery + test).
    perf_rows = []
    for name, df in books.items():
        for split_name, part in zip(("discovery", "test"), split(df)):
            perf_rows.append({"book": name, "split": split_name, **summarize(part, ppy)})
    perf = pd.DataFrame(perf_rows)
    perf.to_csv(out_dir / "book_performance.csv", index=False)

    # Sleeve correlation (net returns, full sample).
    sleeve_net = pd.DataFrame({
        s: standalone[s].set_index("date")["net"] for s in BOOK_SLEEVES
    }).dropna()
    corr = sleeve_net.corr()
    corr.to_csv(out_dir / "sleeve_correlation.csv")

    # DSR for the combined inverse-vol book on the hold-out.
    _, comb_test = split(books["combined_inverse_vol"])
    trial_sr = [per_obs_sharpe(split(standalone[s])[1]["net"].to_numpy(dtype=np.float64))
                for s in signals]
    dsr = deflated_sharpe(comb_test["net"].to_numpy(dtype=np.float64), trial_sr)
    lo, hi = block_bootstrap_sharpe_ci(comb_test["net"].to_numpy(dtype=np.float64), ppy)
    dsr.update({"boot_sharpe_ci_low": lo, "boot_sharpe_ci_high": hi,
                "alpha_momentum": alpha["mom_252d_skip_21d"], "alpha_reversal": alpha["ret_5d"]})
    pd.DataFrame([dsr]).to_csv(out_dir / "dsr_combined.csv", index=False)

    # Console output.
    try:
        from tabulate import tabulate
        print("\n=== Book performance (net of {:.0f}bps, rebalance {}d) ===".format(args.cost_bps, h))
        show = perf[["book", "split", "sharpe_net", "ann_ret_net", "max_dd_net", "avg_turnover", "periods"]]
        print(tabulate(show, headers="keys", tablefmt="github", floatfmt=".3f", showindex=False))
        print("\n=== Sleeve net-return correlation (full sample) ===")
        print(tabulate(corr, headers="keys", tablefmt="github", floatfmt=".3f"))
        print("\n=== Combined book hold-out (2022+) multiple-testing check ===")
        print(tabulate(pd.DataFrame([dsr]).T.reset_index(), headers=["metric", "value"],
                       tablefmt="github", floatfmt=".4f", showindex=False))
    except Exception:
        print(perf.to_string(index=False)); print(corr.to_string()); print(dsr)

    # Equity curves.
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 5))
        for name in ["momentum_only", "reversal_only", "combined_inverse_vol"]:
            d = books[name].copy()
            d["equity"] = (1.0 + d["net"]).cumprod()
            ax.plot(pd.to_datetime(d["date"]), d["equity"], label=name)
        ax.axvline(val_end, color="grey", ls="--", lw=1, label="hold-out start")
        ax.set_yscale("log"); ax.set_ylabel("net equity (log)"); ax.legend()
        ax.set_title(f"Factor sleeve book ({args.target_family}, {h}d rebalance, net {args.cost_bps:.0f}bps)")
        fig.tight_layout()
        fig.savefig(out_dir / "sleeve_book_equity.png", dpi=150)
        print(f"\nEquity curve -> {out_dir / 'sleeve_book_equity.png'}")
    except Exception as exc:
        print(f"(equity plot skipped: {exc})")

    print(f"\nWrote outputs under {out_dir}/")


if __name__ == "__main__":
    main()
