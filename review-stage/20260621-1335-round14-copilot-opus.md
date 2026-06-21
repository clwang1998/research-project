# round14 Copilot Opus Review

Reviewer: GitHub Copilot Opus
Prompt file: tmp/copilot_opus_review_prompt.md
Scope: scripts/run_validation_ensemble_search.py
Generated: 2026-06-21T05:35:54+00:00
Recovered from VS Code Copilot Chat session storage after the response was not pasted into this file.

---

# GitHub Copilot Opus 审查结论

## 结论摘要

编排式过夜流水线没有发现 P0/P1 级阻断问题。监督 GAT 的防泄漏设计是稳健的（训练期用 OOF、val/test 用“仅在 train 上训练”的最终模型、再以 backward as-of 展开），集成评估也是防泄漏的（在 val 上选择、test 在定义之后才评估）。下列为 Medium 及以下的可修复风险。

## 发现（按严重度排序）

### Medium

**M1 — `--supervised-graph-embedding-path` 默认值 `.../latest/...` 指向一个从不被创建的目录**

- 位置：`scripts/run_model_pipeline.py`、`scripts/run_validation_ensemble_search.py`
- 影响：`scripts/train_supervised_gat.py` 只写入 `{out_dir}/{run_name}/supervised_gat_oof_embeddings.parquet`，全仓库没有任何代码创建/更新 `latest/`。因此只要直接运行下游脚本并带 `--include-supervised-graph-embeddings` 但不显式指定路径，就会在 `pd.read_parquet` 处 `FileNotFoundError`。过夜流程通过 `supervised_embedding_for()` glob 解析显式路径而幸免，所以编排作业能跑通，但该默认值对手动/walk-forward 使用具有误导性。
- 修复：让 GAT 训练成功后写入/更新一个 `latest` 符号链接（或拷贝）；或把默认值改为 `None` 并在缺失时给出明确报错提示用户传路径。runbook 中补充说明。

**M2 — 监督图特征 join 使用 `KEY_COLS + META_COLS` 作为键，存在静默全 NaN 风险**

- 位置：`scripts/run_model_pipeline.py` 的 `load_panel` 监督 join
- 影响：常规图嵌入 join 用 `on=KEY_COLS`（date, symbol），而监督 join 额外加了 `META_COLS`（sector, sub_industry, hq_state, hq_region）。panel 的 META 来自 `targets.parquet`，监督嵌入文件的 META 来自 `expand_embeddings_daily` 读取的 `calendar_metadata.parquet`。两者一旦某个 META 取值不一致，这些行的全部监督特征会静默变成 NaN，随后被预处理器中位数填充。由于本研究核心命题是“监督图嵌入是否有增量价值”，一次静默的部分 NaN join 可能让 `supervised_graph` 变体因为错误的原因看起来无效。
- 修复：监督文件改为只读 `columns=KEY_COLS + supervised_graph_cols` 并 `on=KEY_COLS` join（与常规图 join 一致）。若需保留 META 做校验，请在 join 后断言监督特征空值比例在期望范围内，否则告警/失败。

**M3 — `ensure_data` 的数据新鲜度校验只检查文件存在，无法满足新增的 10d 目标**

- 位置：`scripts/make_features.py` 的 `TARGET_WINDOWS`、`scripts/run_overnight_supervised_gat_search.sh` 的 `ensure_data`
- 影响：`TARGET_WINDOWS` 新增了 `10`，但 `ensure_data` 只检查 `targets.parquet` 是否存在、不校验 schema。在已有缓存数据的主机上，旧 `targets.parquet` 没有 `target_*_fwd_10d` / `target_ret_fwd_10d`，而 `SEARCH_HORIZONS` 默认含 `10`，会在 parquet 读取列时报错。属显式失败（非静默），但会破坏可断点续跑的过夜任务。
- 修复：在 `ensure_data` 中追加对所需目标列的校验（读取 parquet schema 检查 `target_ret_fwd_10d`），缺失则重建；或在文档中明确要求此更改后必须重跑 `prepare_data`。

### Low / 提示

**L1 — 最终 GAT 模型在真实 val 上做 early-stopping，导致 VAL 嵌入轻度乐观**

- 位置：`scripts/train_supervised_gat.py` 的 final val/test 段
- 影响：最终模型用 `final_val_dates`（真实 val 划分）做早停，又用同一模型产出 val 嵌入；这些 val 嵌入对 epoch 选择是轻度 in-sample，使 `supervised_graph` 变体的 VAL 指标（下游用于选择）略偏乐观。TEST 嵌入仍是干净 OOS（模型只在 train 上训练、在 val<test 上早停），headline test 数字不受影响。建议在写作中说明残留风险。

**L2 — `first_oof_train_end`（默认 2012-12-31）之前的训练期没有监督嵌入，被中位数填充**

- 位置：`scripts/train_supervised_gat.py` 的 `build_oof_folds` / `expand_embeddings_daily` backward as-of
- 影响：OOF 折叠从 `first_oof_train_end` 之后才产出预测，故约 2001-2012 训练行经 backward as-of 展开得到 NaN 监督特征，随后被中位数填充（近似常数）。非泄漏，但在很长一段训练区间稀释了监督信号。建议记录或考虑提前 `first_oof_train_end`。

**L3 — `feature_within_lookback` 仅过滤匹配 `\d+d` / `skip_\d+d` 的列名**

- 影响：不带 `Nd` 形式 token 的特征名永远不会被 `--max-lookback-days` 过滤，故 MLP 窗口大小限制是“尽力而为”启发式而非硬保证。鉴于本仓库的 `Nd` 命名约定基本无碍，提示一下以免把窗口消融当作硬上限来解读。

**L4 — Shell：`set -u` 下空数组展开 / 后台阶段失败暴露偏晚 / 默认无限等 GPU**

- 位置：`run_search_phase` 的 `sector_args`/`budget_args`；`main` 的 `cpu_pid`
- 影响：默认值下（`SECTOR_NEUTRAL=1`、`MAX_TRAIN_ROWS=800000`）数组非空，`"${arr[@]}"` 安全；仅当两者都被清空且 bash < 4.4 才有 `unbound variable`。`GPU_WAIT_TIMEOUT_SECONDS=0`（默认）会无限等待 GPU（过夜场景符合预期，但 GPU 永不空闲时会挂起）。`sector_args`/`budget_args` 未声明 `local`。对 Linux GPU 主机均为低风险。

## 缺失的测试（建议补充）

1. 泄漏边界测试：对 `build_oof_folds` / `split_masks` 断言不存在 `infer_date <= fold_train_end` 的 OOF 推断行。
2. join 健全性测试：断言监督 join（M2）不会引入超出预期的 NaN 比例。
3. `feature_within_lookback` / `safe_corrcoef` / `parse_regime_periods` 单测（边界：空、常数列、非法 regime 规格）。

## 已复核为正确、构成残留风险背景的项

- 默认图路径 `gat_embeddings_daily.parquet` -> `graph_relation_embeddings_daily.parquet` 是正确修复；旧名已无任何残留引用。
- `safe_corrcoef` 计算的 rank-IC 与原 `.rank().corr()`（Spearman）数值等价，并增加了常数/样本不足的守卫，无回归。
- `summarize_ic` 的 `ic.empty` 守卫与 `.get("ic", ...)` 安全；`clean_json(..., allow_nan=False)` 不会抛错（非有限的 float/np.floating 会被映射为 None）。
- `choose_weights` 的 `observed=True` 行为中性（空分类组此前也会被 `len(h) < ...` 跳过）。
- `tabulate>=0.9` 在 requirements 中，`to_markdown()` 不会缺依赖。
- 集成路径在 val 上选择、test 在定义之后评估，防泄漏。
- `args.label_horizon_days` 在评估循环前已设置，故 `evaluate_score_metrics_only` 的 `getattr(..., 1)` 取到真实 horizon，regime ICIR 的非重叠下采样正确。

**阻断判定**：未发现 P0/P1 阻断项、数据泄漏或不安全 shell 行为。M1-M3 属可复现性/正确性风险，建议在合并前修复（尤其 M2 直接关系到监督图变体结论的有效性），但不阻断当前编排式过夜运行。

（本次为只读审查，未修改任何文件或执行命令。）
