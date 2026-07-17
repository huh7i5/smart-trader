# Baseline DCA + Checklist Booster Strategy Specification

This document defines the combined strategy framework that merges **Option 1 (Baseline DCA)** and **Option 3 (Multi-Asset Confluence)** with our **Checklist & Sentiment/Momentum dynamic booster**. 

---

## 1. Core Architecture: The "Shield & Spear" Model

To solve the conflict between **high precision (low drawdown)** and **sufficient accumulation (total volume)**, the system splits capital deployment into two distinct modes:

```
                          ┌────────────────────────┐
                          │     Total Capital      │
                          └───────────┬────────────┘
                                      │
             ┌────────────────────────┴────────────────────────┐
             ▼                                                 ▼
┌─────────────────────────┐                       ┌─────────────────────────┐
│  Weekly Baseline DCA    │                       │  Dynamic Checklist      │
│  (The Shield - 定投防守) │                       │  Booster (The Spear)    │
└────────────┬────────────┘                       └────────────┬────────────┘
             │                                                 │
   Creates Weekly Proposal                              Executes Only If:
   (BTC 45%, SOL 35%, LINK 20%)                       1. 3-Point Checklist = 🟢🟢🟢
   Small ticket size (e.g., $30)                      2. F&G <= 15 or RSI <= 25 (Model 1)
   50% Market / 50% ATR-Limit                         3. RSI crossback/div (Model 2/3)
                                                      Scales size dynamically (0.5x - 3.0x)
```

1.  **The Shield (Baseline DCA):** Creates a small weekly proposal regardless of checklist filters (unless extreme black swan halts are active). It never submits a live order automatically. **This mode is explicitly exempt from Rule 6 (One-Red-Stop)**, but still requires code risk checks and separate user confirmation.
2.  **The Spear (Checklist Booster):** Executes dynamically when market capitulations occur, using our optimized WFA parameters to place heavy buy orders at deep cycle bottoms. **This mode is NEVER exempt from Rule 6** — all 3 checklist lights must be green (🟢🟢🟢) before the Spear fires.

---

## 2. Execution Logic

### 2.1. Weekly Baseline DCA (The Shield)
*   **Trigger:** A scheduler may create a preview every Monday at 08:00 UTC. It must not confirm or submit the order.
*   **Base Budget:** Small size (e.g., $30 to $50 total).
*   **Asset Allocation:**
    *   BTC/USDT: 45%
    *   SOL/USDT: 35%
    *   LINK/USDT: 20%
*   **Execution Method:**
    *   **50% Market Buy Proposal:** Proposed at the current price and submitted only after confirmation.
    *   **50% ATR-based Limit Buy:** Placed at `Current Price - K * ATR(14)` (where $K = 2.0$ for BTC, $2.5$ for SOL/LINK) to secure a local discount. Unfilled limit orders expire and are cancelled after 24 hours.

### 2.2. Checklist Booster (The Spear)
*   **Trigger:** Daily scan of core assets. Fires only if **Checklist Enforced == Green (🟢🟢🟢)** AND any of the following triggers occur:
    *   **Model 1 (Sentiment DCA):** F&G index $\le 15$ OR Daily RSI $\le 25$.
    *   **Model 2 (Momentum Sniper):** Daily/4h RSI crosses back above 30 from oversold, or bullish divergence confirmed.
    *   **Model 3 (Volatility Dip Buyer):** Low price drops below lower Bollinger Band ($Middle - 2.0\sigma$) while F&G $\le 35$.
*   **Booster Budget:** Scaled up dynamically based on sentiment multiplier:
    $$Budget_{booster} = Base\_Budget \times M_t$$
    Where $M_t \in [0.5, 3.0]$ is determined by F&G and RSI (Model 1 modifier).
*   **Execution Method:**
    *   100% placed as limit orders at calculated support levels (recent lows or ATR spacing) to capture the wick.

---

## 3. Parameter Matrix for Core Assets

| Asset | Baseline Pct | ATR Limit Multiplier ($K$) | Target Support Levels for Booster |
| :--- | :---: | :---: | :--- |
| **BTC/USDT** | 45% | $2.0 \times ATR$ | Recent 1h Low / Daily MA200 |
| **SOL/USDT** | 35% | $2.5 \times ATR$ | Recent 4h Low / Daily EMA50 |
| **LINK/USDT** | 20% | $2.5 \times ATR$ | Recent 4h Low / Historical Support |

---

## 4. Guarded Script Integration

Use the bundled order scripts rather than an external execution engine:

1. Run `buy_limit.py SYMBOL PRICE AMOUNT --mode baseline` to create a baseline preview.
2. Run the normal three-point workflow before an active or booster preview.
3. Show the proposal to the user and wait for a separate explicit confirmation.
4. Submit the unchanged command with `--confirm PROPOSAL_TOKEN` only after confirmation.
5. Let schedulers create evidence and previews only. Never let a scheduler consume a proposal token.
