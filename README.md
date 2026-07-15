# Crypto Smart Trader 🎯

> A disciplined, data-driven trading system for cryptocurrency and bStock (Binance tokenized US stocks) spot markets.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

## Features

- 📋 **3-Point Pre-Trade Checklist** — Smart money direction + retail behavior + macro events
- 💰 **Fund Flow Analysis** — Track Taker buy/sell volume and order book depth
- 📊 **Portfolio Management** — View holdings, P&L, open orders at a glance
- 🛡️ **Risk Management** — Enforced position sizing, cash reserves, and batch entry
- ⚡ **One-Command Trading** — Market buy, limit buy, market sell, cancel orders
- 📅 **Macro Event Awareness** — CPI, FOMC, earnings season calendar

## Quick Start

### Prerequisites

- Python 3.10+
- Binance account with API keys
- `ccxt` library

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/crypto-smart-trader.git
cd crypto-smart-trader

# Install dependencies
pip install ccxt

# Configure your API keys
cp resources/config_template.json config.json
# Edit config.json with your Binance API key and secret
```

### Usage

```bash
# Check current prices
python scripts/check_prices.py

# View your portfolio
python scripts/check_portfolio.py

# Run pre-trade checklist before any trade
python scripts/pre_trade_checklist.py --symbol BTC/USDT

# Analyze fund flows
python scripts/check_fund_flow.py --hours 6

# Buy $50 of BTC at market price
python scripts/buy_market.py BTC 50

# Place a limit buy for BTC at $58,800
python scripts/buy_limit.py BTC 58800 50

# Sell all DRAMB holdings
python scripts/sell_market.py DRAMB --all

# Cancel all open orders
python scripts/cancel_order.py --all
```

## The 3-Point Pre-Trade Checklist

Before **every** trade, you MUST check:

| Check | What to Look For | Tool |
|:---:|:---|:---|
| ① Smart Money | ETF flows, whale accumulation, exchange reserves | `check_fund_flow.py` |
| ② Retail Behavior | Taker volume, order book depth, divergence signals | `check_fund_flow.py` |
| ③ Macro Events | CPI, FOMC, earnings within 48 hours | `pre_trade_checklist.py` |

**Only trade when all 3 checks pass (🟢🟢🟢).**

## The 5 Iron Rules

1. **Never sell core positions in panic**
2. **Never chase pumps (>5% daily = don't buy)**
3. **Wait for data before acting on releases**
4. **Max 6-12% of capital per trade**
5. **Always maintain 30%+ cash reserve**

## Project Structure

```
crypto-smart-trader/
├── SKILL.md              # AI agent skill definition
├── README.md             # This file
├── LICENSE               # MIT License
├── scripts/              # Executable trading scripts
│   ├── check_portfolio.py
│   ├── check_prices.py
│   ├── check_fund_flow.py
│   ├── pre_trade_checklist.py
│   ├── buy_market.py
│   ├── buy_limit.py
│   ├── sell_market.py
│   └── cancel_order.py
├── references/           # Documentation
│   ├── trading_rules.md
│   ├── position_sizing.md
│   ├── smart_money_signals.md
│   └── macro_calendar.md
├── examples/             # Examples and templates
│   ├── dca_plan_example.md
│   └── pre_trade_report_example.md
└── resources/            # Configuration templates
    └── config_template.json
```

---

# 📖 中文说明

## 这是啥

这套交易工具是我个人**自己瞎摸索出来的**。本金不多（$1,700 左右），核心逻辑就是通过脚本去读取你的币安持仓、分析当前行情、然后跑一遍“三项检查”给出信心评分（⭐ 到 ⭐⭐⭐⭐⭐ 推荐度）。

我把它开源出来，大家可以作为一个基础参考，去优化、改进、找到更适合你自己的交易策略。

> [!IMPORTANT]
> **这套工具是“半自动”的（决策辅助），不是“全自动”挂机机器人**。我自己害怕全自动机器人可能会因为网络波动、插针行情或者逻辑漏洞直接“玩脱”导致爆仓，所以最终的买卖执行依然需要你手动确认。

## 核心怎么用？

1. **申请币安 API**：去币安后台申请只读/现货交易权限的 API Key 和 Secret（**绝对不要开杠杆/合约/提现权限！**）。
2. **填写配置**：把 API Key 填入 `config.json` 配置文件。
3. **读取持仓**：运行脚本，它会去读你的“池塘”（持仓），把每个代币的市值和现金占比列出来。
4. **分析行情**：跑“信心评分”和“三项检查”，它会结合最新的波动率、回撤深度和均线，给出现在的星级推荐。
5. **手动下单**：如果分数很高（比如 4-5 星），你可以选择用买入脚本手动下一笔定投单。

## 快速上手

```bash
git clone https://github.com/yourusername/crypto-smart-trader.git
cd crypto-smart-trader
pip install ccxt
cp resources/config_template.json config.json
# 编辑 config.json，填入你的币安 API Key
# 国内用户记得填 proxy 代理，比如 "http://127.0.0.1:7890"
```

常用命令：

```bash
python scripts/check_portfolio.py                       # 1. 读持仓（看你水池里有多少鱼和水）
python scripts/pre_trade_checklist.py --symbol BTC/USDT # 2. 跑三项检查（看宏观和资金流）
# 或者运行最新优化的评分脚本：
python scripts/conviction_score.py BTC SOL LINK DOGE    # 3. 查看这几个币今天的星级和信心评分
python scripts/buy_market.py BTC 50                     # 4. 手动确认：市价买入 $50 BTC
```

> 💡 **评分标准**：关于 ⭐ 到 ⭐⭐⭐⭐⭐ 的详细评分标准、市场状态成因，请参考 [star_rating_guide.md](references/star_rating_guide.md) 说明文档。

## 我的几条规矩

1. 跌了不割核心仓（BTC/SOL 这种），除非逻辑变了
2. 涨超 5% 的不追
3. CPI/FOMC 之前不开新仓
4. 单笔最多投总资金的 10%
5. 永远留 30% 现金

## 待改进

- 资金流分析现在用 K 线估算，不够精确
- 缺 Telegram 推送
- 需要更多历史回测

欢迎 Issue / PR 👋

---

## ⚠️ 免责声明

本项目仅供学习研究，不构成投资建议。炒币有风险，亏了别找我。

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

*用纪律交易，靠数据决策。半自动行稳致远。* 🎯
