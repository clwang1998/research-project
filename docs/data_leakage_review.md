# 数据泄漏审查报告：时序切分与标签净化

## 总结

对流水线的时序切分逻辑进行了全面审查。主切分方式**正确使用了硬时间边界**，没有随机 K-fold。但原实现存在标签跨边界、无 embargo、同日成交假设、以及报告层面用测试集挑赢家的问题。

当前主训练管线中记录的修复包括：精确 label purge、可配置 embargo、执行滞后一日，以及实验入口对 split 控制参数的透传。本轮补充的轻量 synthetic 验证见 `review-stage/20260620-1324-leakage-validation.md`。这些代码路径仍应在包含对应脚本 diff 和真实运行输出的 review scope 中复核后，才可作为最终无泄漏证据。报告层面的 horizon winner 选择口径和 refinement 搜索脚本是否完整继承这些约束，也需要在对应脚本纳入 review scope 后单独确认。

## 审查边界

本报告可作为 `scripts/run_model_pipeline.py` 和 `scripts/run_target_model_experiments.py` 相关时序净化逻辑的设计审查记录，但不能替代代码 diff、测试输出和运行配置审计。若后续报告、汇总脚本或 refinement 自动搜索引用这些结果，必须确认对应命令实际使用了相同的 `--execution-lag-days`、`--embargo-days` 和 target horizon 配置，并保留新的运行配置与 split audit。

---

## ✅ 正确的地方

### 1. 主切分使用硬时间边界

**文件**：`scripts/run_model_pipeline.py:293–301`

```python
def split_masks(df, train_end, val_end):
    return {
        "train": dates <= train_end_ts,                              # ≤ 2018-12-31
        "val":   (dates > train_end_ts) & (dates <= val_end_ts),    # 2019–2020
        "test":  dates > val_end_ts,                                 # > 2020-12-31
    }
```

三段切分按时间严格递进，未来不会漏入过去。没有使用随机 K-fold。

### 2. 截面特征在当天内计算，无跨期信息

`cs_rank_*`、`sector_rank_*`、`subind_rank_*`、`sector_peer_mean_*` 等全部通过 `df.groupby("date")` 计算，是纯粹的截面操作，不会引入跨期泄漏。

---

## ✅ 已修复问题一：标签跨边界（Label Leakage）

### 问题描述

**文件**：`scripts/make_features.py:1088`

```python
future_price = g[price_col].shift(-h)          # h ∈ [1, 5, 20, 30, ..., 120, 150]
df[f"target_ret_fwd_{h}d"] = future_price / df[price_col] - 1
```

每条训练样本的标签依赖未来 `h` 个交易日的价格。当 `train_end = 2018-12-31` 时：

| 目标 horizon | 受污染的训练样本 | label 使用的数据来源 |
|---|---|---|
| `target_ret_fwd_5d` | 训练集最后 ~5 行（≈ 2018-12-25 之后） | 2019 年 1 月价格（验证期） |
| `target_ret_fwd_20d` | 训练集最后 ~20 行（≈ 2018-12-05 之后） | 2019 年 1–2 月价格（验证期） |
| `target_ret_fwd_120d` | 训练集最后 ~120 行（≈ 2018-07 之后） | 2019 年价格（验证期） |

`split_masks` 中没有任何 purge 步骤，这部分泄漏静默发生。

用本地 `targets.parquet` 实证计数后，按 `train_end=2018-12-31`、`val_end=2020-12-31` 得到：

| horizon | train label 跨入验证期行数 | train 占比 | val label 跨入测试期行数 | val 占比 |
|---:|---:|---:|---:|---:|
| 1 | 478 | 0.024% | 490 | 0.200% |
| 5 | 2,390 | 0.119% | 2,450 | 1.001% |
| 20 | 9,556 | 0.477% | 9,791 | 4.000% |
| 60 | 28,636 | 1.428% | 29,311 | 11.974% |
| 120 | 57,240 | 2.855% | 58,536 | 23.912% |
| 150 | 71,520 | 3.568% | 73,146 | 29.881% |

### 风险等级

**高**。对于长 horizon（如 60d、120d），泄漏范围达数月，会系统性地高估模型在验证集上的表现。

### 修复方案（Purge）

`scripts/run_model_pipeline.py` 现在从 `target_col` / `return_col` 自动推断 horizon，并按每只股票的真实交易日序列构造 `_label_end_date`。训练行只有在 `_label_end_date <= train_end` 时才进入 fit；验证行只有在 `_label_end_date <= val_end` 时才进入模型选择。这样不会依赖 `BDay` 对交易日/节假日的近似。

---

## ✅ 已修复问题二：没有 Embargo（隔离间隔）

### 问题描述

val 从 `train_end + 1 day` 立即开始，test 从 `val_end + 1 day` 立即开始，两个边界都没有留 gap。

即使做了 purge（删除了标签污染的行），金融时序中相邻交易日的**特征值**仍高度自相关（同一股票的技术指标、动量因子等在相邻几天变化极小）。训练集最后几天的特征与验证集头几天的特征几乎相同，模型会从这种"记忆"中受益，导致 IC 虚高。

López de Prado 在《Advances in Financial Machine Learning》第 7 章中将这称为"序列相关泄漏"，建议在边界处留 `embargo ≥ h` 个交易日的空窗。

### 风险等级

**中**。单纯的 purge 不足以消除这种泄漏，必须配合 embargo 一起使用。

### 修复方案

`run_model_pipeline.py` 新增 `--embargo-days`。默认值等于 target horizon；设为 `0` 可关闭。实现按实际 split 内交易日期删除 val/test 开头的前 N 个交易日，不用自然日近似。

---

## ✅ 已修复问题三：同日成交假设

原回测和训练目标都使用同一行的 `score(t)` 与 `target_ret_fwd_h(t)`。由于特征包含当天收盘价、成交量和当天截面 rank，这等价于假设在知道全天数据后还能按当天收盘价建仓。

`run_model_pipeline.py` 新增 `--execution-lag-days`，默认 `1`。有效训练标签、IC target 和 portfolio return 都使用原始 target/return 按股票向后移动 1 个交易日后的值，即特征日 `t` 的信号只评价从 `t+1` 开始的 forward return。

---

## ✅ 已修复问题四：长 horizon 重叠窗口导致的指标虚高

### 问题描述

原回测对所有 horizon 都按固定的 `--rebalance-every 5` 调仓，但每次调仓记的是完整 `target_ret_fwd_{h}d`（h 日前向收益）。当 `h > 5` 时，相邻调仓日的持有窗口高度重叠（例如 150D 目标每 5 天记一次 150 日收益，约 30 倍重叠）。同时 `summarize_ic` 用 `sqrt(252)` 对高度自相关的每日 IC 序列做年化。两者叠加使 Sharpe 与 ICIR 随 horizon 单调虚增（旧横评中 150D Sharpe≈6.06、年化≈373%、验证 ICIR 19–22），这是评估口径伪迹，而非真实 alpha。

### 风险等级

**高（结论层面）**。它不一定是未来数据泄漏，但会系统性高估长 horizon 的预测力与组合表现，违反“关注泛化、信号稳定一致”的要求。

### 修复方案

`run_model_pipeline.py` 现在让 `--rebalance-every` 默认等于 target horizon，使持有期=调仓周期=年化基准，组合收益不重叠。`summarize_ic` 改为在按 horizon 步长抽取的**非重叠日期**上计算 `rank_ic_ir` 并按 `252/h` 年化；原始重叠值仅保留为 `rank_ic_ir_raw` 供对照。`evaluate_scores` 对 `Sharpe>3` 或 `ICIR>5` 打 `suspect_overfit_or_leak` 标记。模型选择改由 `scripts/run_walk_forward.py` 的多折平均验证 ICIR（去重叠）驱动。

---

## ✅ 已修复问题五：test split 未做 label purge 的不对称

### 问题描述

`apply_purge_embargo` 对 train/val 都按 `_label_end_date <= 边界` 做 purge，但 test split 原先直接 `masks["test"].copy()`，没有显式 purge。test 是最终 hold-out，没有右侧边界，但 forward label 窗口超出最后一个可用交易日的行其 label 不完整。

### 风险等级

**低**。这些不完整 label 行的 target/return 本就是 NaN，会在下游 `spearman_by_date`/`run_backtest` 被隐式丢弃，因此结果数值不变。但保留隐式行为不利于审计。

### 修复方案

`apply_purge_embargo` 现在显式写明 `purged["test"] = masks["test"] & (label_end <= data_end_ts)`，与 train/val 的 purge 对称，`data_end_ts` 为面板内最后一个交易日。这只是把原先的隐式 NaN-drop 显式化，结果保持一致。

---

## ✅ 已修复问题六：`sample_mask` 跨日期随机采样破坏截面

### 问题描述

**文件**：`scripts/run_model_pipeline.py` `sample_mask`

原实现在训练集内对**单行**随机采样（`rng.choice(idx, size=max_rows)`），当 `--max-train-rows` 激活时不保证每个日期的截面被完整保留。横截面模型按日期拟合，丢弃某一天的部分行会扭曲那一天的截面。

### 风险等级

**低**。样本仍在 train split 内，**不会将未来数据漏入过去**；但会破坏截面完整性，轻微影响 Preprocessor 的 median/mean/std 统计量。

### 修复方案

`sample_mask` 改为**按整日期随机采样**：用 seeded RNG 打乱训练集内的日期顺序，按累计行数取到 `max_rows` 预算为止，保留被选日期的**完整截面**。函数签名增加 `df` 参数，`run_model_pipeline.py` 与 `scripts/run_walk_forward.py`（fold 拟合与 hold-out 拟合）的全部调用点已同步更新。冒烟验证：`--max-train-rows 50000` 时 `train_rows=49583`（停在不超预算的整日期边界）。网格实验用默认 `max_train_rows=None`，不触发此路径，故对已有结果数值无影响。

---

## 实现与验证状态清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `scripts/run_model_pipeline.py` | 已记录，需随代码 diff 复核 | 新增 horizon 推断、执行滞后一日、精确 `_label_end_date`、purge、embargo、split audit |
| `scripts/run_target_model_experiments.py` | 已记录，需随代码 diff 复核 | 透传 `--execution-lag-days` 和可选 `--embargo-days` |
| `docs/model_pipeline.md` | 已记录 | 在方法论部分补充 purge + embargo + execution lag 说明 |
| `scripts/autoresearchclaw_param_search.py` | 待单独复核 | refinement 运行应继承 execution lag 和自定义 embargo 配置；该脚本必须进入后续 review scope 后才能标记为已验证 |
| `scripts/build_horizon_comparison.py` | 已实现 | 现已存在；读取 walk-forward 各运行的 `walk_forward_metrics.json`，按多折平均验证 ICIR（去重叠）选模并汇总 horizon 对比 |
| `scripts/run_walk_forward.py` | 已实现 | 逐年扩张 walk-forward + 最终 hold-out，复用 purge/embargo/execution-lag 与 per-fold preprocessor fit |

---

## 验证步骤

本轮轻量验证记录在 `review-stage/20260620-1324-leakage-validation.md`，覆盖 horizon 推断、execution lag 后的有效标签、按 `_label_end_date` 的 purge、以及 val/test 起点 embargo。完整实验结论仍需用真实数据重跑以下检查：

1. 以 `--target-col target_ret_fwd_5d` 运行 `run_model_pipeline.py`，日志中 `split_audit.train.label_end_max` 应不晚于 `2018-12-31`。
2. 日志中 `split_audit.val.label_end_max` 应不晚于 `2020-12-31`。
3. `--execution-lag-days 1` 时，5D 目标实际需要 `t+6` 的交易日可用，因此 train 最后可用 signal date 会比无滞后再少 1 个交易日。
4. 对旧报告中的长 horizon 结果全部重跑；旧的 `target_grid_core_*`、`horizon_comparison_*` 指标不能再作为无泄漏结论引用。

---

## 参考

- López de Prado, M. (2018). *Advances in Financial Machine Learning*, Chapter 7: Cross-Validation in Finance.
