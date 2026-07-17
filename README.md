# Crypto Smart Trader

面向 Binance Spot 与 bStocks 的证据驱动交易辅助 skill。它提供实时市场扫描、持仓检查、资金流分析、交易前验证和受保护的订单预览。

> 仅供研究和决策辅助，不构成投资建议。默认禁止真实下单，不支持期货、杠杆、保证金或提现。

## 核心能力

- 动态发现 Binance Spot 与 bStocks 市场并生成涨跌幅、成交量榜单。
- 使用 Binance Kline 与订单簿数据分析 taker flow 和可见深度。
- 将实时结果保存为带 UTC 时间、数据源和记录数的 JSON 证据。
- 通过市场结构、资金流、宏观/新闻三项检查控制主动交易。
- 使用两阶段预览与一次性 token 保护买入、卖出和撤单操作。

## 安装

```bash
git clone https://github.com/huh7i5/smart-trader.git
cd smart-trader
python -m venv .venv
```

Windows：

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item resources\config_template.json config.json
```

Linux/macOS：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
cp resources/config_template.json config.json
```

公共行情功能不需要 API Key。持仓和订单功能应使用仅开启 Spot 权限、关闭提现的独立 API Key，并配置 IP 白名单。

## 常用命令

```bash
# 市场榜单
python scripts/binance_market_scan.py --category bstock --limit 10 --json
python scripts/binance_market_scan.py --category crypto --limit 10 --json

# 持仓、价格和资金流
python scripts/check_portfolio.py
python scripts/check_prices.py BTC SOL DRAMB NVDAB
python scripts/check_fund_flow.py --hours 6 --symbols BTC SOL

# 交易前检查
python scripts/pre_trade_checklist.py --symbol BTC/USDT --json
```

宏观/新闻证据必须来自实际可访问的 URL。缺失、过期或不可访问的证据会使主动交易停止。只有三项检查全部通过，系统才允许生成订单预览。

## 下单保护

第一次调用只生成预览：

```bash
python scripts/buy_limit.py BTC 58800 50
```

核对订单后，在新的确认步骤中使用预览返回的一次性 token：

```bash
python scripts/buy_limit.py BTC 58800 50 --confirm PROPOSAL_TOKEN
```

`config.json` 默认关闭真实交易。代码同时检查 proposal 时效、交易参数、单笔上限、最低现金储备和核心仓位保护。

## 验证

```bash
python -m unittest discover -s tests -v
```

CI 会执行语法检查、单元测试和 skill frontmatter 验证。

## 隐私

`config.json`、`.state/`、`.cache/` 和 `user_profile.local.json` 不会提交到 GitHub。禁止提交 API Key、账户余额、成本价或个人交易记录。

## License

MIT
