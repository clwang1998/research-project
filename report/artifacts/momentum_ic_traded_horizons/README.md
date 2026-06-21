# Momentum Traded-Horizon IC Robustness

Generated for cycle 8 with:

```bash
for h in 5 10 20 30; do
  python3 scripts/build_momentum_ic_robustness.py \
    --target-col target_excess_sector_fwd_${h}d \
    --return-col target_ret_fwd_${h}d \
    --nw-lags $h 21 \
    --block-length $h \
    --out-dir output/momentum_ic_traded_horizons/h${h}d
done
```

The compact CSV keeps the 2022+ hold-out rows for the 12--1 momentum signal at
the traded sector-relative horizons. This is a diagnostic over existing feature
and target parquet files; it does not train models or select horizons.
