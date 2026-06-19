# S&P 500 Relative Return Modeling Experiment Report

- Experiment: `target_grid_core_refine`
- Completed run directories: 156
- Completed targets: 12/12
- Target grid: 3 horizons (1D, 5D, 20D) x 4 target definitions (`ret`, `excess_market`, `rank`, `excess_sector`).
- Models: Ridge reference, LightGBM, XGBoost.
- Selection rule: choose each model's best hyperparameter setting by validation ICIR; report test metrics afterward.

## 1. 数据是否干净？

数据整体可用：2,467,822 rows, 503 symbols, date range 2005-01-03 to 2026-06-16. 核心 OHLCV 列无缺失，date-symbol 重复数为 0。需要在报告里披露的小问题是：non-positive volume rows = 4234, OHLC inversion rows = 1。这些问题比例很低，对基于收益率和横截面排序的研究影响有限，但正式生产中应进一步清洗。

## 2. Raw Price 能不能预测？

raw close price level 的 1D future-return rank IC 接近 0 且为负，说明价格绝对水平本身不是稳定 alpha。这也支持不要用 raw price LSTM 直接预测价格路径。

| score           | target                      |   mean_rank_ic |   rank_ic_ir |   dates |
|:----------------|:----------------------------|---------------:|-------------:|--------:|
| raw_price_level | target_ret_fwd_1d           |        -0.0025 |      -0.3699 |    5396 |
| raw_price_level | target_excess_market_fwd_1d |        -0.0025 |      -0.3699 |    5396 |
| raw_price_level | target_rank_fwd_1d          |        -0.0025 |      -0.3699 |    5396 |
| raw_price_level | target_excess_sector_fwd_1d |        -0.0026 |      -0.4096 |    5396 |
| close_lag1      | target_ret_fwd_1d           |        -0.0022 |      -0.3174 |    5395 |
| close_lag1      | target_excess_market_fwd_1d |        -0.0022 |      -0.3174 |    5395 |
| close_lag1      | target_rank_fwd_1d          |        -0.0022 |      -0.3174 |    5395 |
| close_lag1      | target_excess_sector_fwd_1d |        -0.0023 |      -0.3599 |    5395 |

## 3. 为什么要用 Log Return？

log return 和 simple return 在日频上数值接近，但 log return 可加。本数据中 simple-return std = 0.022093, log-return std = 0.022106, mean absolute difference = 0.00024397。5D log return 由 1D log return 求和与直接计算的最大误差只有 0.000000492437。因此 log return 更适合多期 horizon、滚动特征和风险统计。

## 4. 单股收益有没有自相关？

单股 1D return 的 lag-1 自相关均值为 -0.0403，接近 0 且略为负，说明直接用昨日收益预测明日同向收益并不强。但 absolute return 的 lag-1 自相关均值为 0.2406，lag-5 仍为 0.2093，说明波动状态比收益方向更有持续性。

## 5. 市场波动有没有聚集？

有。市场 absolute return lag-1 autocorr = 0.3306，20D realized volatility lag-1 autocorr = 0.9944。这说明 volatility clustering 非常明显，使用 volatility、drawdown、market-vol context features 是合理的。

## 6. 什么是 Baseline？

本实验的 baseline 是单因子横截面 momentum rank：默认使用 `cs_rank_mom_252d_skip_21d`。它不训练复杂模型，只按每个交易日的股票动量信号排序，然后同样做 rank IC、decile spread 和 long-short decile backtest。baseline 的作用是回答：复杂模型是否真的超过一个简单、可解释、常用的量化信号。

## 7. 简单模型能不能打败 Baseline？

按 test ICIR 看，Ridge 在 8/12 个已完成 target-model 对照中超过 baseline，win rate = 66.7%。下面是 Ridge 相对 baseline 的 test delta：
| target_col                   |   delta_icir |   delta_sharpe |   model_test_ic |   baseline_test_ic |
|:-----------------------------|-------------:|---------------:|----------------:|-------------------:|
| target_excess_market_fwd_1d  |      -0.3879 |         0.9331 |          0.0118 |             0.0205 |
| target_excess_market_fwd_20d |       0.5999 |         0.4365 |          0.0262 |             0.0195 |
| target_excess_market_fwd_5d  |      -0.0060 |        -0.1795 |          0.0156 |             0.0190 |
| target_excess_sector_fwd_1d  |      -0.3836 |         0.9081 |          0.0097 |             0.0162 |
| target_excess_sector_fwd_20d |       0.8832 |         0.5789 |          0.0216 |             0.0135 |
| target_excess_sector_fwd_5d  |       0.0866 |        -0.1072 |          0.0129 |             0.0143 |
| target_rank_fwd_1d           |       0.5509 |         1.1021 |          0.0207 |             0.0205 |
| target_rank_fwd_20d          |       0.7127 |         0.0821 |          0.0258 |             0.0195 |
| target_rank_fwd_5d           |       0.7279 |         0.0201 |          0.0225 |             0.0190 |
| target_ret_fwd_1d            |      -0.4711 |         0.7867 |          0.0101 |             0.0205 |
| target_ret_fwd_20d           |       1.1596 |         0.3678 |          0.0317 |             0.0195 |
| target_ret_fwd_5d            |       0.1962 |        -0.0967 |          0.0168 |             0.0190 |

## 8. XGBoost 是否比 Ridge 好？

按 test ICIR 看，XGBoost 在 10/12 个 target 上超过 Ridge。是否“更好”不只看 ICIR，还要看 Sharpe、turnover 和稳定性；树模型通常 turnover 更高，因此交易成本敏感。
| target_col                   |   xgb_minus_ridge_test_icir |   xgb_minus_ridge_test_sharpe |
|:-----------------------------|----------------------------:|------------------------------:|
| target_excess_market_fwd_1d  |                      0.2638 |                       -0.6598 |
| target_excess_market_fwd_20d |                      0.8515 |                        0.4262 |
| target_excess_market_fwd_5d  |                      0.2141 |                        0.0953 |
| target_excess_sector_fwd_1d  |                      0.4328 |                       -0.5434 |
| target_excess_sector_fwd_20d |                      0.6109 |                       -0.7890 |
| target_excess_sector_fwd_5d  |                      0.1448 |                        0.0498 |
| target_rank_fwd_1d           |                      0.0228 |                       -0.8195 |
| target_rank_fwd_20d          |                      0.7981 |                        0.4235 |
| target_rank_fwd_5d           |                      0.0946 |                        0.0811 |
| target_ret_fwd_1d            |                     -0.5489 |                       -0.7691 |
| target_ret_fwd_20d           |                      0.3787 |                       -0.1483 |
| target_ret_fwd_5d            |                     -0.6265 |                       -0.2395 |

## 9. LSTM 是否值得复杂度？

当前证据不支持优先做 raw-price LSTM。原因：

- 任务目标是横截面相对收益/排序，不是单只股票价格路径预测。
- raw price level 的 IC 接近 0，直接把价格序列喂给 LSTM 容易学到价格尺度、拆股/股票间不可比性和市场 regime，而不是可交易 alpha。
- 1D return 自相关弱，方向预测信号小；真正持续的是波动，不是收益方向。
- LSTM 需要更复杂的样本构造、序列截面融合、调参和防泄漏流程。对 10 页 take-home 报告来说，LightGBM/XGBoost + time split + long-short backtest 的性价比更高。

因此报告里可以写：LSTM 是未来扩展方向，但不是本项目主模型。

## 10. Best Model Results

|   horizon | target_family   | model    | grid_tag                    |   val_icir |   test_ic |   test_icir |   test_sharpe |   test_ann_return |   test_turnover |
|----------:|:----------------|:---------|:----------------------------|-----------:|----------:|------------:|--------------:|------------------:|----------------:|
|         1 | excess_market   | lightgbm | lgbm_balanced               |     2.7504 |    0.0111 |      1.2674 |        0.2204 |            0.0099 |          0.7127 |
|         1 | excess_market   | ridge    | ridge_ref                   |     0.9701 |    0.0118 |      0.9670 |        1.1052 |            0.0669 |          0.6004 |
|         1 | excess_market   | xgboost  | xgb_balanced                |     2.3402 |    0.0109 |      1.2308 |        0.4454 |            0.0190 |          0.6717 |
|         1 | excess_sector   | lightgbm | arc_refine_more_capacity    |     3.9009 |    0.0109 |      1.5515 |        0.3707 |            0.0126 |          0.7118 |
|         1 | excess_sector   | ridge    | ridge_ref                   |     1.7033 |    0.0097 |      0.9634 |        1.0801 |            0.0600 |          0.6033 |
|         1 | excess_sector   | xgboost  | xgb_deeper                  |     2.9754 |    0.0107 |      1.3962 |        0.5367 |            0.0200 |          0.6856 |
|         1 | rank            | lightgbm | lgbm_balanced               |     3.5625 |    0.0184 |      1.8076 |        0.5232 |            0.0249 |          0.7468 |
|         1 | rank            | ridge    | ridge_ref                   |     1.5385 |    0.0207 |      1.9058 |        1.2741 |            0.0611 |          0.6397 |
|         1 | rank            | xgboost  | xgb_balanced                |     3.4776 |    0.0197 |      1.9285 |        0.4546 |            0.0210 |          0.7409 |
|         1 | ret             | lightgbm | arc_refine_more_regularized |     1.9129 |    0.0054 |      0.5079 |        0.6955 |            0.0334 |          0.6920 |
|         1 | ret             | ridge    | ridge_ref                   |     0.9468 |    0.0101 |      0.8838 |        0.9588 |            0.0531 |          0.6329 |
|         1 | ret             | xgboost  | arc_refine_more_regularized |     2.0297 |    0.0034 |      0.3349 |        0.1897 |            0.0089 |          0.6868 |
|         5 | excess_market   | lightgbm | lgbm_balanced               |     3.1643 |    0.0124 |      1.3039 |        0.2007 |            0.0183 |          0.5870 |
|         5 | excess_market   | ridge    | ridge_ref                   |     1.9186 |    0.0156 |      1.3452 |        0.3648 |            0.0441 |          0.5548 |
|         5 | excess_market   | xgboost  | xgb_deeper                  |     3.5225 |    0.0149 |      1.5593 |        0.4601 |            0.0417 |          0.5851 |
|         5 | excess_sector   | lightgbm | arc_refine_more_capacity    |     4.5099 |    0.0137 |      1.8718 |        0.2520 |            0.0183 |          0.5855 |
|         5 | excess_sector   | ridge    | ridge_ref                   |     3.0468 |    0.0129 |      1.3589 |        0.4371 |            0.0471 |          0.5760 |
|         5 | excess_sector   | xgboost  | xgb_deeper                  |     4.2187 |    0.0118 |      1.5037 |        0.4869 |            0.0381 |          0.5732 |
|         5 | rank            | lightgbm | arc_refine_more_capacity    |     4.4315 |    0.0193 |      2.0141 |        0.5004 |            0.0451 |          0.6239 |
|         5 | rank            | ridge    | ridge_ref                   |     2.3218 |    0.0225 |      2.0791 |        0.5643 |            0.0585 |          0.5395 |
|         5 | rank            | xgboost  | arc_refine_more_regularized |     4.3694 |    0.0205 |      2.1737 |        0.6454 |            0.0569 |          0.6111 |
|         5 | ret             | lightgbm | arc_refine_more_regularized |     3.4158 |    0.0091 |      0.8740 |        0.1444 |            0.0133 |          0.7259 |
|         5 | ret             | ridge    | ridge_ref                   |     2.1118 |    0.0168 |      1.5474 |        0.4475 |            0.0499 |          0.5412 |
|         5 | ret             | xgboost  | xgb_shallow_regularized     |     3.7806 |    0.0096 |      0.9209 |        0.2081 |            0.0186 |          0.7103 |
|        20 | excess_market   | lightgbm | arc_refine_more_regularized |     6.3246 |    0.0302 |      3.1270 |        2.0956 |            0.4327 |          0.4206 |
|        20 | excess_market   | ridge    | ridge_ref                   |     2.0578 |    0.0262 |      2.2548 |        1.6480 |            0.3968 |          0.3650 |
|        20 | excess_market   | xgboost  | arc_refine_lower_lr         |     5.8016 |    0.0311 |      3.1064 |        2.0742 |            0.4408 |          0.4092 |
|        20 | excess_sector   | lightgbm | lgbm_balanced               |     8.2558 |    0.0196 |      2.9329 |        1.4442 |            0.2286 |          0.4255 |
|        20 | excess_sector   | ridge    | ridge_ref                   |     4.5416 |    0.0216 |      2.2750 |        1.7903 |            0.3807 |          0.3950 |
|        20 | excess_sector   | xgboost  | arc_refine_more_capacity    |     8.3593 |    0.0191 |      2.8859 |        1.0013 |            0.1539 |          0.4395 |
|        20 | rank            | lightgbm | arc_refine_more_regularized |     7.0006 |    0.0271 |      3.0361 |        1.8488 |            0.3494 |          0.4214 |
|        20 | rank            | ridge    | ridge_ref                   |     2.4020 |    0.0258 |      2.3677 |        1.2936 |            0.2842 |          0.3733 |
|        20 | rank            | xgboost  | xgb_shallow_regularized     |     6.9826 |    0.0281 |      3.1658 |        1.7171 |            0.3252 |          0.4278 |
|        20 | ret             | lightgbm | arc_refine_lower_lr         |     5.1617 |    0.0237 |      2.5726 |        1.3198 |            0.2488 |          0.4474 |
|        20 | ret             | ridge    | ridge_ref                   |     2.6115 |    0.0317 |      2.8146 |        1.5793 |            0.3478 |          0.3703 |
|        20 | ret             | xgboost  | arc_refine_more_regularized |     5.7409 |    0.0295 |      3.1933 |        1.4310 |            0.2738 |          0.3892 |

## 11. Winner Count By Test ICIR

| target_col                   | winner   | metric    |   value |
|:-----------------------------|:---------|:----------|--------:|
| target_excess_market_fwd_1d  | lightgbm | test_icir |  1.2674 |
| target_excess_market_fwd_20d | lightgbm | test_icir |  3.1270 |
| target_excess_market_fwd_5d  | xgboost  | test_icir |  1.5593 |
| target_excess_sector_fwd_1d  | lightgbm | test_icir |  1.5515 |
| target_excess_sector_fwd_20d | lightgbm | test_icir |  2.9329 |
| target_excess_sector_fwd_5d  | lightgbm | test_icir |  1.8718 |
| target_rank_fwd_1d           | xgboost  | test_icir |  1.9285 |
| target_rank_fwd_20d          | xgboost  | test_icir |  3.1658 |
| target_rank_fwd_5d           | xgboost  | test_icir |  2.1737 |
| target_ret_fwd_1d            | ridge    | test_icir |  0.8838 |
| target_ret_fwd_20d           | xgboost  | test_icir |  3.1933 |
| target_ret_fwd_5d            | ridge    | test_icir |  1.5474 |

| model    |   wins |
|:---------|-------:|
| lightgbm |      5 |
| xgboost  |      5 |
| ridge    |      2 |

## 12. Best Hyperparameters

|   horizon | target_family   | model    |   val_icir |   n_estimators |   learning_rate |   max_depth |   num_leaves |   min_child_samples |   min_child_weight |   subsample |   colsample_bytree |   reg_lambda |
|----------:|:----------------|:---------|-----------:|---------------:|----------------:|------------:|-------------:|--------------------:|-------------------:|------------:|-------------------:|-------------:|
|         1 | excess_market   | lightgbm |     2.7504 |            350 |          0.0400 |           5 |           31 |                 250 |            20.0000 |      0.7500 |             0.7500 |      10.0000 |
|         1 | excess_market   | ridge    |     0.9701 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|         1 | excess_market   | xgboost  |     2.3402 |            350 |          0.0400 |           4 |           63 |                 100 |            40.0000 |      0.7500 |             0.7500 |      10.0000 |
|         1 | excess_sector   | lightgbm |     3.9009 |            255 |          0.0575 |           7 |          100 |                 125 |            20.0000 |      0.8000 |             0.9000 |       6.0000 |
|         1 | excess_sector   | ridge    |     1.7033 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|         1 | excess_sector   | xgboost  |     2.9754 |            300 |          0.0500 |           5 |           63 |                 100 |            30.0000 |      0.7500 |             0.8500 |       8.0000 |
|         1 | rank            | lightgbm |     3.5625 |            350 |          0.0400 |           5 |           31 |                 250 |            20.0000 |      0.7500 |             0.7500 |      10.0000 |
|         1 | rank            | ridge    |     1.5385 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|         1 | rank            | xgboost  |     3.4776 |            350 |          0.0400 |           4 |           63 |                 100 |            40.0000 |      0.7500 |             0.7500 |      10.0000 |
|         1 | ret             | lightgbm |     1.9129 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|         1 | ret             | ridge    |     0.9468 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|         1 | ret             | xgboost  |     2.0297 |            500 |          0.0250 |           2 |           63 |                 100 |           136.0000 |      0.7500 |             0.6500 |      34.0000 |
|         5 | excess_market   | lightgbm |     3.1643 |            350 |          0.0400 |           5 |           31 |                 250 |            20.0000 |      0.7500 |             0.7500 |      10.0000 |
|         5 | excess_market   | ridge    |     1.9186 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|         5 | excess_market   | xgboost  |     3.5225 |            300 |          0.0500 |           5 |           63 |                 100 |            30.0000 |      0.7500 |             0.8500 |       8.0000 |
|         5 | excess_sector   | lightgbm |     4.5099 |            255 |          0.0575 |           7 |          100 |                 125 |            20.0000 |      0.8000 |             0.9000 |       6.0000 |
|         5 | excess_sector   | ridge    |     3.0468 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|         5 | excess_sector   | xgboost  |     4.2187 |            300 |          0.0500 |           5 |           63 |                 100 |            30.0000 |      0.7500 |             0.8500 |       8.0000 |
|         5 | rank            | lightgbm |     4.4315 |            425 |          0.0287 |           5 |           31 |                 280 |            20.0000 |      0.8500 |             0.7500 |      15.0000 |
|         5 | rank            | ridge    |     2.3218 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|         5 | rank            | xgboost  |     4.3694 |            300 |          0.0500 |           4 |           63 |                 100 |            51.0000 |      0.7000 |             0.8000 |      13.6000 |
|         5 | ret             | lightgbm |     3.4158 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|         5 | ret             | ridge    |     2.1118 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|         5 | ret             | xgboost  |     3.7806 |            500 |          0.0250 |           3 |           63 |                 100 |            80.0000 |      0.8000 |             0.7000 |      20.0000 |
|        20 | excess_market   | lightgbm |     6.3246 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        20 | excess_market   | ridge    |     2.0578 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        20 | excess_market   | xgboost  |     5.8016 |            750 |          0.0163 |           3 |           63 |                 100 |            80.0000 |      0.8000 |             0.7000 |      20.0000 |
|        20 | excess_sector   | lightgbm |     8.2558 |            350 |          0.0400 |           5 |           31 |                 250 |            20.0000 |      0.7500 |             0.7500 |      10.0000 |
|        20 | excess_sector   | ridge    |     4.5416 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        20 | excess_sector   | xgboost  |     8.3593 |            255 |          0.0575 |           6 |           63 |                 100 |            19.5000 |      0.8000 |             0.9000 |       6.0000 |
|        20 | rank            | lightgbm |     7.0006 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        20 | rank            | ridge    |     2.4020 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        20 | rank            | xgboost  |     6.9826 |            500 |          0.0250 |           3 |           63 |                 100 |            80.0000 |      0.8000 |             0.7000 |      20.0000 |
|        20 | ret             | lightgbm |     5.1617 |            750 |          0.0163 |           4 |           15 |                 400 |            20.0000 |      0.8000 |             0.7000 |      20.0000 |
|        20 | ret             | ridge    |     2.6115 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        20 | ret             | xgboost  |     5.7409 |            500 |          0.0250 |           2 |           63 |                 100 |           136.0000 |      0.7500 |             0.6500 |      34.0000 |

## 13. Files

- Full metrics: `output/model_pipeline/target_grid_core_refine_all_metrics.csv`
- Best metrics: `output/model_pipeline/target_grid_core_refine_best_metrics.csv`
- Best hyperparameters: `output/model_pipeline/target_grid_core_refine_best_params.csv`
- Diagnostics: `output/diagnostics/diagnostics_report.md`
