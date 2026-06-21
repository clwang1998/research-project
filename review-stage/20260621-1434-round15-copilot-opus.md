# round15 Copilot Opus Review

Paste the full VS Code Copilot Chat response below this line.

Reviewer: GitHub Copilot Opus
Prompt file: tmp/copilot_opus_review_prompt.md
Scope: scripts/run_model_pipeline.py, scripts/train_supervised_gat.py, scripts/run_walk_forward.py, scripts/run_overnight_supervised_gat_search.sh, review-stage/20260621-1335-round14-copilot-opus.md, review-stage/20260621-1335-round14-scope.md
Generated: 2026-06-21T06:34:09+00:00

---

审查完成。以下是对本轮（M1-M3 修复）的独立只读评审结论。我已对照实际源码逐项验证了修复的正确性，未修改任何文件、未执行命令。

## GitHub Copilot Opus 审查结论（round15 - 复核 M1-M3 修复）

## 结论摘要

未发现 P0/P1 阻断项。上一轮 round14 的 M1-M3 已被正确修复，未引入数据泄漏，shell 改动安全。修复与现有代码约定一致，回归风险已逐项排除。下列为新增的 Low 级别提示与残留风险，均不阻断合并。

## 修复验证（已确认正确）

- M1（默认路径） - `run_model_pipeline.py` 行 521 的 `None` 守卫正确。唯一的程序化调用方 `run_validation_ensemble_search.py` 行 327 在 `supervised_path is None` 时直接跳过该 variant，因此 `--include-supervised-graph-embeddings` 始终与一个已解析的真实路径成对出现，无回归。手动 CLI / walk-forward 现在抛出清晰的 `ValueError`，而非对永不存在的 `latest/` 目录报 `FileNotFoundError`，属严格改进。全仓库（含 docs/runbook）无任何代码再引用旧默认路径。
- M1（symlink） - `run_dir = Path(args.out_dir)/run_name`（`train_supervised_gat.py` 行 832），故 `latest` 是 `run_dir` 的同级目录，相对软链 `../run_name/file` 解析正确（`train_supervised_gat.py` 行 803）。已正确处理悬空软链、目录、以及不支持 symlink 的文件系统（`copy2` 回退）。`train_gat_targets` 串行执行（`run_overnight_supervised_gat_search.sh` 行 206），不存在 `latest` 写入竞态。
- M2（join 键） - 改为只读 `KEY_COLS + supervised_graph_cols` 并 `on=KEY_COLS` join（`run_model_pipeline.py` 行 533、行 552），与既有图嵌入 join（`run_model_pipeline.py` 行 515）一致。panel 的 META 来自 `targets.parquet`（`run_model_pipeline.py` 行 480），独立于监督文件，故无信息丢失。新增重复键守卫 + 缺失率日志。scope 记录的 `key_only_not_meta=0` 复核了既有 8 个 run 的历史指标不受影响。
- M3（schema 校验） - 校验列名 `target_ret_fwd_{h}d` / `target_{family}_fwd_{h}d` 与 `make_features.py` 行 1095（`target_excess_sector_fwd_{h}d`、`target_excess_market_fwd_{h}d`）精确匹配，`TARGET_WINDOWS` 含 10（`make_features.py` 行 36）。heredoc 用 `<<'PY'` 引号防展开、env 正确透传、退出码作为函数返回值、置于 `if` 中故 `set -e` 安全。
- L4（shell） - `local -a sector_args/budget_args`（`run_overnight_supervised_gat_search.sh` 行 165）已修复 round14 的 unset/泄漏隐患。

## 新发现（按严重度排序，均为 Low）

### L1 - 新鲜度门只校验 SEARCH_*，未校验 GAT_HORIZONS/GAT_FAMILIES

- 位置：`run_overnight_supervised_gat_search.sh` 行 85 `processed_data_ready`
- 影响：GAT 训练用的是 `GAT_HORIZONS` / `GAT_FAMILIES`（`run_overnight_supervised_gat_search.sh` 行 209，默认等于 `SEARCH_*`）。若用户把 `GAT_HORIZONS` 覆盖为 `SEARCH_HORIZONS` 的超集，门不会检测到缺失的 GAT 目标列，`train_supervised_gat.py` 会在跑到一半时才显式失败，破坏可断点续跑。
- 修复：在 `required` 集合中并入 `GAT_HORIZONS` / `GAT_FAMILIES`（取并集后再做 schema 检查）。

### L2 - M2 缺失率为“仅日志”，未做阈值守卫

- 位置：`run_model_pipeline.py` 行 554
- 影响：round14 的 M2 建议是“断言空值比例在期望范围内，否则告警/失败”。当前实现只 `print(all_features=.../any_feature=...)`，需要人工盯日志。在自动化过夜场景下，一次错配的 target 文件导致的高 NaN join 不会 fail-fast。
- 修复：对 in-range 日期窗口内的 `missing_all` 设期望上限，超限则告警或抛错。（因显式路径要求 + 重复键守卫已覆盖主要风险，故为 Low。）

### L3 - `update_latest_outputs` 不清理上一轮遗留文件

- 位置：`train_supervised_gat.py` 行 782
- 影响：若某轮产物文件名变化，旧 `latest/` 中的过期软链/拷贝会残留，可能把消费者指向陈旧文件。因文件清单稳定且 `latest` 仅为便利指针、`LATEST_RUN.txt` 已记录真实 run，风险很低。
- 修复（可选）：进入循环前清空 `latest/` 中未列入清单的条目，或写 manifest。

### L4 - pyarrow 导入失败会触发整管线重建

- 位置：`run_overnight_supervised_gat_search.sh` 行 94
- 影响：`processed_data_ready` 的 python 段在 `import pyarrow` 失败时 `exit(1)`，从而触发完整 `run_cloud_data_pipeline.sh` 重建。若 pyarrow 真缺失，重建本身也会失败；若为瞬时/环境问题，则会保守地强制一次昂贵重建。属可接受的 fail-safe，仅作提示。

## 残留风险（非本 diff 引入，建议在写作/walk-forward 路径确认）

- walk-forward 经 `rmp.load_panel`（`run_walk_forward.py` 行 261）对所有 fold 复用同一个 train/val/test 划分产出的监督 OOF 嵌入文件。OOF 性质仅对训练该 GAT 的那个划分成立；对任意 walk-forward 排程，per-fold 的“样本外”性质未必严格保证。建议确认 walk-forward 用的是与其折叠排程匹配的监督嵌入。

## 建议补充的测试（仍未覆盖）

1. `processed_data_ready`：缺 `target_ret_fwd_10d` 时返回 stale、齐全时返回 ready 的单测。
2. `update_latest_outputs`：断言生成的软链可解析到 `run_dir`，并覆盖 `copy2` 回退分支。
3. M2 join：断言监督特征 NaN 比例不超出预期窗口。

阻断判定：无 P0/P1 阻断，无新增数据泄漏，无不安全 shell 行为。M1-M3 修复正确且与既有约定一致，可合并；L1-L4 为可择机处理的低风险项。（本次为只读审查，未修改文件或执行命令。）
