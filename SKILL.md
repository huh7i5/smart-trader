---
name: crypto-smart-trader
description: Evidence-backed Binance Spot and bStocks trading assistant for live market rankings, portfolio checks, taker-flow analysis, pre-trade validation, guarded order proposals, position sizing, and DCA planning. Use for Binance spot questions such as current rankings, top gainers/losers, bStocks lists, "什么情况", "BN/Binance 排行榜", "查看持仓", "资金流向", "交易前检查", "买入", "卖出", "挂单", "定投计划", "仓位管理", "止损", or "止盈". Do not use for futures, leverage, DeFi, tax, or fully autonomous trading.
---

# Crypto Smart Trader

Use this skill as a decision-support system for Binance Spot. Never represent it as financial advice or a guarantee of profit.

## Non-Negotiable Truth Protocol

Apply these rules before every live-market answer:

1. Run a bundled script for every claim about current prices, rankings, available symbols, volume, fund flow, portfolio state, or checklist status.
2. Never answer current-market questions from memory, prior chat messages, a hardcoded symbol list, or model intuition.
3. Treat missing, malformed, empty, or stale script output as `DATA_UNAVAILABLE`. State the failure plainly and do not fill gaps with plausible values.
4. Include `fetched_at_utc`, the data source, the number of markets/records, and the evidence file path in the answer.
5. Treat market evidence older than five minutes as stale and rerun it.
6. Never call a two-point scan "fully green". A trade verdict requires all three checks, including verified macro/news evidence.
7. Never invent URLs, article titles, Binance announcements, rankings, fills, balances, or API results.

These rules override conversational helpfulness. A truthful failure is better than a fluent hallucination.

## Live Ranking Workflow

For "排行榜", "涨幅榜", "跌幅榜", "成交量榜", "有哪些 bStocks", "什么情况", or similar requests:

```bash
python ${SKILL_DIR}/scripts/binance_market_scan.py --category bstock --limit 10 --json
```

Use `--category crypto` for crypto only and `--category all` for every Binance Spot USDT market. Verify all of the following before reporting results:

- `status` equals `ok`.
- `market_count` is greater than zero.
- `fetched_at_utc` is within five minutes.
- `source.exchange_info`, `source.ticker_24h`, and `source.product_tags` are present.

The script discovers bStocks dynamically from Binance's `bStocks` product tag and intersects them with currently trading Spot markets. Do not maintain or quote a manual bStock count.

## Current Market Workflow

When the user asks "什么情况" or "现在呢":

1. Run `check_prices.py` for held or requested symbols.
2. Run `binance_market_scan.py` when relative market position or rankings matter.
3. Run `check_fund_flow.py` for actual Binance taker-buy volume and visible order-book depth.
4. If private credentials are configured, run `check_portfolio.py` when holdings or cash affect the answer.
5. Separate measured facts from interpretation. Label order-book/trend logic as a proxy, never as proof of institutional activity.

## Pre-Trade Workflow

Apply this sequence to every active or booster buy:

1. Read [references/user_profile.md](references/user_profile.md). If a local `user_profile.local.json` exists, use it without exposing it.
2. Fetch current price, market ranking context, and taker flow with bundled scripts.
3. Use an available web search or browser tool to open current macro, company, sector, security, and regulatory sources. Do not rely on snippets alone.
4. Save reachable source URLs as evidence. A `clear` verdict requires at least two independent sources:

```bash
python ${SKILL_DIR}/scripts/macro_evidence.py --symbol BTC --status clear \
  --source "https://source-one.example/article" \
  --source "https://source-two.example/calendar" \
  --note "No material event found in the next 48 hours"
```

5. Run the checklist:

```bash
python ${SKILL_DIR}/scripts/pre_trade_checklist.py --symbol BTC/USDT --json
```

6. Stop if `all_pass` is false, any check is not `pass`, evidence is stale, or a tool failed. Macro/news `unknown` is a hard stop.
7. Optionally run `conviction_score.py` only after the checklist passes. A score never overrides a failed checklist.
8. Calculate size, cash reserve, and projected cost basis. Propose a limit order first.
9. Generate a preview. Do not execute in the same conversational step:

```bash
python ${SKILL_DIR}/scripts/buy_limit.py BTC 58800 50
```

10. Show the exact symbol, side, type, price, quantity, USDT amount, current/projected cost, reserve impact, checklist time, and proposal expiry. Wait for a new explicit user confirmation.
11. Only after explicit confirmation, execute the unchanged proposal with its token:

```bash
python ${SKILL_DIR}/scripts/buy_limit.py BTC 58800 50 --confirm PROPOSAL_TOKEN
```

12. Run `check_portfolio.py` to verify the resulting order or fill. Never claim success from command submission alone.

## Canonical Decision Rule

For active and booster buys, only `PASS + PASS + PASS` permits an order proposal. Any `caution`, `blocked`, `unknown`, missing data, or script error means do not trade.

Baseline DCA is the only checklist exception. Use `--mode baseline` only when the user explicitly requests the pre-agreed baseline schedule. It still requires risk checks, a preview token, a separate confirmation, and code-enabled live trading. Never silently reinterpret an active buy as baseline DCA.

## Hard Execution Guardrails

- Live trading is disabled by default in `config.json`.
- Every order and cancellation is preview-only on the first command.
- Proposal tokens expire and are single use.
- Active buys require a recent all-pass checklist artifact for the exact symbol.
- Code enforces the configured per-trade cap and minimum USDT reserve.
- Full sale of configured core assets is disabled by default.
- Prefer limit buys. Use market buys only when the user explicitly requests them after seeing slippage risk.
- Never grant API withdrawal, futures, or margin permissions. Recommend IP restrictions and a dedicated Spot-only key.

## Research and Strategy References

- Read [references/data_sources.md](references/data_sources.md) before changing live data semantics or ranking logic.
- Read [references/trading_rules.md](references/trading_rules.md) for behavioral and risk rules.
- Read [references/position_sizing.md](references/position_sizing.md) for allocation planning.
- Read [references/baseline_booster_strategy.md](references/baseline_booster_strategy.md) for baseline versus booster modes.
- Read [references/integrated_strategy.md](references/integrated_strategy.md) and [references/wfa_backtest_report.md](references/wfa_backtest_report.md) only for research context. Historical backtests are not live deployment approval.

## Response Contract

For live data, finish with a compact provenance block:

```text
DATA PROVENANCE
Fetched: <UTC timestamp>
Sources: <actual endpoints/pages opened>
Records: <market or result count>
Evidence: <local JSON artifact>
Limitations: <proxy, stale, unavailable, or coverage notes>
```

Respond in Chinese unless the user requests another language. Keep exact portfolio values and local paths out of public-facing content.
