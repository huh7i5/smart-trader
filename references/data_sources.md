# Live Data Sources and Limits

## Binance Ranking Evidence

The market scanner joins three live Binance responses:

| Purpose | Endpoint | Required validation |
|---|---|---|
| Trading status and Spot eligibility | `https://api.binance.com/api/v3/exchangeInfo` | `status=TRADING`, Spot allowed, requested quote asset |
| 24-hour price, quote volume, trade count | `https://api.binance.com/api/v3/ticker/24hr` | Positive last price and parseable numeric fields |
| Product category | `https://www.binance.com/bapi/asset/v2/public/asset-service/product/get-products?includeEtf=true` | Product symbol contains the `bStocks` tag |

The product endpoint is on Binance's official domain but is not part of the stable Spot API contract. If its schema changes or returns no bStocks, fail closed rather than falling back to ticker-name guessing.

## Taker Flow

`https://api.binance.com/api/v3/klines` returns total base volume at index 5 and taker-buy base volume at index 9. Calculate:

```text
taker_sell_base_volume = total_base_volume - taker_buy_base_volume
taker_buy_ratio = taker_buy_base_volume / total_base_volume
```

Do not estimate taker flow from candle shape when the real field is available.

## Order Book and Smart-Money Language

`https://api.binance.com/api/v3/depth` is a visible, short-lived order-book snapshot. It can be cancelled, spoofed, or moved immediately. Combining it with a seven-day price trend is a market-structure proxy only. It is not evidence of ETF flows, whale wallets, exchange reserves, or institutional intent.

Use external, attributable sources for those claims. If such sources were not actually opened, omit the claim.

## Macro and Company News

The checklist accepts only recent URL-backed evidence created by `macro_evidence.py`. A clear result requires at least two reachable sources. Reachability does not prove relevance, so the response must still show the URLs and summarize what each source establishes.

When evidence cannot be obtained, report `unknown` and block active trading.

## Unified Technical, Fundamental, and News Snapshot

`research_snapshot.py` refreshes the three research dimensions for held, requested, or shortlisted symbols. It saves both a latest artifact and a timestamped archive in `.state/`.

### Technical

Technical evidence comes from Binance `ticker/24hr`, `klines`, and `depth`. The script calculates 24-hour, seven-day, and 30-day changes, SMA20/50, RSI14, 20-day annualized volatility, six-hour taker flow, and visible bid/ask notional. These are market proxies, not forecasts or trader-identity evidence.

When a newly listed bStock has fewer than 51 daily candles, longer-horizon indicators use its linked underlying ticker through Yahoo's public chart endpoint. Binance still supplies the bStock's current price, taker flow, and visible depth. The report labels the history as `underlying_stock_reference` and `official_exchange_feed=false`; do not assume the exchange-session stock and 24/7 bStock are always identical.

### Fundamental

Every symbol receives Binance trading status, product tags, quote volume, and trade count. For crypto, this is explicitly a market-liquidity/adoption proxy; it is not on-chain activity, protocol revenue, treasury, token unlock, or issuer financial coverage.

For bStocks, the script strips the Binance `B` suffix, resolves the underlying ticker through the official SEC company-ticker file, and fetches recent material filings from `data.sec.gov/submissions`. SEC fair-access policy requires a configured `sec_user_agent` containing an application name and real contact email. Missing configuration returns `partial` instead of using a third-party ticker map.

### News

The Federal Reserve RSS feed is an official macro source. Google News RSS is used only to discover current symbol coverage. The script decodes aggregator URLs, verifies that the original publisher page is reachable, and preserves publisher and publication time.

Discovery, decoding, and reachability do not establish accuracy, relevance, independence, or market impact. Keep `review_required=true`; open and read the original sources before creating `macro_evidence.py` input. Never generate `clear`, `caution`, or `blocked` from headline sentiment alone.

## Historical Note

On 2026-07-17, the official live product response contained 36 trading USDT products tagged `bStocks`, while the previous repository hardcoded 33. This demonstrates why live discovery is mandatory and manual counts must not be quoted as current facts.
