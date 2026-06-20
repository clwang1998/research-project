# Claude 对话记录整理：量化研究 Take-home Project 学习笔记

> 来源：用户粘贴的 Claude 对话记录  
> 主题：S&P 500 股票收益预测、机器学习建模、walk-forward + purge/embargo 验证框架、量化研究入门术语  
> 适用场景：量化研究 / 数据科学 take-home project 报告准备

---

# 1. 项目总体解读

这是一个 **量化研究 / 数据科学 take-home project**。从文件名 `MLP` 看，很可能是某家对冲基金或多策略平台的面试/评估任务。核心任务是：

> 使用技术因子和机器学习方法预测股票收益，并构建一个交易组合来验证预测是否有效。

换句话说，这个项目考察的不只是“能不能训练一个模型”，而是：

- 能否理解真实金融数据；
- 能否构造有经济逻辑的特征 / 因子；
- 能否严格避免前视偏差和过拟合；
- 能否进行样本外验证；
- 能否用回测检验交易信号；
- 能否意识到交易成本、幸存者偏差、体制依赖等现实问题。

---

## 1.1 总体目标

项目目标：

> 用 S&P 500 股票的历史数据，构造特征 / 信号，训练机器学习模型预测未来收益，然后基于预测结果构建交易组合并回测。

关键词：

```text
预测股票收益 + 构建组合 + 样本外评估
```

---

## 1.2 交付要求

项目要求：

- 使用 Python / PyTorch 或任意数据科学工具栈完成；
- 提交一份 PDF case study report；
- 报告最多 10 页；
- 不要求提交代码；
- 预期投入不超过 3 天；
- 需要在收到项目后 3 天内邮件发回报告。

---

## 1.3 数据说明

数据来自 Kaggle 的 S&P 500 日频数据集，主要包括两个文件：

### `sp500_stocks.csv`

包含当前 S&P 500 成分股从 2000 年至今的日频 OHLCV 数据：

| 字段 | 含义 |
|---|---|
| Open | 开盘价 |
| High | 最高价 |
| Low | 最低价 |
| Close | 收盘价 |
| Adj Close | 复权收盘价 |
| Volume | 成交量 |

该文件大约有 300 多万行数据。

### `sp500_companies.csv`

包含每家公司的行业信息：

| 字段 | 含义 |
|---|---|
| sector | 行业 |
| sub_industry | 子行业 |

这些信息可以用于行业中性化、子行业相对收益计算、行业内排名等。

---

# 2. 项目评分重点

这个项目本质上希望候选人走一遍完整的数据科学 / 量化研究流程：

1. 理解数据集；
2. 构造有预测力的特征 / 信号；
3. 准备训练数据集；
4. 选择合适模型并训练；
5. 搭建模型评估和选择流程；
6. 进行验证和回测；
7. 解释每一步为什么这样做。

---

## 2.1 特征 / 信号

从原始 OHLCV 数据中构造可能预测未来收益的特征。

常见例子包括：

- 动量因子；
- 布林带；
- MACD；
- RSI；
- 短期反转；
- 波动率；
- 成交量变化；
- 流动性指标。

强的特征通常称为：

\[
\alpha
\]

弱因子可以通过统计模型或机器学习模型组合成更强的 alpha。

---

## 2.2 预测目标

项目允许预测：

- 1 日收益；
- 多日收益。

但是需要说明选择理由。

较合理选择：

\[
h = 5
\]

即预测未来 5 个交易日收益。

原因：

- 1 日收益噪声过大；
- 1 日预测换手率太高，交易成本容易吃掉收益；
- 月度预测样本较少，反馈慢；
- 5 日预测是信噪比与换手率之间的折中。

---

## 2.3 最重要提示：预测相对收益，而不是绝对收益

项目中最关键的一点是：

> 应该预测相对收益，而不是原始绝对收益。

原因：

- 原始收益极难预测；
- 个股波动中很大一部分来自市场 beta；
- 大盘涨跌很难预测；
- 去掉市场或行业共同成分后，剩下的横截面 alpha 更容易建模。

可以定义未来相对收益为：

\[
r^{rel}_{i,t}
=
r^{fwd}_{i,t,h}
-
\overline{r^{fwd}_{t,h}}
\]

其中：

- \(r^{fwd}_{i,t,h}\)：股票 \(i\) 在 \(t\) 日之后 \(h\) 天的未来收益；
- \(\overline{r^{fwd}_{t,h}}\)：同一天全市场或同组股票的平均未来收益；
- \(r^{rel}_{i,t}\)：股票 \(i\) 的未来相对收益。

也可以在行业或子行业内去均值：

\[
r^{rel}_{i,t}
=
r^{fwd}_{i,t,h}
-
\frac{1}{|G(i)|}
\sum_{j \in G(i)}
r^{fwd}_{j,t,h}
\]

其中 \(G(i)\) 表示股票 \(i\) 所在行业或子行业。

---

# 3. 三天执行计划

## Day 1：数据、目标、特征

### 3.1 数据加载与清洗

建议用 `Adj Close` 计算收益。

原因：

- `Adj Close` 已经处理拆股和分红；
- 普通 `Close` 可能在分红日或拆股日产生虚假的暴跌 / 暴涨。

需要处理的问题：

### IPO / 上市时间不齐

每只股票需要至少有一定历史长度才纳入，比如：

\[
N = 252
\]

即至少有约一年交易日历史。

否则很多长窗口因子无法计算。

### 极端值 winsorize

对日收益或因子做横截面分位裁剪，例如：

\[
1\% / 99\%
\]

目的：

- 防止 bad tick；
- 防止并购跳空；
- 防止极端异常值污染模型。

### 流动性过滤

可以根据 20 日平均美元成交额筛选：

\[
\text{DollarVolume}_{i,t}
=
P_{i,t}
\times
Volume_{i,t}
\]

剔除流动性最差的股票，比如后 10%。

原因：

- 信号集中在小票 / 低流动性票上，真实交易不可行；
- 低流动性股票交易成本和市场冲击更高。

---

## 3.2 幸存者偏差

Kaggle 数据集只包含当前 S&P 500 成分股。

这意味着：

- 已经退市的股票不在数据里；
- 被并购的股票不在数据里；
- 跌出指数的股票不在数据里。

这会造成：

\[
\text{survivorship bias}
\]

即幸存者偏差。

影响方向：

> 回测收益可能被系统性高估。

因为很多历史上的“输家”已经被数据集剔除了。

这个问题在该数据集下无法完全修复，因为没有 point-in-time 成分股名单。但报告中必须正面承认：

- 数据只含现存成分股；
- 回测可能高估真实表现；
- 这是数据层面的限制。

---

## 3.3 预测目标选择

推荐预测未来 5 日相对收益：

\[
h = 5
\]

定义：

\[
r^{fwd}_{i,t,5}
=
\frac{P_{i,t+5}}{P_{i,t}} - 1
\]

再做横截面或行业内去均值，得到 label：

\[
y_{i,t}
=
r^{fwd}_{i,t,5}
-
\text{mean}_{j \in G(i)}
\left(
r^{fwd}_{j,t,5}
\right)
\]

其中 \(G(i)\) 可以是：

- 全市场；
- 行业；
- 子行业。

---

## 3.4 因子构造

建议覆盖多个不完全相关的类别。

### 动量 Momentum

经典因子：

\[
\text{Momentum}_{12-1}
=
\frac{P_{t-21}}{P_{t-252}} - 1
\]

含义：

- 使用过去 12 个月收益；
- 跳过最近 1 个月，避免短期反转影响。

经济直觉：

> 过去长期表现好的股票，在短期内可能继续跑赢。

---

### 短期反转 Reversal

例如过去 1–5 日收益的反向：

\[
\text{Reversal}_{5}
=
-
\left(
\frac{P_t}{P_{t-5}} - 1
\right)
\]

经济直觉：

> 短期涨太多的股票可能回调，短期跌太多的股票可能反弹。

---

### 波动率 Volatility

例如过去 20 日收益标准差：

\[
\text{Volatility}_{20}
=
\sigma(r_{t-19}, \ldots, r_t)
\]

经济直觉：

> 低波动股票可能具有更稳定的风险调整后收益。

---

### 量价 / 流动性

Amihud 非流动性：

\[
\text{Amihud}_{i,t}
=
\frac{|r_{i,t}|}{\text{DollarVolume}_{i,t}}
\]

可以再取 20 日平均：

\[
\text{Amihud}_{20}
=
\frac{1}{20}
\sum_{k=0}^{19}
\frac{|r_{i,t-k}|}{\text{DollarVolume}_{i,t-k}}
\]

经济直觉：

> 流动性差的股票可能要求更高预期收益，但交易成本也更高。

---

### 技术指标

包括：

- 布林带位置；
- MACD；
- RSI；
- 价格距 50 日 / 200 日均线距离。

---

## 3.5 因子标准化

所有因子建议每天做横截面标准化。

### Z-score

\[
z_{i,t}
=
\frac{x_{i,t} - \mu_t}{\sigma_t}
\]

其中 \(\mu_t\) 和 \(\sigma_t\) 是当天横截面均值和标准差。

### Rank-normalization

将因子变成当天横截面排名：

\[
\text{rank}_{i,t}
=
\text{Rank}(x_{i,t})
\]

优点：

- 更抗极端值；
- 更符合相对收益预测；
- 不同因子之间更容易比较。

---

# 4. Day 2：训练管线、验证框架、建模

## 4.1 先搭验证框架，再训练

金融时间序列不能使用随机 K-fold。

随机切分会把未来样本混入训练集，造成前视偏差。

正确方法：

\[
\text{Walk-forward} + \text{Purge} + \text{Embargo}
\]

---

## 4.2 Walk-forward 验证

Walk-forward 模拟真实部署：

\[
\text{用过去训练} \rightarrow \text{用未来验证} \rightarrow \text{继续向前滚动}
\]

示例：

```text
Fold 1:
Train:      2005–2014
Validation: 2015
Test:       2016

Fold 2:
Train:      2005–2015
Validation: 2016
Test:       2017

Fold 3:
Train:      2005–2016
Validation: 2017
Test:       2018
```

训练窗口逐渐扩张，验证窗口不断向未来移动。

---

## 4.3 Purge

因为 label 使用未来 \(h\) 天收益，所以训练集尾部靠近验证集的样本可能发生重叠。

如果：

\[
y_t
=
r_{t:t+h}
\]

那么样本 \(t\) 的标签区间是：

\[
[t, t+h]
\]

如果训练集最后一部分样本的标签区间伸入验证期，就会发生泄漏。

判断条件：

\[
t + h > T_{\text{train end}}
\]

这些样本需要删除。

如果：

\[
h = 5
\]

则通常需要 purge 掉训练集尾部约 5 个交易日的样本。

---

## 4.4 Embargo

金融序列存在自相关。

验证期之后紧邻的数据可能携带验证期信息，并在后续 fold 进入训练集。

为减少这种泄漏，在验证集之后加入 embargo 缓冲区：

```text
Train → Purge → Validation → Embargo
```

日频股票可以设置：

\[
\text{embargo} = 5 \sim 10 \text{ trading days}
\]

---

## 4.5 Walk-forward + Purge / Embargo 示意图说明

单折结构：

```text
[==== Train ====][ Purge ][===== Validation =====][ Embargo ][ Future ]
```

对应含义：

| 区域 | 作用 |
|---|---|
| Train | 模型训练 |
| Purge | 删除训练集尾部会泄漏验证信息的样本 |
| Validation | 调参、选模型 |
| Embargo | 验证后缓冲，防止自相关泄漏 |

训练样本示例：

```text
样本 A（离边界远）:
● —— 标签看未来 5 天 ——▶
终点还在训练区
→ 安全，保留

样本 B（贴着边界）:
● —— 标签看未来 5 天 ——▶
终点落进验证区
→ 时间重叠，删除
```

一句话：

> Purge 防止训练标签伸进验证期；Embargo 防止验证期信息通过自相关渗入后续训练。

---

## 4.6 sklearn TimeSeriesSplit 的问题

`sklearn.model_selection.TimeSeriesSplit` 是简化版。

它只做：

```text
Train → Validation
```

但默认没有：

```text
Purge
Embargo
```

所以直接使用可能仍然泄漏。

更安全方法：

1. 用 `TimeSeriesSplit` 生成初始切分；
2. 手动删除 purge 区间；
3. 手动跳过 embargo 区间；
4. 再训练模型。

也可以使用 `mlfinlab` 的 `PurgedKFold`。

---

# 5. 建模策略

建议由简到繁。

## 5.1 基线模型：等权因子 / Ridge 回归

### 等权因子

将标准化后的因子简单平均：

\[
\hat{y}_{i,t}
=
\frac{1}{K}
\sum_{k=1}^{K}
z^{(k)}_{i,t}
\]

优点：

- 可解释；
- 不容易过拟合；
- 作为强 baseline 很合适。

### Ridge 回归

线性模型：

\[
\hat{y}
=
X \beta
\]

Ridge 损失：

\[
\mathcal{L}
=
\sum_i
(y_i - x_i^\top \beta)^2
+
\lambda \|\beta\|_2^2
\]

其中：

- 第一项是预测误差；
- 第二项是正则化；
- \(\lambda\) 控制正则强度。

---

## 5.2 主力模型：LightGBM / XGBoost

梯度提升树适合表格数据，能够捕捉：

- 非线性关系；
- 因子交互；
- 阈值效应。

注意限制复杂度：

- 限制树深；
- 加正则；
- early stopping；
- 只用验证集调参。

---

## 5.3 可选模型：MLP

MLP 即多层感知机：

\[
x \rightarrow \text{hidden layers} \rightarrow \hat{y}
\]

优点：

- 表达能力强；
- 可拟合复杂非线性。

缺点：

- 股票收益标签噪声大；
- 特征数量有限时容易过拟合；
- 对调参较敏感。

报告中可以诚实说明：

> 神经网络在该任务中未必优于树模型。若 MLP 样本内显著优于样本外，则说明存在过拟合。

---

# 6. Day 3：回测、稳健性检验、报告写作

## 6.1 预测质量评估：IC

IC 是 Information Coefficient，信息系数。

每天计算预测值和真实未来相对收益的横截面相关性：

\[
IC_t
=
\text{corr}_{i}
\left(
\hat{y}_{i,t},
y_{i,t}
\right)
\]

通常使用 Spearman 秩相关：

\[
IC_t
=
\text{SpearmanCorr}_{i}
\left(
\text{rank}(\hat{y}_{i,t}),
\text{rank}(y_{i,t})
\right)
\]

最终报告：

\[
\overline{IC}
=
\frac{1}{T}
\sum_{t=1}^{T}
IC_t
\]

IC IR：

\[
ICIR
=
\frac{\text{mean}(IC_t)}{\text{std}(IC_t)}
\]

经验上，日频股票横截面 IC：

\[
0.02 \sim 0.05
\]

已经算不错。

如果 IC 过高，需要警惕数据泄漏。

---

## 6.2 分层组合

按照预测值将股票分成十档：

```text
Decile 1: 预测最差
...
Decile 10: 预测最好
```

检查：

- 高分组是否比低分组收益更高；
- 收益是否单调；
- top-bottom spread 是否稳定。

Top-bottom 收益：

\[
R^{LS}_t
=
R^{Top}_t
-
R^{Bottom}_t
\]

---

## 6.3 回测设计

### 多空组合

做多预测最高的一档，做空预测最低的一档：

\[
w_i > 0
\quad \text{for top-ranked stocks}
\]

\[
w_i < 0
\quad \text{for bottom-ranked stocks}
\]

组合可以保持市场中性：

\[
\sum_i w_i = 0
\]

---

### 交易滞后一天执行

为避免前视偏差：

```text
t 日收盘计算信号
t+1 日建仓
```

不能在 \(t\) 日用 \(t\) 日收盘价计算信号后，又假设在同一个收盘价成交。

---

### 交易成本

交易成本要按换手率扣除。

换手率：

\[
\text{Turnover}_t
=
\sum_i
|w_{i,t} - w_{i,t-1}|
\]

扣费后收益：

\[
R^{net}_t
=
R^{gross}_t
-
c \cdot \text{Turnover}_t
\]

其中 \(c\) 是单边交易成本，例如：

\[
c = 5 \sim 10 \text{ bps}
\]

---

## 6.4 回测指标

### 年化收益

\[
R_{ann}
=
(1+\bar{R}_{daily})^{252} - 1
\]

### 年化波动

\[
\sigma_{ann}
=
\sigma_{daily}
\sqrt{252}
\]

### Sharpe Ratio

\[
Sharpe
=
\frac{R_{ann}}{\sigma_{ann}}
\]

或者用日收益近似：

\[
Sharpe
=
\frac{\text{mean}(R_t)}{\text{std}(R_t)}
\sqrt{252}
\]

### 最大回撤

\[
MDD
=
\max_t
\left(
\frac{\text{Peak}_t - \text{Wealth}_t}{\text{Peak}_t}
\right)
\]

---

## 6.5 稳健性与体制依赖

不要只给总结果，还应该分阶段检验。

可以检查：

| 阶段 | 作用 |
|---|---|
| 2008 | 金融危机 |
| 2020 | COVID 冲击 |
| 2022 | 加息熊市 |
| 2023–2024 | 科技股集中行情 |

评估：

- 分阶段 IC；
- 分阶段 Sharpe；
- 滚动 IC；
- 滚动 Sharpe。

如果信号只在某类市场中有效，要诚实说明。

---

# 7. 需要在报告里讨论的关键问题

| 问题 | 处理方式 |
|---|---|
| 前视偏差 look-ahead bias | 因子只用 \(t\) 及以前数据；交易滞后一天；验证集 purge + embargo |
| 幸存者偏差 survivorship bias | 承认数据只含现存 S&P 500 成分股，说明收益可能被高估 |
| 过拟合 overfitting | 由简到繁建模；正则化；early stopping；只看样本外 |
| 换手率 / 市场冲击 turnover / market impact | 统计换手率，扣除交易成本，展示扣费后 Sharpe |
| 体制依赖 regime dependence | 分阶段评估，画滚动 IC / Sharpe |
| 数据质量 data quality | winsorize、最小历史要求、流动性过滤 |
| 经济直觉 economic intuition | 每个因子配解释，避免纯数据挖掘 |

---

# 8. 量化入门总览

整个量化研究流程可以概括为：

```text
原始数据
→ 数据清洗
→ 构造因子
→ 定义预测目标
→ 切分样本
→ 训练模型
→ 验证选模型
→ 构建组合
→ 回测评估
→ 讨论偏差与风险
```

---

## 8.1 量化交易在赌什么？

量化交易的本质是：

> 用数据和数学，按固定规则找到一点点比随机更准的优势，然后通过大量交易和分散化，把小优势累积成稳定收益。

类比：

> 赌场庄家每一把只比玩家多一点点胜率，但次数足够多，优势会稳定体现出来。

量化交易追求的就是：

\[
\text{Small Edge} \times \text{Many Bets} \rightarrow \text{Stable Return}
\]

---

## 8.2 Systematic vs Discretionary

| 术语 | 中文 | 含义 |
|---|---|---|
| Systematic | 系统化交易 | 按可重复规则交易 |
| Discretionary | 主观交易 | 靠交易员判断交易 |

本项目属于 systematic quantitative research。

---

# 9. 术语解释

## 9.1 OHLCV

| 术语 | 中文 | 解释 |
|---|---|---|
| Open | 开盘价 | 当天第一笔或开盘形成的价格 |
| High | 最高价 | 当天最高成交价 |
| Low | 最低价 | 当天最低成交价 |
| Close | 收盘价 | 当天收盘价 |
| Volume | 成交量 | 当天成交股数 |
| Adj Close | 复权收盘价 | 调整分红和拆股后的价格 |

---

## 9.2 Return 收益率

收益率：

\[
r_t
=
\frac{P_t}{P_{t-1}} - 1
\]

相比价格，收益率更适合建模。

---

## 9.3 Alpha 与 Beta

### Beta

Beta 表示股票跟随市场共同涨跌的部分。

如果市场涨 \(1\%\)，股票平均涨 \(\beta\%\)，则该股票 beta 为 \(\beta\)。

### Alpha

Alpha 是剥离市场共同影响后，股票自己的超额表现。

量化研究真正想找的是：

\[
\alpha
\]

不是简单预测大盘涨跌。

---

## 9.4 Factor / Signal 因子 / 信号

因子是从原始数据中计算出来、可能预测未来收益的变量。

例子：

- 过去一年收益；
- RSI；
- 波动率；
- 成交量变化；
- MACD。

---

## 9.5 Cross-sectional 横截面

固定某一天，比较所有股票。

例如：

```text
2024-01-02 这一天，把 500 只股票按动量排序。
```

本项目主要做横截面预测：

> 在同一天里预测哪些股票会跑赢其他股票。

---

## 9.6 Time-series 时间序列

盯着一只股票，看它随时间的变化。

例如：

```text
AAPL 从 2000 年到 2025 年的价格走势。
```

---

## 9.7 In-sample / Out-of-sample

| 术语 | 中文 | 含义 |
|---|---|---|
| In-sample | 样本内 | 用来训练或调参的数据 |
| Out-of-sample | 样本外 | 模型没见过、用于最终检验的数据 |

核心原则：

> 样本外结果才可信。

---

## 9.8 Overfitting 过拟合

过拟合是指模型把历史中的随机噪声也学进去了。

表现：

```text
样本内很好
样本外很差
```

防止方法：

- 简单模型优先；
- 正则化；
- early stopping；
- 严格样本外验证；
- 不在测试集上调参。

---

## 9.9 Look-ahead Bias 前视偏差

前视偏差是指：

> 使用了当时不可能知道的未来信息。

例子：

- 用未来收益构造当前因子；
- 用 \(t\) 日收盘价算信号，又假设在 \(t\) 日收盘成交；
- 训练标签窗口跨入验证集。

防止方法：

- 因子只用 \(t\) 及以前数据；
- 交易滞后一天；
- 使用 purge / embargo。

---

## 9.10 Survivorship Bias 幸存者偏差

幸存者偏差是指数据只包含“活到现在”的股票，忽略历史上失败、退市、被剔除的股票。

结果：

> 回测收益可能偏高。

---

## 9.11 Regime Dependence 体制依赖

信号只在某些市场环境下有效。

例如：

- 牛市有效；
- 熊市失效；
- 高利率环境失效；
- 危机期表现反转。

需要用分阶段回测和滚动指标检查。

---

## 9.12 Economic Intuition 经济直觉

每个因子背后都应该有合理解释。

例如：

- 动量：投资者反应不足；
- 反转：短期流动性冲击修复；
- 低波动：杠杆约束导致低波股被低估；
- 流动性：流动性差要求更高补偿。

没有经济直觉的因子，容易只是数据挖掘结果。

---

# 10. 报告结构建议

10 页报告可以这样安排：

| 页数 | 内容 |
|---|---|
| 1 | 项目目标、数据、核心思想 |
| 2 | 数据清洗与偏差说明 |
| 3 | 目标定义：未来 5 日相对收益 |
| 4 | 因子工程与经济直觉 |
| 5 | Walk-forward + purge/embargo 验证框架 |
| 6 | 模型：baseline、Ridge、LightGBM / XGBoost、MLP |
| 7 | 预测评估：IC、ICIR、分层组合 |
| 8 | 回测设计：多空组合、滞后执行、交易成本 |
| 9 | 稳健性：分阶段表现、滚动 IC / Sharpe |
| 10 | 局限性、偏差、结论 |

---

# 11. 报告中可直接使用的英文段落

## 11.1 Validation Framework

> I adopt an expanding walk-forward validation framework with purging and embargo. Each fold trains the model using only past data and evaluates it on a future validation block. Since the target is a forward \(h\)-day relative return, I purge training samples near the validation boundary whose label horizon overlaps with the validation period. This prevents label leakage and look-ahead bias. I also apply an embargo period after each validation block to reduce potential information leakage caused by serial dependence in financial time series. After model and hyperparameter selection, I reserve a final untouched hold-out period for the final out-of-sample backtest.

---

## 11.2 Relative Return Target

> Instead of predicting raw stock returns, I focus on cross-sectional relative returns. Raw returns are dominated by market-wide movements, which are difficult to predict and less useful for constructing an alpha signal. I therefore define the target as the stock's future \(h\)-day return minus the contemporaneous average return of its sector or the full universe. This formulation removes common market or industry effects and aligns the prediction task with a market-neutral long-short portfolio.

---

## 11.3 Bias and Robustness

> I explicitly consider several sources of bias and overfitting. Features are constructed only from information available up to the prediction date, and trades are executed with a one-day lag to avoid look-ahead bias. Since the dataset only contains current S&P 500 constituents, survivorship bias may lead to an upward-biased estimate of performance. I report both gross and transaction-cost-adjusted results, and evaluate the signal across different market regimes to assess robustness.

---

# 12. 总结

这个项目考的核心不是模型复杂度，而是量化研究的基本纪律：

\[
\boxed{
\text{有经济逻辑的因子}
+
\text{严格样本外验证}
+
\text{防泄漏}
+
\text{扣交易成本}
+
\text{诚实讨论偏差}
}
\]

一个合理的最终方案是：

\[
\boxed{
\text{5 日未来相对收益}
+
\text{横截面因子}
+
\text{Ridge / LightGBM / MLP 对比}
+
\text{Walk-forward + Purge / Embargo}
+
\text{市场中性多空回测}
}
\]

比起堆很多复杂模型，更重要的是建立一个经得起推敲的研究流程。
