---
name: crypto-smart-trader
description: >-
  Cryptocurrency and bStock (tokenized US stocks) spot trading system with
  smart money tracking, fund flow analysis, and strict discipline rules.
  Designed for small retail investors ($1K-$10K) on Binance spot market.
  Use when the user asks to check portfolio, analyze fund flows, place trades,
  check smart money signals, run pre-trade checklist, manage positions, or
  asks about crypto/stock trading strategy. Trigger phrases include:
  "check portfolio", "fund flow", "smart money", "buy BTC", "sell position",
  "pre-trade check", "交易前检查", "查看持仓", "资金流向", "聪明钱",
  "买入", "卖出", "挂单", "定投计划", "仓位管理", "止损", "止盈".
---

# Crypto Smart Trader

A disciplined, data-driven trading system for cryptocurrency and bStock (Binance tokenized US stocks) spot markets. Built around a **3-Point Pre-Trade Checklist** that combines smart money analysis, retail behavior tracking, and macro event awareness to ensure every trade decision is backed by evidence — not emotion.

> [!CAUTION]
> ## Disclaimer
> This skill is for **educational and informational purposes only**. It does NOT constitute financial advice. Cryptocurrency and stock trading involves substantial risk of loss. Never invest more than you can afford to lose.

## When to use

- User wants to check their current portfolio holdings and P&L
- User asks about current market prices or trends
- User wants to analyze fund flows (smart money vs retail)
- User wants to place a buy or sell order on Binance
- User asks about position sizing or risk management
- User wants to run a pre-trade checklist before making a decision
- User is planning a DCA (dollar cost averaging) strategy
- User asks about macro events (CPI, FOMC, earnings) impact on trades

## When NOT to use

- Futures or leverage trading (this skill is spot-only)
- DeFi protocols, yield farming, or liquidity pools
- NFT trading or minting
- Tax preparation or accounting (consult a professional)
- Automated bot trading (this is a manual decision-support system)

## Related files

| File | Open when |
|------|-----------|
| [references/trading_rules.md](references/trading_rules.md) | User asks about trading discipline, rules, or risk management |
| [references/position_sizing.md](references/position_sizing.md) | User asks about how much to invest, batch sizing, or DCA planning |
| [references/smart_money_signals.md](references/smart_money_signals.md) | User asks about smart money, whale activity, or fund flow interpretation |
| [references/macro_calendar.md](references/macro_calendar.md) | User asks about upcoming events (CPI, FOMC, earnings) or when to trade |
| [references/star_rating_guide.md](references/star_rating_guide.md) | User asks about conviction score star ratings, scores, or buy timing recommendations |
| [examples/dca_plan_example.md](examples/dca_plan_example.md) | User wants a concrete DCA plan template |
| [examples/pre_trade_report_example.md](examples/pre_trade_report_example.md) | User wants to see what a pre-trade report looks like |

## Pre-Trade Checklist (The 3-Point Check)

**This is the core methodology. Before EVERY trade, run all 3 checks. Only proceed when all pass (🟢🟢🟢).**

### ① Smart Money Direction

Check what institutional investors and whales are doing:

- **ETF fund flows**: Are Bitcoin/Ethereum ETFs seeing net inflows or outflows this week?
- **Whale accumulation**: Are large holders (>1000 BTC) adding to positions?
- **Exchange reserves**: Are coins leaving exchanges (bullish) or entering (bearish)?

Run: `python ${SKILL_DIR}/scripts/check_fund_flow.py --hours 24`

### ② Retail Behavior

Analyze what small traders are doing in the short term:

- **Taker buy/sell volume**: Is retail net buying or selling in the last 6 hours?
- **Order book depth**: Is the bid wall bigger than the ask wall?
- **Key signal**: Retail selling + price stable = smart money absorbing (bottom signal)

Run: `python ${SKILL_DIR}/scripts/check_fund_flow.py --hours 6`

### ③ Macro Events

Check the economic calendar for upcoming volatility triggers:

- **Within 24 hours**: CPI, FOMC, jobs data → DO NOT TRADE
- **Within 48 hours**: Earnings, IPOs → PROCEED WITH CAUTION
- **Clear calendar**: SAFE TO TRADE

Run: `python ${SKILL_DIR}/scripts/pre_trade_checklist.py`

### Decision Matrix

| ① Smart Money | ② Retail | ③ Macro | Decision |
|:---:|:---:|:---:|:---|
| 🟢 | 🟢 | 🟢 | ✅ Execute trade |
| 🟢 | 🟢 | 🔴 | ⏸️ Wait for event to pass |
| 🟢 | 🔴 | 🟢 | ✅ Execute (retail panic = opportunity) |
| 🔴 | 🟢 | 🟢 | ⏸️ Wait for smart money confirmation |
| 🔴 | 🔴 | 🔴 | ❌ Absolutely do not trade |

## Trading Discipline (5 Iron Rules)

1. **Never sell core positions in panic** — Bottom is where you feel most scared. If the thesis hasn't changed, the position stays.
2. **Never chase pumps** — If an asset has risen >5% today, do NOT buy. Wait for a pullback or next entry opportunity.
3. **Wait for confirmation** — Before major data releases (CPI, FOMC), do NOT place new orders. Wait for the data, then decide.
4. **Cap each trade at 6-12% of capital** — Maximum $50-$100 per single trade for a $1,000 account. Spread entries across multiple tranches.
5. **Always maintain 30%+ cash reserve** — Cash is ammunition. Without it, you can't capitalize on crashes. Never go all-in.

## Workflow

### Step 1 · Check Current Portfolio

Run the portfolio checker to see current holdings, open orders, and account value:

```bash
python ${SKILL_DIR}/scripts/check_portfolio.py
```

### Step 2 · Run Pre-Trade Checklist

Before any trade decision, run the automated 3-point check:

```bash
python ${SKILL_DIR}/scripts/pre_trade_checklist.py --symbol BTC/USDT
```

### Step 3 · Analyze Fund Flows

Get detailed fund flow data to understand market dynamics:

```bash
python ${SKILL_DIR}/scripts/check_fund_flow.py --hours 6
```

### Step 4 · Execute Trade (User Confirmation Required)

**Always confirm with the user before executing.** Present the trade details and wait for explicit "execute" command.

```bash
# Market buy
python ${SKILL_DIR}/scripts/buy_market.py BTC 50

# Limit buy
python ${SKILL_DIR}/scripts/buy_limit.py BTC 58800 50

# Market sell
python ${SKILL_DIR}/scripts/sell_market.py DRAMB --all
```

### Step 5 · Verify Execution

After any trade, re-run the portfolio checker to confirm the order was filled:

```bash
python ${SKILL_DIR}/scripts/check_portfolio.py
```

## Position Sizing Quick Reference

| Account Size | Max Per Trade | Cash Reserve | Tranches |
|:---:|:---:|:---:|:---:|
| $1,000 | $50-$100 | $300+ | 3-4 batches |
| $5,000 | $250-$500 | $1,500+ | 4-5 batches |
| $10,000 | $500-$1,000 | $3,000+ | 5-6 batches |

## Available Scripts

| Script | Purpose |
|--------|---------|
| `${SKILL_DIR}/scripts/check_portfolio.py` | View holdings, P&L, open orders |
| `${SKILL_DIR}/scripts/check_prices.py` | Real-time price monitoring |
| `${SKILL_DIR}/scripts/check_fund_flow.py` | Short-term fund flow analysis |
| `${SKILL_DIR}/scripts/pre_trade_checklist.py` | Automated 3-point pre-trade check |
| `${SKILL_DIR}/scripts/buy_market.py` | Execute market buy orders |
| `${SKILL_DIR}/scripts/buy_limit.py` | Place limit buy orders |
| `${SKILL_DIR}/scripts/sell_market.py` | Execute market sell orders |
| `${SKILL_DIR}/scripts/cancel_order.py` | Cancel open orders |

## Output Format

### Portfolio Report
```
CURRENT HOLDINGS & VALUE
  BTC      qty=0.00693  price=65348.00  value=452.85 USDT
  SOL      qty=3.397    price=78.09     value=265.28 USDT
  USDT: free=$759.86 | locked=$49.98 | total=$809.84
  Total account: ~1777.00 USDT
```

### Pre-Trade Checklist Report
```
📋 PRE-TRADE CHECKLIST
  ① Smart Money Direction: 🟢 PASS
  ② Retail Behavior (6h):  🟢 PASS
  ③ Macro Events (next 48h): 🟢 PASS
  VERDICT: ✅ ALL CLEAR — SAFE TO TRADE
```
