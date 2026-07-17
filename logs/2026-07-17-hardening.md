# 2026-07-17 Reliability Hardening

## Observed issues

- The bStocks universe depended on a maintained symbol list and could omit newly tagged markets.
- Market-flow interpretation did not consistently use Binance taker-buy fields.
- Some two-signal scan results could be presented without verified macro or company-news evidence.
- Live-data answers did not consistently expose timestamps, sources, record counts, and evidence artifacts.
- Order workflows needed stronger separation between preview and execution.

## Changes

- Discover bStocks dynamically from Binance product tags and active Spot markets.
- Calculate taker flow from Binance Kline volume fields and label order-book analysis as a proxy.
- Require three passing checks for active buys; missing or stale macro evidence fails closed.
- Persist live reports as timestamped JSON with source and coverage metadata.
- Require expiring, single-use proposal tokens and a separate confirmation step for order execution.
- Enforce trade caps, cash reserves, checklist freshness, and core-position protections in code.

## Verification

- Added unit coverage for market discovery, macro evidence, checklist logic, and order safety.
- Added CI checks for Python syntax, unit tests, and skill frontmatter validation.
- Confirmed public market scans use Binance endpoints and do not submit orders.
