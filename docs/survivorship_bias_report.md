# S&P 500 数据幸存者偏差与建模影响报告

日期：2026-06-19

## 1. 背景

当前项目使用的数据主要来自：

- `data/raw/sp500_stocks.csv`
- `data/raw/sp500_companies.csv`

`sp500_stocks.csv` 的核心字段为：

```text
date, open, high, low, close, volume, symbol
```

该数据覆盖约 503 个 symbol，日期范围约为 2000-01-03 至 2026-06-16。数据本身在 OHLCV 层面较完整，未发现核心价格列缺失或 `symbol/date` 重复。

需要特别注意的是，这份数据更像是“当前或近期 S&P 500 成分股的历史价格数据”，而不是“每个历史日期真实的 S&P 500 成分股名单”。因此，它可能存在明显的 survivorship bias，中文通常称为幸存者偏差。

## 2. 什么是幸存者偏差

幸存者偏差指的是：样本中只保留了后来仍然存在、仍然表现较好、仍然在指数中或仍然能被数据源追踪的公司，而遗漏了历史上曾经存在但后来破产、退市、被并购、被剔除或严重衰落的公司。

对于当前数据，这意味着：

```text
2005 年的回测股票池里，可能使用的是 2026 年仍然存在的 S&P 500 公司名单。
```

真实情况下，2005 年的投资者并不知道哪些公司会在未来存活下来。因此，如果历史回测只包含后来的幸存公司，就会隐含使用未来信息。

## 3. 当前数据可能遗漏的历史公司

以下是一些历史上曾经属于或接近 S&P 500 大盘股范围，但后来破产、退市、被并购或被剔除的典型公司。它们在当前 `sp500_stocks.csv` 的 symbol 列中通常不存在，或存在 ticker 歧义。

| 公司 | 历史 ticker | 事件类型 | 对当前数据的含义 |
|---|---:|---|---|
| Enron | ENE | 会计丑闻、破产 | 不在当前数据中 |
| WorldCom / MCI | WCOM / MCIP | 会计丑闻、破产、后续并购 | 不在当前数据中 |
| Lehman Brothers | LEH | 2008 年破产 | 不在当前数据中 |
| Bear Stearns | BSC | 2008 年被 JPMorgan 收购 | 不在当前数据中 |
| Washington Mutual | WM | 2008 年倒闭，银行业务被接收 | 当前数据中的 `WM` 是 Waste Management，不是 WaMu |
| Fannie Mae | FNM | 2008 年被政府接管 | 不在当前数据中 |
| Freddie Mac | FRE | 2008 年被政府接管 | 不在当前数据中 |
| Countrywide Financial | CFC | 次贷危机中被 Bank of America 收购 | 不在当前数据中 |
| Eastman Kodak | EK / KODK | 被剔除，后破产重组 | 不在当前数据中 |
| Sears Holdings | SHLD | 长期衰落，后破产 | 不在当前数据中 |
| RadioShack | RSH | 长期衰落，后破产 | 不在当前数据中 |
| J.C. Penney | JCP | 长期衰落，后破产/退市 | 不在当前数据中 |
| Yahoo | YHOO | 被 Verizon 收购核心业务 | 不在当前数据中 |
| Whole Foods | WFM | 被 Amazon 收购 | 不在当前数据中 |
| Tiffany | TIF | 被 LVMH 收购 | 不在当前数据中 |
| Celgene | CELG | 被 Bristol Myers Squibb 收购 | 不在当前数据中 |
| Allergan | AGN | 被 AbbVie 收购 | 不在当前数据中 |
| Anadarko Petroleum | APC | 被 Occidental 收购 | 不在当前数据中 |
| Red Hat | RHT | 被 IBM 收购 | 不在当前数据中 |
| Xilinx | XLNX | 被 AMD 收购 | 不在当前数据中 |

这些公司并不全是“差公司”。有些是因为被高价收购而消失，有些是因为业务衰退、财务危机或破产而消失。对回测而言，两类都重要，因为真实历史股票池应当包含当时可以买到的公司，而不是只包含后来仍然在样本中的公司。

## 4. 对 LightGBM、树模型和其他模型的影响

幸存者偏差不是由模型类型造成的。因此，使用 LightGBM、XGBoost、Random Forest、线性模型、神经网络或 Kronos，都不会自动消除这个问题。

问题的根源是：

```text
训练集和测试集的股票池已经被未来结果筛选过。
```

如果股票池只包含当前幸存公司，模型就没有学习到那些最终退市、破产、被剔除公司的风险模式。回测时，它也天然避开了这些公司。

因此，即使使用 LGBM，也会出现以下风险：

- 高估预测信号的稳定性。
- 高估 long-only top-K 策略收益。
- 低估最大回撤。
- 低估退市、破产、极端下跌带来的尾部风险。
- 对 2000-2026 这种长周期历史回测产生过度乐观结论。

## 5. 什么时候可以继续使用当前数据

当前数据仍然有研究价值。它可以用于以下目的：

1. 训练或微调模型，让模型学习美股大盘股日线 OHLCV 模式。
2. 比较不同模型在同一幸存股票池上的相对表现，例如 LGBM vs Kronos。
3. 研究当前 S&P 500 公司历史价格行为中的可预测性。
4. 做模型工程、特征工程、训练流程、评估流程的验证。
5. 作为初步实验数据，判断某类方法是否值得进一步投入。

但结论应限定为：

```text
当前或近期 S&P 500 成分股历史样本上的预测实验。
```

不应直接表述为：

```text
真实历史 S&P 500 成分股上的可交易策略回测。
```

## 6. 什么时候问题会很严重

以下场景中，幸存者偏差会严重影响结论：

1. 声称策略在 2000-2026 年真实 S&P 500 股票池上有效。
2. 报告长期年化收益率、Sharpe、最大回撤，并把它解释为真实可交易结果。
3. 做 long-only top-K 策略，因为只买幸存股票通常会明显抬高收益。
4. 研究金融危机、破产风险、信用风险、极端下跌风险。
5. 比较“是否能避开失败公司”，但数据中失败公司本身已经被删掉。

## 7. 对当前项目的建议

短期可以继续使用当前数据，但应把它定位为模型研究数据，而不是严格投资回测数据。

建议当前阶段采用以下表述：

```text
This experiment uses historical prices of current or recent S&P 500 constituents.
The dataset is subject to survivorship bias and should not be interpreted as a
fully tradable point-in-time S&P 500 backtest.
```

建模上，建议保留 LGBM 作为强基线模型：

```text
features at date t -> future return at t+1 / t+5 / t+20
```

主要评估指标建议使用：

- daily cross-sectional RankIC
- RankIC information ratio
- 分层收益
- top-bottom spread
- 方向准确率
- 交易成本后的组合收益
- 按年份和市场状态分组的稳定性

报告时应避免只展示累计收益曲线。累计收益在幸存者偏差数据上最容易显得过度乐观。

## 8. 更严格的解决方案

如果后续目标是做严谨的历史可交易策略，需要引入 point-in-time universe，即每个日期当时真实存在、真实属于 S&P 500 或可交易股票池的公司名单。

更严谨的数据应包含：

- 历史每日 S&P 500 成分股名单。
- 被剔除公司。
- 退市公司。
- 被并购公司。
- delisting return 或退市处理逻辑。
- 公司行为调整，例如拆股、分红、并购、ticker 变更。
- 当时可得的行业分类和财务数据，避免 look-ahead bias。

常见专业数据源包括 CRSP、Compustat、WRDS、Bloomberg、Refinitiv 等。开源或免费数据也可以使用，但需要额外处理历史成分股和退市样本。

## 9. 结论

当前数据可以用于 LGBM、Kronos 或其他模型的初步预测实验和方法比较，但不能直接支持“真实历史 S&P 500 策略收益”的强结论。

模型类型不是核心问题。即使用 LGBM，幸存者偏差仍然存在。核心问题是股票池定义是否 point-in-time，以及是否包含历史上消失的公司。

因此，本项目当前阶段推荐的研究定位是：

```text
在当前或近期 S&P 500 成分股历史样本上，评估不同模型对未来收益排序的预测能力。
```

而不是：

```text
构建并验证一个已经消除幸存者偏差的真实历史 S&P 500 可交易策略。
```

## 10. 参考资料

- S&P 500 成分股及历史变更说明：https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
- CRSP survivor-bias-free 数据说明：https://www.crsp.org/research/crsp-survivor-bias-free-us-mutual-funds/
- Shumway, Tyler. "The Delisting Bias in CRSP Data." Journal of Finance, 1997.
- FDIC 关于 Washington Mutual 的历史资料：https://archive.fdic.gov/view/fdic/3396
- FHFA 关于 Fannie Mae 和 Freddie Mac conservatorship 的历史资料：https://www.fhfa.gov/conservatorship/history
