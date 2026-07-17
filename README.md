# Crypto Smart Trader

面向 Binance Spot 与 bStocks 的证据驱动交易辅助 skill。实时榜单、价格、资金流和交易结论必须来自脚本输出，不允许语言模型凭记忆补全。

> 仅供研究和决策辅助，不构成投资建议。默认禁止真实下单；期货、杠杆、保证金和提现不在支持范围内。

## 核心改进

- 动态读取 Binance 产品标签，不再手写 bStocks 名单。
- 从 Binance Kline 的真实 taker-buy 字段计算买卖流，不再用蜡烛形状冒充资金流。
- 每份实时报告包含 UTC 时间、数据源、记录数和本地证据 JSON。
- 宏观/公司新闻缺少可验证 URL 时返回 `unknown`，主动交易直接停止。
- 买入、卖出和撤单默认只生成预览；真实操作需要未过期的一次性 proposal token。
- 代码强制执行单笔上限、现金储备、checklist 时效和核心仓位保护。

## 安装

```bash
git clone https://github.com/huh7i5/smart-trader.git
cd smart-trader
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
copy resources\config_template.json config.json
```

Linux/macOS 使用 `source .venv/bin/activate` 和 `cp`。公共行情与榜单不需要 API Key；只有持仓和订单功能需要 Spot-only Key。禁止开启提现、期货、杠杆权限，建议配置 IP 白名单。

`config.json` 默认：

```json
{
  "allow_live_trading": false,
  "testnet": false,
  "risk_per_trade_pct": 10,
  "min_cash_reserve_pct": 30
}
```

在完成 testnet 验证前不要打开 `allow_live_trading`。

## 真实 Binance 榜单

```bash
# 动态 bStocks 涨幅榜、跌幅榜、成交量榜
python scripts/binance_market_scan.py --category bstock --limit 10

# 加密货币榜单
python scripts/binance_market_scan.py --category crypto --limit 10

# 机器可读证据
python scripts/binance_market_scan.py --category bstock --limit 10 --json
```

脚本实时联结 Binance `exchangeInfo`、24h ticker 和产品 `bStocks` 标签。接口失败或返回空集时退出非零状态，不会回退到手写名单。

## 三点检查

先使用真实打开过的网页创建宏观/新闻证据：

```bash
python scripts/macro_evidence.py --symbol BTC --status clear ^
  --source "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm" ^
  --source "https://example.com/actual-opened-market-news" ^
  --note "未来 48 小时未发现重大负面事件"
```

然后运行：

```bash
python scripts/pre_trade_checklist.py --symbol BTC/USDT --json
```

只有三项全部 `pass` 才会生成 `trade_allowed`。没有宏观证据、证据过期、URL 不可访问或任何数据请求失败时均 fail closed。

## 两阶段下单

第一次命令只创建预览：

```bash
python scripts/buy_limit.py BTC 58800 50
```

用户检查并在新的消息中明确确认后，才能使用原 proposal token：

```bash
python scripts/buy_limit.py BTC 58800 50 --confirm PROPOSAL_TOKEN
```

修改价格、数量、symbol、方向或订单类型会使 token 不匹配。token 过期或已经使用也会被拒绝。市价买入、卖出和撤单遵循相同流程。

## 常用命令

```bash
python scripts/check_prices.py BTC SOL DRAMB NVDAB
python scripts/check_fund_flow.py --hours 6 --symbols BTC DRAMB
python scripts/check_portfolio.py
python scripts/conviction_score.py BTC SOL
python scripts/bulk_screener.py --category bstock
```

`bulk_screener.py` 现在是动态榜单兼容入口，只提供排名证据，不再把缺少宏观检查的 2/3 结果叫作“全绿”。

## 验证

```bash
python -m unittest discover -s tests -v
```

CI 会执行语法检查、单元测试和 skill frontmatter 验证。需要本地运行 `quick_validate.py` 时，请使用当前 Codex 安装中 `skill-creator/scripts/quick_validate.py` 的实际路径。联网测试只读取 Binance 公共接口，测试流程不会提交订单。

## 隐私

`config.json`、`.state/`、`.cache/` 和 `user_profile.local.json` 已被忽略。不要把 API Key、账户余额、成本价、用户名路径或个人交易日志提交到 GitHub。

## License

MIT
