# Walk-Forward Horizon / Model Comparison

Selection rule: best model per (family, horizon) by across-fold mean validation rank ICIR (overlap-adjusted). Hold-out metrics are reported only after selection. `holdout_icir_raw` is the naive overlapping value and is shown only to document the inflation that the adjusted ICIR fixes.

## Best model per family and horizon

| family | horizon | model | n_folds | val_mean_icir | val_mean_sharpe | holdout_ic | holdout_icir | holdout_icir_raw | holdout_sharpe | holdout_ann_return | holdout_max_dd | holdout_turnover | holdout_suspect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| excess_market | 1 | mlp | 7 | 0.9241 | 0.0055 | 0.0052 | 0.5346 | 0.5346 | -0.6869 | -0.0676 | -0.3011 | 0.5385 | False |
| excess_market | 5 | mlp | 7 | 0.9870 | 0.5435 | 0.0088 | 0.3789 | 0.8945 | 0.0277 | 0.0026 | -0.1958 | 0.5749 | False |
| excess_market | 20 | lightgbm | 7 | 0.9890 | 1.0689 | 0.0280 | 0.3938 | 2.4671 | 0.4851 | 0.0551 | -0.1064 | 0.6411 | False |
| excess_market | 30 | mlp | 7 | 0.8302 | -0.0871 | 0.0089 | 0.1531 | 0.9596 | 0.2960 | 0.0342 | -0.0994 | 0.7354 | False |
| excess_sector | 1 | mlp | 7 | 1.5531 | -0.1454 | 0.0089 | 1.0827 | 1.0827 | -0.2152 | -0.0186 | -0.1596 | 0.4911 | False |
| excess_sector | 5 | mlp | 7 | 1.1469 | 0.6791 | 0.0126 | 0.7341 | 1.7155 | 0.1661 | 0.0123 | -0.1770 | 0.5891 | False |
| excess_sector | 20 | lightgbm | 7 | 0.7381 | 0.3675 | 0.0208 | 0.4824 | 2.4205 | 0.6470 | 0.0534 | -0.0706 | 0.6570 | False |
| excess_sector | 30 | mlp | 7 | 0.4882 | 0.6531 | 0.0271 | 0.9172 | 3.8827 | 0.6911 | 0.0653 | -0.0611 | 0.6992 | False |

## All runs

| family | horizon | model | n_folds | val_mean_icir | val_mean_sharpe | holdout_ic | holdout_icir | holdout_icir_raw | holdout_sharpe | holdout_ann_return | holdout_max_dd | holdout_turnover | holdout_suspect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| excess_market | 1 | lightgbm | 7 | 0.7362 | 0.2989 | 0.0010 | 0.0855 | 0.0855 | -0.3482 | -0.0359 | -0.2111 | 0.4027 | False |
| excess_market | 1 | mlp | 7 | 0.9241 | 0.0055 | 0.0052 | 0.5346 | 0.5346 | -0.6869 | -0.0676 | -0.3011 | 0.5385 | False |
| excess_market | 1 | ridge | 7 | 0.6683 | 0.2603 | 0.0050 | 0.4017 | 0.4017 | 0.2093 | 0.0266 | -0.1450 | 0.4554 | False |
| excess_market | 1 | xgboost | 7 | 0.6685 | 0.3166 | 0.0001 | 0.0086 | 0.0086 | -0.4833 | -0.0508 | -0.2578 | 0.3704 | False |
| excess_market | 5 | lightgbm | 7 | 0.6908 | 0.6069 | 0.0040 | 0.0472 | 0.3897 | 0.0382 | 0.0035 | -0.1905 | 0.5299 | False |
| excess_market | 5 | mlp | 7 | 0.9870 | 0.5435 | 0.0088 | 0.3789 | 0.8945 | 0.0277 | 0.0026 | -0.1958 | 0.5749 | False |
| excess_market | 5 | ridge | 7 | 0.4169 | 0.4005 | 0.0134 | 0.4065 | 1.1147 | 0.7638 | 0.0837 | -0.1386 | 0.6480 | False |
| excess_market | 5 | xgboost | 7 | 0.6077 | 0.5605 | 0.0042 | 0.1016 | 0.4039 | -0.1120 | -0.0103 | -0.2079 | 0.5310 | False |
| excess_market | 20 | lightgbm | 7 | 0.9890 | 1.0689 | 0.0280 | 0.3938 | 2.4671 | 0.4851 | 0.0551 | -0.1064 | 0.6411 | False |
| excess_market | 20 | mlp | 7 | 0.6924 | 0.9022 | -0.0114 | -0.6586 | -1.2597 | -1.0850 | -0.1016 | -0.3506 | 0.7191 | False |
| excess_market | 20 | ridge | 7 | 0.1813 | 0.2262 | 0.0288 | 0.5419 | 2.2698 | 0.7551 | 0.0981 | -0.0868 | 0.6053 | False |
| excess_market | 20 | xgboost | 7 | 0.8977 | 0.8008 | 0.0351 | 0.5076 | 3.0236 | 0.6838 | 0.0792 | -0.1005 | 0.6392 | False |
| excess_market | 30 | lightgbm | 7 | 0.2202 | 0.3284 | 0.0556 | 0.6445 | 4.7123 | 0.8621 | 0.1272 | -0.1090 | 0.6205 | False |
| excess_market | 30 | mlp | 7 | 0.8302 | -0.0871 | 0.0089 | 0.1531 | 0.9596 | 0.2960 | 0.0342 | -0.0994 | 0.7354 | False |
| excess_market | 30 | ridge | 7 | -0.5721 | -0.0990 | 0.0436 | 0.7706 | 3.5360 | 1.1292 | 0.1488 | -0.1077 | 0.6450 | False |
| excess_market | 30 | xgboost | 7 | 0.4648 | 0.3288 | 0.0550 | 0.6350 | 4.5266 | 0.8254 | 0.1216 | -0.1211 | 0.5713 | False |
| excess_market | 90 | lightgbm | 7 |  |  | 0.0953 | 0.9613 | 9.9236 | 1.7412 | 0.2395 | -0.0200 | 0.6665 | False |
| excess_market | 90 | mlp | 7 |  |  | 0.0414 | 0.6770 | 6.5130 | 0.7431 | 0.0917 | -0.0424 | 0.7501 | False |
| excess_market | 90 | ridge | 7 |  |  | 0.0739 | 0.6274 | 6.4043 | 1.2757 | 0.2068 | -0.0514 | 0.6489 | False |
| excess_market | 90 | xgboost | 7 |  |  | 0.0991 | 1.1012 | 10.8225 | 1.7349 | 0.2501 | -0.0163 | 0.6370 | False |
| excess_sector | 1 | lightgbm | 7 | 0.6490 | 0.2391 | 0.0005 | 0.0603 | 0.0603 | -0.2036 | -0.0178 | -0.1867 | 0.4125 | False |
| excess_sector | 1 | mlp | 7 | 1.5531 | -0.1454 | 0.0089 | 1.0827 | 1.0827 | -0.2152 | -0.0186 | -0.1596 | 0.4911 | False |
| excess_sector | 1 | ridge | 7 | 0.6446 | 0.0307 | 0.0036 | 0.3486 | 0.3486 | 0.1952 | 0.0219 | -0.1416 | 0.4537 | False |
| excess_sector | 1 | xgboost | 7 | 0.6354 | 0.2381 | 0.0017 | 0.1729 | 0.1729 | -0.3402 | -0.0326 | -0.2691 | 0.3608 | False |
| excess_sector | 5 | lightgbm | 7 | 0.6101 | 0.4271 | 0.0090 | 0.1977 | 1.1659 | 0.2363 | 0.0169 | -0.1007 | 0.5255 | False |
| excess_sector | 5 | mlp | 7 | 1.1469 | 0.6791 | 0.0126 | 0.7341 | 1.7155 | 0.1661 | 0.0123 | -0.1770 | 0.5891 | False |
| excess_sector | 5 | ridge | 7 | 0.5951 | 0.3690 | 0.0097 | 0.3999 | 0.9943 | 0.5342 | 0.0507 | -0.1135 | 0.6446 | False |
| excess_sector | 5 | xgboost | 7 | 0.6261 | 0.4859 | 0.0051 | 0.0354 | 0.6369 | -0.0367 | -0.0027 | -0.1566 | 0.5179 | False |
| excess_sector | 20 | lightgbm | 7 | 0.7381 | 0.3675 | 0.0208 | 0.4824 | 2.4205 | 0.6470 | 0.0534 | -0.0706 | 0.6570 | False |
| excess_sector | 20 | mlp | 7 | 0.5703 | 0.1349 | 0.0171 | 0.1438 | 2.5942 | -0.5442 | -0.0401 | -0.2546 | 0.7132 | False |
| excess_sector | 20 | ridge | 7 | -0.1878 | 0.2263 | 0.0174 | 0.3419 | 1.6555 | 0.8271 | 0.0904 | -0.0627 | 0.6031 | False |
| excess_sector | 20 | xgboost | 7 | 0.6195 | 0.2722 | 0.0216 | 0.6485 | 2.6172 | 0.8455 | 0.0674 | -0.0596 | 0.6491 | False |
| excess_sector | 30 | lightgbm | 7 | 0.0804 | 0.1633 | 0.0362 | 0.8020 | 4.3380 | 1.2265 | 0.1295 | -0.0816 | 0.6307 | False |
| excess_sector | 30 | mlp | 7 | 0.4882 | 0.6531 | 0.0271 | 0.9172 | 3.8827 | 0.6911 | 0.0653 | -0.0611 | 0.6992 | False |
| excess_sector | 30 | ridge | 7 | -0.5521 | -0.1346 | 0.0260 | 0.3705 | 2.5126 | 1.1686 | 0.1276 | -0.0751 | 0.6611 | False |
| excess_sector | 30 | xgboost | 7 | -0.0182 | -0.0489 | 0.0323 | 0.7385 | 3.7959 | 1.2129 | 0.1315 | -0.0702 | 0.6253 | False |
| excess_sector | 90 | lightgbm | 7 |  |  | 0.0622 | 1.2727 | 8.6251 | 1.4508 | 0.1725 | -0.0172 | 0.6673 | False |
| excess_sector | 90 | mlp | 7 |  |  | 0.0361 | 0.3731 | 7.8692 | 0.1103 | 0.0126 | -0.1630 | 0.7331 | False |
| excess_sector | 90 | ridge | 7 |  |  | 0.0488 | 0.5929 | 4.9404 | 1.1982 | 0.1734 | -0.0376 | 0.6215 | False |
| excess_sector | 90 | xgboost | 7 |  |  | 0.0582 | 1.1715 | 7.9373 | 1.6158 | 0.1701 | -0.0098 | 0.6589 | False |

