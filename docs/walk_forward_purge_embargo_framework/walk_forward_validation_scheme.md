# Walk-forward Validation Scheme for Stock Return Prediction

## 1. Motivation

For this project, the objective is to predict future relative stock returns and evaluate the resulting trading signal through out-of-sample testing and backtesting. A simple static train-validation-test split is easy to implement, but it is not ideal for financial time-series prediction because market regimes change over time and the model should be evaluated in a way that resembles real trading deployment.

Therefore, I use an **expanding walk-forward validation framework with purging and a final hold-out test set**.

The recommended structure is:

\[
\boxed{
\text{Expanding Walk-forward Validation} + \text{Purging} + \text{Final Hold-out Test}
}
\]

---

## 2. Why Not Use Only a Static Train/Validation/Test Split?

A direct split may look like this:

```text
Train:      2000-2018
Validation: 2019-2021
Test:       2022-2025
```

This setup is simple, but it has several weaknesses:

1. **Only one market regime is used for validation**

   If the validation period happens to favor a certain signal, the model may look stronger than it really is.

2. **Model selection can become unstable**

   A model selected on one validation block may not generalize across different market environments.

3. **Financial data are non-stationary**

   Stock return patterns may change across bull markets, bear markets, crisis periods, high-rate environments, and low-rate environments.

4. **It does not fully reflect real trading workflow**

   In real trading, the model is usually trained using historical data, tested on future unseen data, and then periodically updated as new data arrive.

Because of these issues, a static split can be used as a simple baseline, but it should not be the main validation method.

---

## 3. Main Choice: Expanding Walk-forward Validation

The preferred approach is **expanding walk-forward validation**.

The idea is:

```text
Use past data to train the model
→ validate on the next future period
→ test on the following unseen period
→ expand the training window
→ repeat
```

Example structure:

```text
Fold 1:
Train:      2005-2014
Validation: 2015
Test:       2016

Fold 2:
Train:      2005-2015
Validation: 2016
Test:       2017

Fold 3:
Train:      2005-2016
Validation: 2017
Test:       2018

Fold 4:
Train:      2005-2017
Validation: 2018
Test:       2019

...
```

This structure has several advantages:

- It respects the chronological order of the data.
- It avoids using future information for model training.
- It evaluates the model across multiple market regimes.
- It gives a more reliable estimate of out-of-sample performance.
- It is close to how a trading signal would be developed and updated in practice.

---

## 4. Expanding Window vs Rolling Window

There are two common walk-forward choices:

### 4.1 Expanding Window

The training set grows over time:

```text
Fold 1 train: 2005-2014
Fold 2 train: 2005-2015
Fold 3 train: 2005-2016
```

Advantages:

- Uses more historical data.
- More stable for machine learning models.
- Easier to explain in a project report.
- Suitable for daily S&P 500 data with a long history.

### 4.2 Rolling Window

The training set keeps a fixed length:

```text
Fold 1 train: 2005-2014
Fold 2 train: 2006-2015
Fold 3 train: 2007-2016
```

Advantages:

- More adaptive to recent regimes.
- Reduces the effect of very old data.

Disadvantages:

- May discard useful long-term information.
- More sensitive to the choice of window length.

### 4.3 Recommended Choice

For this project, I recommend using the **expanding window** as the main validation design.

Reason:

- The dataset contains more than 20 years of daily stock data.
- The project is a take-home research case study, so the method should be robust and easy to justify.
- Expanding windows are stable and suitable for comparing feature sets and models.
- The report can still discuss rolling windows as a possible robustness check.

---

## 5. Purging Around Split Boundaries

If the target is a future \(h\)-day return, the label for sample \(t\) uses future prices.

For example, for a 5-day forward return:

\[
y_t = \frac{P_{t+5}}{P_t} - 1
\]

This means that a sample near the boundary between training and validation may use validation-period prices to construct its label.

Example:

```text
Train period ends: 2022-12-31
Validation starts: 2023-01-01

Sample date: 2022-12-29
Label uses price at: 2023-01-05
```

Although the feature date is inside the training period, the label uses information from the validation period. This creates **label leakage** and **look-ahead bias**.

Therefore, samples whose label horizon overlaps with the validation or test period should be removed from the training set.

The purging rule is:

\[
t + h > T_{\text{train end}}
\]

If this condition holds, the training sample should be removed.

For a 5-day forward return:

```text
Safe sample:
Feature date: t
Label window: t to t+5
Label end remains inside training period
→ keep

Unsafe sample:
Feature date: t
Label window: t to t+5
Label end falls into validation or test period
→ remove
```

---

## 6. Final Hold-out Test Set

Walk-forward validation is useful for model selection and stability analysis, but it is still useful to reserve a final untouched test period.

A practical design is:

```text
2005-2020:
Walk-forward validation and model selection

2021-2024:
Walk-forward out-of-sample backtest

2025-now:
Final untouched hold-out test
```

Or, if the dataset ends earlier, the final available year can be used as the final hold-out period.

The final hold-out test should only be used once after all modeling decisions are fixed.

This gives a cleaner final performance estimate.

---

## 7. Recommended Full Workflow

The full workflow is:

1. Construct features using only information available up to date \(t\).
2. Define the target as future relative return over horizon \(h\), for example:

   \[
   y_{i,t} = r_{i,t:t+h} - \text{median}_{j \in G(i)} r_{j,t:t+h}
   \]

   where \(G(i)\) can be the stock's sector, industry group, or the full universe.

3. Build expanding walk-forward folds.
4. For each fold:
   - Train the model on the training window.
   - Purge boundary samples whose label horizon overlaps with validation or test.
   - Tune hyperparameters using the validation window.
   - Evaluate the selected model on the test window.
5. Aggregate results across all test windows.
6. Report:
   - Cross-sectional IC / Rank IC
   - Long-short portfolio return
   - Sharpe ratio
   - Max drawdown
   - Turnover
   - Hit rate
   - Performance by year or regime
7. Evaluate the final selected model on the untouched hold-out test period.

---

## 8. Example Data Split

A clean example is:

```text
Fold 1:
Train:      2005-2014
Validation: 2015
Test:       2016

Fold 2:
Train:      2005-2015
Validation: 2016
Test:       2017

Fold 3:
Train:      2005-2016
Validation: 2017
Test:       2018

Fold 4:
Train:      2005-2017
Validation: 2018
Test:       2019

Fold 5:
Train:      2005-2018
Validation: 2019
Test:       2020

Fold 6:
Train:      2005-2019
Validation: 2020
Test:       2021

Fold 7:
Train:      2005-2020
Validation: 2021
Test:       2022

Fold 8:
Train:      2005-2021
Validation: 2022
Test:       2023

Fold 9:
Train:      2005-2022
Validation: 2023
Test:       2024
```

Then reserve:

```text
Final hold-out:
2025-now
```

If the available data period is shorter, the same logic can be applied with fewer folds.

---

## 9. Report-ready English Description

The following paragraph can be used directly in the project report:

> I use an expanding walk-forward validation framework rather than a single static train-validation-test split. This setup better reflects the real trading workflow, where models are repeatedly trained on past data and evaluated on future unseen periods. Since the prediction target is a forward \(h\)-day relative return, I purge samples near split boundaries whose label horizon overlaps with the validation or test period. This avoids look-ahead bias and label leakage. Model selection is performed using validation windows across multiple walk-forward folds, while the final performance is reported on out-of-sample test windows and an untouched final hold-out period.

---

## 10. Conclusion

For this project, the recommended validation design is:

\[
\boxed{
\text{Expanding Walk-forward Validation} + \text{Purging} + \text{Final Hold-out Test}
}
\]

A direct static split is simple, but it is weaker for financial prediction because it only tests one time period and may not capture regime dependence. Walk-forward validation gives a more realistic and more reliable estimate of whether the signal has stable predictive power across time.
