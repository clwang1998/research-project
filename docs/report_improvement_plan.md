# S&P 500 案例研究报告 · 指导改进计划书

> **适用对象**：`report/sp500_case_study.pdf`（quant researcher take-home 提交稿）
> **目标**：从「严谨但无 alpha 的方法学报告」升级为「有 conviction、能打动 PM 的 alpha pitch」
> **数据约束**：仅可用 `data/raw/sp500_stocks.csv`(OHLCV) + `data/raw/sp500_companies.csv`(sector / sub-industry / HQ / founded / `date_added`)；正文 ≤ 10 页
> **生成日期**：2026-06-22

---

## 0. 一句话诊断

| 维度 | 评级 | 说明 |
|---|---|---|
| 实验卫生（leakage 控制 / overlap 校正 / walk-forward） | **A-** | 明显在平均候选人之上，保留 |
| 给 PM 的 alpha pitch（品味 / conviction / 沟通） | **B- / C+** | 录用线之下，本计划要解决的就是它 |

**核心病灶**：用 525 特征 / 6 类模型 / GAT / 基础模型，最终结论是「打不过单因子动量」；而唯一的正面结果极可能是网格搜索噪声，整套结论又建立在一个**未定量修正、且恰好最毒化动量**的幸存者偏差之上。即——你证明了自己诚实、会做实验卫生，但没证明你能产生 alpha、有研究品味、像交易真钱的人一样思考。

---

## 1. 必须先认清的两个致命矛盾（不解决，可信度从根上塌）

- **矛盾 A（幸存者 × 动量）**：你唯一「稳健」的信号是横截面动量，而动量恰恰最被你最大的缺陷——幸存者偏差——污染（空头腿缺了破产/退市的最差结局，长头腿高估赢家持续性）。报告里只有方向性的 "treat as upper bound"，**没有任何数字级 bound**。
- **矛盾 B（多重检验 × 唯一胜利）**：那个 10d sector-neutral XGBoost+graph 的「胜利」rank IC 反而更低（0.0239 < 0.0271），只有风险调整后好看；它是 模型×horizon(11)×特征变体(4)×ensemble(5)×组合构造(5) 大网格里挑出来的最好一格，却**没有 Deflated Sharpe / PBO 护栏**。

> 这两条是 PM 一眼会看穿的。优先级最高。

---

## 2. 严厉批评清单

### 2.1 保留（这些是真功夫，别在重写时丢掉）
- 一日执行滞后、双向 label purge、horizon embargo、train-only 拟合、盘前 winsorize。
- Overlap 校正 + `Sharpe>3 / ICIR>5` sanity gate。
- 正确的横截面相对收益框架、sector-neutral 组合。
- 敢报负面结果（诚信分）。

### 2.2 砸（按严重度）
1. **幸存者污染动量**，且无定量 bound（矛盾 A）。
2. **唯一胜利无多重检验护栏**，缺 DSR / PBO（矛盾 B）。
3. **简历驱动开发**：日频横截面 |IC|≈0.01 的 SNR 上堆 GAT / Kronos，纯增过拟合面、烧页数预算。Kronos 半页 test IC 为负、样本 60/10 个日期、你自己叫它 "sampling artifact"。
4. **因子归因完全缺席**：525 特征却从没回答「扣掉已知价量因子后还剩 alpha 吗」；只做了 sector/market 中性，没做价量因子中性。
5. **容量 / 换手 / 冲击点到为止**：报告原文 "Market impact … is not modeled"；no-trade band 扫了 0/5/10/15% 却没做成 headline。
6. **hold-out 单一 regime**（2022–2026 动量友好期），结论近乎循环；应给 Sharpe 分布而非点估计。
7. **硬伤**：正文 11 页 > 10 页上限；几乎无 t-stat / 置信区间。
8. **叙事自我证伪**：每个正面结论被立刻亲手否定，读起来像在论证自己没做出东西；写作层面信噪比是反的。

---

## 3. 可行性边界（基于当前 raw 数据，已逐项核对）

| 改进项 | 用什么 | 仅当前数据？ |
|---|---|---|
| 重写叙事 / 砍 GAT·Kronos / 压到 10 页 | 无 | ✅ |
| **DSR + PBO** | 现有 `output/` 网格结果，纯后处理 | ✅ 不用重跑模型 |
| **CPCV 多 regime** Sharpe 分布 | 现有面板 | ✅ |
| **因子中性 IC / Fama–MacBeth** | `price_momentum / volatility / liquidity_volume / statistical_linkage` 已算好 | ✅ **但只能中性到「价量+行业」因子** |
| IC 衰减 / 等权 benchmark 对照 | 现有面板 | ✅ |
| 容量曲线（net Sharpe vs AUM） | 现有 ADV + **假设**冲击系数 | ⚠️ 需假设参数（非外部数据） |
| 幸存者 haircut | `date_added`（已有）+ **假设**退市率/退市收益 | ⚠️ 纳入端可 PIT；退市端只能参数化 |
| 真·size / value / quality 中性 | 需 market cap / 财报 | ❌ 当前数据没有 |
| 真·测量级幸存者修正 | 需 PIT 成分股 + 退市收益 | ❌ 外部数据 |

**诚实 scope（必须写进报告）**：本数据集没有市值 / 财报，因此「因子中性化」**不可能是 Barra / Fama–French 全因子**，只能是**价量 + 行业因子中性**（市场 beta、多周期动量、短期反转、波动率/低波、Amihud 流动性、特异波动、GICS sector）。但这正是 OHLCV-only 任务下「残差 alpha」的**正确定义**——你的信号必须打败「任何人用同样输入就能搭出来的价量因子」。

---

## 4. 改进任务清单（按 ROI 排序）

### P0 — 不做就出局
| # | 任务 | 交付物 | 仅当前数据 |
|---|---|---|---|
| P0-1 | **重写叙事，第一段就给答案**：交易什么信号 → 净 Sharpe（DSR 后）→ 容量 → 回撤 → 与动量相关性 → 下一步 | 新 abstract + §1 | ✅ |
| P0-2 | **多重检验校正**：DSR + PBO；IC 的 t-stat、Sharpe 的 bootstrap CI；把 10d「win」放回全网格 Sharpe 分布 | `scripts/deflated_sharpe.py` + 图 | ✅ |
| P0-3 | **因子归因**：价量+行业因子中性 IC / Fama–MacBeth（详见 §5） | `scripts/factor_neutral_alpha.py` + 表 | ✅ |
| P0-4 | **幸存者从「一句话」变「一个数」**：`date_added` 做 PIT 纳入过滤 + 退市率×退市收益的 haircut 区间 | Sharpe 定量区间 + 敏感性表 | ⚠️ 需假设参数 |

### P1 — 显著加分
| # | 任务 | 交付物 |
|---|---|---|
| P1-1 | 砍 GAT / Kronos 进附录或各一句话，把页数还给 P0 | 精简正文 |
| P1-2 | 容量分析做成正式图：net Sharpe vs AUM、turnover 分解、no-trade band 的 cost/alpha trade-off | 容量图 |
| P1-3 | 多 regime OOS：CPCV 出 Sharpe 分布；hold-out 切 2008/2020/2022 子区间 | 分布图 |
| P1-4 | 压回 10 页以内 | 终稿 |

### P2 — 锦上添花
- 信号 IC 衰减 / 半衰期；与标准多因子 benchmark 对照给 Sharpe 一个参照系。

---

## 5. Route B：因子中性残差 alpha（核心方法）

### 5.1 先澄清：**不是放弃 LGBM**
因子中性化是**套在模型外面的一层**，不是模型的替代品。
- **模型**（Ridge / LGBM / XGBoost）= 把 525 弱特征压成一个分数的引擎。
- **中性化** = 评估/重定向这个分数的一层包装。

它可以放在三个位置（都不需要扔掉 LGBM）：
1. **模型输出上（事后诊断）**：LGBM 照常出分 `s`，对因子取残差看还有没有 IC。残差 IC≈0 → 模型只是重新打包动量；残差显著 → 更要留着。
2. **target 上（残差化标签，推荐）**：先把已知因子能解释的未来收益剥掉，让 LGBM 只学剩下的。
3. 特征上（正交化输入，可选，效果一般）。

**战略重构**：动量打赢 ≠ ML 没用，而是说明你让 LGBM 去预测「原始相对收益」= 和动量正面硬刚（结构上必输）。Route B 把 LGBM 调到「捡动量捡不到的残差 alpha」——给它一个能赢的工作。

### 5.2 因子面板 F（**预先登记**，别加到信号显得独特为止 = 反向 p-hacking）
全部已在 `data/processed/features_by_group/` 中：
- 市场 beta、特异波动（`statistical_linkage.parquet`）
- 12−1 动量 `mom_252d_skip_21d`、短期反转 `ret_5d/rev_*`（`price_momentum.parquet`）
- 已实现波动 `vol_20d/60d`（`volatility.parquet`，低波）
- Amihud + log 美元成交额（`liquidity_volume.parquet`，size/流动性代理）
- GICS sector one-hot

### 5.3 方案②：残差化 target + LGBM
逐日截面把未来收益对因子回归，残差当新 target：

```
r_{i, t→t+h} = Σ_k θ_{k,t} · F_{k,i,t} + r̃_{i,t}
```

用 `r̃_{i,t}` 训练 LGBM。它的非线性/交互（反转 × 流动性 × regime）正好用在刀刃上。

### 5.4 评估：是否还有 alpha
- **因子中性 IC**：`corr(neutralized signal, forward relative return)`，与原始 IC 对比。≈0 → 诚实 kill；仍显著 → 真正交残差。
- **Fama–MacBeth 边际检验**（更干净）：

```
r_{i, t→t+h} = γ0_t + γs_t · s_{i,t} + Σ_k γF_{k,t} · F_{k,i,t} + u_{i,t}
```

  对 `mean_t(γs_t)` 做 **Newey–West**（重叠 horizon 必须用 overlap-robust SE，复用现有非重叠子采样）t 检验。显著且符号对 = 控制因子后仍有边际溢价。

### 5.5 经济性 + 护栏
- 对中性化残差建 sector-neutral 多空 decile，h 日换手、5bps/side，报告**净 Sharpe / 换手 / 容量 / 与动量相关性**。卖点 = 一条与动量近乎不相关、净费后 Sharpe 为正的残差 book。
- **DSR**（按试过的信号数校正）+ **CPCV** 分布；选择（哪个残差、哪个 h）只在 train/val 上做。

### 5.6 残差最可能藏哪（经济先验，OHLCV 可建、天然正交于 12−1 动量）
- **隔夜 vs 日内收益分解**（close→open vs open→close，隔夜异象）—— 首选，你已有该特征。
- **特异波动**（Ang et al. 低 idio-vol），beta 去除后，`statistical_linkage` 里有。
- **1–5 日反转 × 流动性条件**（正交于 12−1，但盯紧换手）。
- **成交量 / Amihud 冲击**。

### 5.7 三个会自欺的坑
1. **逐日截面回归，不要 pooled**（避免跨期杠杆）。
2. 因子高度共线 → 截面回归用 **ridge** 稳定系数；按日 winsorize+标准化。
3. **中性化通常抬高换手** → 判据是费后 Sharpe + 容量，不是 IC。

---

## 6. 模型取舍（「砍」≠「放弃模型类」，收敛 trial 数让 DSR 更好看）

| 模型 | 处置 | 原因 |
|---|---|---|
| 动量 baseline | **留**（benchmark + 因子面板成员） | 必须打败的对象 |
| Ridge | **留**（线性对照） | 解释性强、过拟合小 |
| LGBM **或** XGBoost | **留一个当主力** | 非线性/交互引擎；两个 GBDT 近重复 |
| MLP | **降级 / 移出 headline** | 该 SNR 下不稳定，hold-out 已证明 |
| GAT / Kronos | **进附录或一句话** | 复杂度信号 ≠ alpha，且烧页数 |

---

## 7. 目标 10 页报告结构（赢的版本，先给答案）

| 页 | 章节 | 要点 |
|---|---|---|
| 1 | 问题 + **Headline 答案** | 第一段直接给：我交易什么信号 / 净 Sharpe(DSR 后) / 容量 / 回撤 / 与动量相关性 / 下一步 |
| 1–2 | 数据 + 幸存者 | 价格调整审计；幸存者**定量 haircut 区间** + `date_added` PIT 纳入 |
| 2–3 | 特征工程 | 经济分组（精简）+ 单因子 IC sanity check |
| 3–4 | 方法 | 因子面板 + 中性化 + 精简后的模型 + leakage 控制 + overlap 校正 |
| 5–6 | 结果（核心） | 因子中性 IC + Fama–MacBeth(NW t) + **DSR/PBO** + 残差信号经济性 |
| 6–7 | 稳健性 | **CPCV Sharpe 分布** + regime 切片 + **容量曲线** + no-trade band trade-off |
| 8 | 讨论 | 过拟合 / leakage / 幸存者(带数) / 换手容量 / regime / 经济直觉 |
| 9 | 局限 + 结论 | **有 conviction**：我会交易什么、为什么、装多少钱、下一步把研究预算投哪 |

> GAT / Kronos → 一句话或附录。全文 ≈ 9 页，留 1 页余量。

---

## 8. 面试口头定位（一句话）

> 「这份作业我最自豪的不是模型，而是我建了一套能让我**知道自己有没有过拟合**的系统。它告诉我在这个数据集上最诚实的可交易信号是什么，以及**为什么再加模型是在浪费风险预算**。」

两条叙事路线（选一条讲到底）：
- **路线 A（诚实但有 conviction）**：纯价量 + 当前成分股下，可稳健交易的 alpha 主要就是低换手横截面动量（净 Sharpe ~1.05，DSR/幸存者 haircut 后落在 [Y′,1.05]）；ML 增量 alpha 统计不显著（DSR=…, PBO=…）→ **决策：不上复杂模型，上低换手动量 + 严格成本/容量约束，下一笔研究预算投 point-in-time 宇宙**。
- **路线 B（若找到真增量）**：因子中性后存在正交、显著、有容量的残差信号 → 讲成可交易产品（前提：过 DSR/CPCV）。

---

## 9. 交付物与执行顺序

| 顺序 | 脚本 / 产物 | 完成定义（DoD） |
|---|---|---|
| 1 | `scripts/deflated_sharpe.py` | 对现有 `output/` 网格输出 DSR/PBO + 全网格 Sharpe 分布图；10d「win」定位 |
| 2 | `scripts/factor_neutral_alpha.py` | 逐日 ridge 中性化 → 因子中性 IC + Fama–MacBeth(NW t) → 残差多空组合(净 Sharpe/换手/动量相关性) → DSR |
| 3 | 幸存者 haircut + `date_added` PIT 纳入 | Sharpe 定量区间 + 敏感性表 |
| 4 | 容量 / no-trade band 图 | net Sharpe vs AUM + cost/alpha trade-off |
| 5 | CPCV 多 regime | Sharpe 分布 + regime 切片 |
| 6 | 报告重排至 ≤10 页 | 按 §7 结构，先给答案 |

**建议起点**：先做 (1) DSR/PBO ——它对 PM 冲击最大，且能立刻判定那个 10d 正面结果是不是噪声，决定走路线 A 还是 B。

---

*本计划书仅依赖当前仓库的 raw 数据与已算特征；标 ⚠️ 的项需要文献假设参数（非外部数据文件），标 ❌ 的项需外部数据、不在本作业 scope 内但应在报告局限中点明。*
