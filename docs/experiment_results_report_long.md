# S&P 500 Relative Return Modeling Experiment Report

- Experiment: `target_grid_core_long_refine`
- Completed run directories: 208
- Completed targets: 16/16
- Target grid: 4 horizons (30D, 40D, 50D, 60D) x 4 target definitions (`excess_market`, `excess_sector`, `rank`, `ret`).
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

按 test ICIR 看，Ridge 在 16/16 个已完成 target-model 对照中超过 baseline，win rate = 100.0%。下面是 Ridge 相对 baseline 的 test delta：
| target_col                   |   delta_icir |   delta_sharpe |   model_test_ic |   baseline_test_ic |
|:-----------------------------|-------------:|---------------:|----------------:|-------------------:|
| target_excess_market_fwd_30d |       1.4348 |         0.8595 |          0.0385 |             0.0226 |
| target_excess_market_fwd_40d |       2.0445 |         1.2639 |          0.0490 |             0.0251 |
| target_excess_market_fwd_50d |       1.4554 |         1.1921 |          0.0490 |             0.0302 |
| target_excess_market_fwd_60d |       0.8402 |         1.0890 |          0.0459 |             0.0328 |
| target_excess_sector_fwd_30d |       1.5604 |         1.0928 |          0.0284 |             0.0143 |
| target_excess_sector_fwd_40d |       2.0801 |         1.5133 |          0.0351 |             0.0151 |
| target_excess_sector_fwd_50d |       1.3497 |         1.4496 |          0.0344 |             0.0194 |
| target_excess_sector_fwd_60d |       0.7146 |         1.4294 |          0.0331 |             0.0221 |
| target_rank_fwd_30d          |       1.6676 |         0.6640 |          0.0393 |             0.0226 |
| target_rank_fwd_40d          |       2.5731 |         1.0653 |          0.0538 |             0.0251 |
| target_rank_fwd_50d          |       1.9569 |         0.9435 |          0.0539 |             0.0302 |
| target_rank_fwd_60d          |       1.4303 |         0.8662 |          0.0519 |             0.0328 |
| target_ret_fwd_30d           |       1.8496 |         0.7377 |          0.0431 |             0.0226 |
| target_ret_fwd_40d           |       2.0192 |         0.9819 |          0.0482 |             0.0251 |
| target_ret_fwd_50d           |       1.3485 |         0.8869 |          0.0466 |             0.0302 |
| target_ret_fwd_60d           |       0.6248 |         0.6714 |          0.0425 |             0.0328 |

## 8. XGBoost 是否比 Ridge 好？

按 test ICIR 看，XGBoost 在 15/16 个 target 上超过 Ridge。是否“更好”不只看 ICIR，还要看 Sharpe、turnover 和稳定性；树模型通常 turnover 更高，因此交易成本敏感。
| target_col                   |   xgb_minus_ridge_test_icir |   xgb_minus_ridge_test_sharpe |
|:-----------------------------|----------------------------:|------------------------------:|
| target_excess_market_fwd_30d |                      0.6963 |                        0.3214 |
| target_excess_market_fwd_40d |                      1.4712 |                        0.3285 |
| target_excess_market_fwd_50d |                      0.9454 |                        0.0122 |
| target_excess_market_fwd_60d |                      1.4966 |                        0.7604 |
| target_excess_sector_fwd_30d |                      0.8040 |                        0.2663 |
| target_excess_sector_fwd_40d |                      1.0059 |                       -0.3306 |
| target_excess_sector_fwd_50d |                      2.9642 |                        0.1110 |
| target_excess_sector_fwd_60d |                      2.7337 |                        0.3943 |
| target_rank_fwd_30d          |                      0.9639 |                        0.3930 |
| target_rank_fwd_40d          |                      0.8377 |                        0.1612 |
| target_rank_fwd_50d          |                      1.3000 |                        0.4802 |
| target_rank_fwd_60d          |                      1.3972 |                        0.5085 |
| target_ret_fwd_30d           |                     -0.1853 |                       -0.2592 |
| target_ret_fwd_40d           |                      0.6775 |                        0.0565 |
| target_ret_fwd_50d           |                      1.9465 |                        0.7581 |
| target_ret_fwd_60d           |                      2.3580 |                        1.0990 |

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
|        30 | excess_market   | lightgbm | arc_refine_more_regularized |     7.4486 |    0.0453 |      4.5024 |        2.7305 |            0.7975 |          0.3727 |
|        30 | excess_market   | ridge    | ridge_ref                   |     2.6985 |    0.0385 |      3.3396 |        2.3072 |            0.6959 |          0.3586 |
|        30 | excess_market   | xgboost  | arc_refine_more_regularized |     7.2773 |    0.0449 |      4.0359 |        2.6287 |            0.8231 |          0.3597 |
|        30 | excess_sector   | lightgbm | lgbm_deeper                 |     8.7790 |    0.0183 |      2.8340 |        1.3551 |            0.2588 |          0.4255 |
|        30 | excess_sector   | ridge    | ridge_ref                   |     5.3286 |    0.0284 |      3.0587 |        2.5405 |            0.6690 |          0.3845 |
|        30 | excess_sector   | xgboost  | arc_refine_more_regularized |     8.4774 |    0.0246 |      3.8627 |        2.8068 |            0.5811 |          0.3834 |
|        30 | rank            | lightgbm | arc_refine_more_regularized |     7.2668 |    0.0400 |      4.4183 |        2.5143 |            0.6424 |          0.4068 |
|        30 | rank            | ridge    | ridge_ref                   |     2.7075 |    0.0393 |      3.5724 |        2.1117 |            0.5824 |          0.3584 |
|        30 | rank            | xgboost  | arc_refine_lower_lr         |     7.5139 |    0.0407 |      4.5364 |        2.5048 |            0.6325 |          0.4068 |
|        30 | ret             | lightgbm | arc_refine_more_regularized |     6.6788 |    0.0379 |      3.6000 |        2.2957 |            0.6047 |          0.4239 |
|        30 | ret             | ridge    | ridge_ref                   |     3.3163 |    0.0431 |      3.7543 |        2.1854 |            0.5783 |          0.3863 |
|        30 | ret             | xgboost  | arc_refine_more_regularized |     7.2368 |    0.0358 |      3.5690 |        1.9263 |            0.5010 |          0.4315 |
|        40 | excess_market   | lightgbm | arc_refine_lower_lr         |     9.5600 |    0.0482 |      5.5021 |        3.3074 |            1.0260 |          0.3641 |
|        40 | excess_market   | ridge    | ridge_ref                   |     3.2219 |    0.0490 |      4.1890 |        2.9571 |            1.0043 |          0.3225 |
|        40 | excess_market   | xgboost  | arc_refine_more_capacity    |     9.6581 |    0.0504 |      5.6602 |        3.2857 |            1.0067 |          0.3655 |
|        40 | excess_sector   | lightgbm | arc_refine_lower_lr         |    12.4804 |    0.0331 |      5.5286 |        3.4635 |            0.7758 |          0.3669 |
|        40 | excess_sector   | ridge    | ridge_ref                   |     5.6739 |    0.0351 |      3.7191 |        3.2065 |            0.9600 |          0.3492 |
|        40 | excess_sector   | xgboost  | xgb_deeper                  |    12.8832 |    0.0279 |      4.7250 |        2.8759 |            0.6152 |          0.3796 |
|        40 | rank            | lightgbm | arc_refine_more_regularized |     8.8364 |    0.0478 |      5.4347 |        3.1220 |            0.9228 |          0.3886 |
|        40 | rank            | ridge    | ridge_ref                   |     3.1506 |    0.0538 |      4.7176 |        2.7586 |            0.9044 |          0.3303 |
|        40 | rank            | xgboost  | xgb_shallow_regularized     |     9.3989 |    0.0491 |      5.5553 |        2.9198 |            0.8702 |          0.3925 |
|        40 | ret             | lightgbm | arc_refine_more_regularized |     8.5235 |    0.0457 |      4.8326 |        3.0211 |            0.8597 |          0.3521 |
|        40 | ret             | ridge    | ridge_ref                   |     3.5176 |    0.0482 |      4.1637 |        2.6751 |            0.7848 |          0.3571 |
|        40 | ret             | xgboost  | arc_refine_more_regularized |     9.3298 |    0.0454 |      4.8412 |        2.7316 |            0.7642 |          0.3441 |
|        50 | excess_market   | lightgbm | arc_refine_more_regularized |     9.7535 |    0.0562 |      5.9118 |        3.7266 |            1.3577 |          0.3436 |
|        50 | excess_market   | ridge    | ridge_ref                   |     4.3044 |    0.0490 |      4.1555 |        3.2040 |            1.2212 |          0.3129 |
|        50 | excess_market   | xgboost  | arc_refine_more_capacity    |    10.0102 |    0.0407 |      5.1008 |        3.2162 |            0.9427 |          0.3938 |
|        50 | excess_sector   | lightgbm | arc_refine_more_capacity    |    13.1441 |    0.0320 |      5.9221 |        3.3935 |            0.7916 |          0.3866 |
|        50 | excess_sector   | ridge    | ridge_ref                   |     6.5203 |    0.0344 |      3.5969 |        3.4614 |            1.1677 |          0.3351 |
|        50 | excess_sector   | xgboost  | xgb_deeper                  |    13.6404 |    0.0359 |      6.5611 |        3.5724 |            0.8031 |          0.3659 |
|        50 | rank            | lightgbm | arc_refine_more_regularized |     9.9388 |    0.0544 |      6.0000 |        3.4592 |            1.1464 |          0.3764 |
|        50 | rank            | ridge    | ridge_ref                   |     4.0220 |    0.0539 |      4.6569 |        2.9554 |            1.0638 |          0.3287 |
|        50 | rank            | xgboost  | arc_refine_lower_lr         |    10.3671 |    0.0546 |      5.9570 |        3.4356 |            1.1190 |          0.3742 |
|        50 | ret             | lightgbm | arc_refine_more_regularized |     8.0707 |    0.0483 |      5.3594 |        3.4705 |            1.0836 |          0.3591 |
|        50 | ret             | ridge    | ridge_ref                   |     4.3618 |    0.0466 |      4.0486 |        2.8987 |            0.9752 |          0.3395 |
|        50 | ret             | xgboost  | arc_refine_more_regularized |     8.3328 |    0.0531 |      5.9951 |        3.6568 |            1.1455 |          0.3541 |
|        60 | excess_market   | lightgbm | arc_refine_more_regularized |    10.4892 |    0.0551 |      5.8998 |        4.1521 |            1.6545 |          0.3144 |
|        60 | excess_market   | ridge    | ridge_ref                   |     5.1445 |    0.0459 |      3.9437 |        3.3727 |            1.4418 |          0.2837 |
|        60 | excess_market   | xgboost  | arc_refine_more_regularized |     9.6510 |    0.0455 |      5.4403 |        4.1331 |            1.4202 |          0.3655 |
|        60 | excess_sector   | lightgbm | lgbm_balanced               |    13.6991 |    0.0355 |      6.4645 |        4.3554 |            1.0871 |          0.3660 |
|        60 | excess_sector   | ridge    | ridge_ref                   |     7.2231 |    0.0331 |      3.4583 |        3.7131 |            1.4182 |          0.3005 |
|        60 | excess_sector   | xgboost  | arc_refine_more_capacity    |    13.9782 |    0.0344 |      6.1920 |        4.1073 |            1.0001 |          0.3593 |
|        60 | rank            | lightgbm | arc_refine_more_regularized |    10.5115 |    0.0524 |      5.8601 |        3.7806 |            1.3563 |          0.3390 |
|        60 | rank            | ridge    | ridge_ref                   |     4.7017 |    0.0519 |      4.5337 |        3.1499 |            1.2685 |          0.2915 |
|        60 | rank            | xgboost  | xgb_shallow_regularized     |    10.7792 |    0.0522 |      5.9309 |        3.6583 |            1.2836 |          0.3368 |
|        60 | ret             | lightgbm | arc_refine_more_capacity    |     8.9784 |    0.0452 |      6.2191 |        3.8884 |            1.1987 |          0.4316 |
|        60 | ret             | ridge    | ridge_ref                   |     5.6604 |    0.0425 |      3.7283 |        2.9550 |            1.1078 |          0.3090 |
|        60 | ret             | xgboost  | xgb_balanced                |     8.5635 |    0.0451 |      6.0863 |        4.0540 |            1.2335 |          0.4095 |

## 11. Winner Count By Test ICIR

| target_col                   | winner   | metric    |   value |
|:-----------------------------|:---------|:----------|--------:|
| target_excess_market_fwd_30d | lightgbm | test_icir |  4.5024 |
| target_excess_market_fwd_40d | xgboost  | test_icir |  5.6602 |
| target_excess_market_fwd_50d | lightgbm | test_icir |  5.9118 |
| target_excess_market_fwd_60d | lightgbm | test_icir |  5.8998 |
| target_excess_sector_fwd_30d | xgboost  | test_icir |  3.8627 |
| target_excess_sector_fwd_40d | lightgbm | test_icir |  5.5286 |
| target_excess_sector_fwd_50d | xgboost  | test_icir |  6.5611 |
| target_excess_sector_fwd_60d | lightgbm | test_icir |  6.4645 |
| target_rank_fwd_30d          | xgboost  | test_icir |  4.5364 |
| target_rank_fwd_40d          | xgboost  | test_icir |  5.5553 |
| target_rank_fwd_50d          | lightgbm | test_icir |  6.0000 |
| target_rank_fwd_60d          | xgboost  | test_icir |  5.9309 |
| target_ret_fwd_30d           | ridge    | test_icir |  3.7543 |
| target_ret_fwd_40d           | xgboost  | test_icir |  4.8412 |
| target_ret_fwd_50d           | xgboost  | test_icir |  5.9951 |
| target_ret_fwd_60d           | lightgbm | test_icir |  6.2191 |

| model    |   wins |
|:---------|-------:|
| xgboost  |      8 |
| lightgbm |      7 |
| ridge    |      1 |

## 12. Best Hyperparameters

|   horizon | target_family   | model    |   val_icir |   n_estimators |   learning_rate |   max_depth |   num_leaves |   min_child_samples |   min_child_weight |   subsample |   colsample_bytree |   reg_lambda |
|----------:|:----------------|:---------|-----------:|---------------:|----------------:|------------:|-------------:|--------------------:|-------------------:|------------:|-------------------:|-------------:|
|        30 | excess_market   | lightgbm |     7.4486 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        30 | excess_market   | ridge    |     2.6985 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        30 | excess_market   | xgboost  |     7.2773 |            500 |          0.0250 |           2 |           63 |                 100 |           136.0000 |      0.7500 |             0.6500 |      34.0000 |
|        30 | excess_sector   | lightgbm |     8.7790 |            300 |          0.0500 |           6 |           63 |                 180 |            20.0000 |      0.7500 |             0.8500 |       8.0000 |
|        30 | excess_sector   | ridge    |     5.3286 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        30 | excess_sector   | xgboost  |     8.4774 |            300 |          0.0500 |           4 |           63 |                 100 |            51.0000 |      0.7000 |             0.8000 |      13.6000 |
|        30 | rank            | lightgbm |     7.2668 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        30 | rank            | ridge    |     2.7075 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        30 | rank            | xgboost  |     7.5139 |            750 |          0.0163 |           3 |           63 |                 100 |            80.0000 |      0.8000 |             0.7000 |      20.0000 |
|        30 | ret             | lightgbm |     6.6788 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        30 | ret             | ridge    |     3.3163 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        30 | ret             | xgboost  |     7.2368 |            500 |          0.0250 |           2 |           63 |                 100 |           136.0000 |      0.7500 |             0.6500 |      34.0000 |
|        40 | excess_market   | lightgbm |     9.5600 |            750 |          0.0163 |           4 |           15 |                 400 |            20.0000 |      0.8000 |             0.7000 |      20.0000 |
|        40 | excess_market   | ridge    |     3.2219 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        40 | excess_market   | xgboost  |     9.6581 |            425 |          0.0287 |           4 |           63 |                 100 |            52.0000 |      0.8500 |             0.7500 |      15.0000 |
|        40 | excess_sector   | lightgbm |    12.4804 |            525 |          0.0260 |           5 |           31 |                 250 |            20.0000 |      0.7500 |             0.7500 |      10.0000 |
|        40 | excess_sector   | ridge    |     5.6739 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        40 | excess_sector   | xgboost  |    12.8832 |            300 |          0.0500 |           5 |           63 |                 100 |            30.0000 |      0.7500 |             0.8500 |       8.0000 |
|        40 | rank            | lightgbm |     8.8364 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        40 | rank            | ridge    |     3.1506 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        40 | rank            | xgboost  |     9.3989 |            500 |          0.0250 |           3 |           63 |                 100 |            80.0000 |      0.8000 |             0.7000 |      20.0000 |
|        40 | ret             | lightgbm |     8.5235 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        40 | ret             | ridge    |     3.5176 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        40 | ret             | xgboost  |     9.3298 |            500 |          0.0250 |           2 |           63 |                 100 |           136.0000 |      0.7500 |             0.6500 |      34.0000 |
|        50 | excess_market   | lightgbm |     9.7535 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        50 | excess_market   | ridge    |     4.3044 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        50 | excess_market   | xgboost  |    10.0102 |            297 |          0.0460 |           5 |           63 |                 100 |            26.0000 |      0.8000 |             0.8000 |       7.5000 |
|        50 | excess_sector   | lightgbm |    13.1441 |            297 |          0.0460 |           6 |           49 |                 175 |            20.0000 |      0.8000 |             0.8000 |       7.5000 |
|        50 | excess_sector   | ridge    |     6.5203 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        50 | excess_sector   | xgboost  |    13.6404 |            300 |          0.0500 |           5 |           63 |                 100 |            30.0000 |      0.7500 |             0.8500 |       8.0000 |
|        50 | rank            | lightgbm |     9.9388 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        50 | rank            | ridge    |     4.0220 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        50 | rank            | xgboost  |    10.3671 |            750 |          0.0163 |           3 |           63 |                 100 |            80.0000 |      0.8000 |             0.7000 |      20.0000 |
|        50 | ret             | lightgbm |     8.0707 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        50 | ret             | ridge    |     4.3618 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        50 | ret             | xgboost  |     8.3328 |            350 |          0.0400 |           3 |           63 |                 100 |            68.0000 |      0.7000 |             0.7000 |      17.0000 |
|        60 | excess_market   | lightgbm |    10.4892 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        60 | excess_market   | ridge    |     5.1445 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        60 | excess_market   | xgboost  |     9.6510 |            300 |          0.0500 |           4 |           63 |                 100 |            51.0000 |      0.7000 |             0.8000 |      13.6000 |
|        60 | excess_sector   | lightgbm |    13.6991 |            350 |          0.0400 |           5 |           31 |                 250 |            20.0000 |      0.7500 |             0.7500 |      10.0000 |
|        60 | excess_sector   | ridge    |     7.2231 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        60 | excess_sector   | xgboost  |    13.9782 |            297 |          0.0460 |           5 |           63 |                 100 |            26.0000 |      0.8000 |             0.8000 |       7.5000 |
|        60 | rank            | lightgbm |    10.5115 |            500 |          0.0250 |           3 |            7 |                 600 |            20.0000 |      0.7500 |             0.6500 |      34.0000 |
|        60 | rank            | ridge    |     4.7017 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        60 | rank            | xgboost  |    10.7792 |            500 |          0.0250 |           3 |           63 |                 100 |            80.0000 |      0.8000 |             0.7000 |      20.0000 |
|        60 | ret             | lightgbm |     8.9784 |            425 |          0.0287 |           5 |           31 |                 280 |            20.0000 |      0.8500 |             0.7500 |      15.0000 |
|        60 | ret             | ridge    |     5.6604 |            300 |          0.0500 |           4 |           63 |                 100 |            20.0000 |      0.8000 |             0.8000 |       5.0000 |
|        60 | ret             | xgboost  |     8.5635 |            350 |          0.0400 |           4 |           63 |                 100 |            40.0000 |      0.7500 |             0.7500 |      10.0000 |

## 13. Files

- Full metrics: `output/model_pipeline/target_grid_core_long_refine_all_metrics.csv`
- Best metrics: `output/model_pipeline/target_grid_core_long_refine_best_metrics.csv`
- Best hyperparameters: `output/model_pipeline/target_grid_core_long_refine_best_params.csv`
- Diagnostics: `output/diagnostics/diagnostics_report.md`
