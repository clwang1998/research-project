# 5d Momentum Traded-Horizon IC Split

Generated for cycle 20 with:

```bash
python3 scripts/build_momentum_ic_robustness.py \
  --target-col target_excess_sector_fwd_5d \
  --return-col target_ret_fwd_5d \
  --nw-lags 5 21 \
  --block-length 5 \
  --out-dir report/artifacts/momentum_ic_traded_horizons_5d_split
```

This focused diagnostic uses the existing feature and target parquet files and
does not train or select a model. It reports the 12--1 momentum Rank IC for the
5-day traded sector-relative target separately for the 2008--2021 discovery
period and the 2022--2026 hold-out.
