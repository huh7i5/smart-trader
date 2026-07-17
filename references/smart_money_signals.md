# Market Structure and External Flow Evidence

"Smart money" is an interpretation, not a field returned by Binance. Never infer the identity or intent of traders from price, volume, or a single order-book snapshot.

## Evidence Classes

### Binance Taker Flow

Use the real Kline fields documented in [data_sources.md](data_sources.md):

- Taker buy volume measures market buys that crossed the spread.
- Derived taker sell volume measures market sells that crossed the spread.
- A high taker-buy ratio shows aggressive buying during the measured window; it does not prove retail or institutional identity.
- Net selling with a stable price can indicate absorption, but it can also reflect passive market making, hidden liquidity, timing effects, or an incomplete candle. Treat it as a hypothesis requiring confirmation.

### Visible Order Book

Measure bid and ask notional over the same depth and at the same timestamp. Always disclose:

- The requested depth.
- The bid/ask notional ratio.
- That orders can be cancelled or spoofed immediately.
- That a snapshot cannot identify iceberg orders or ownership.

Do not use fixed labels such as "3x means bulls control the market" without asset-specific validation.

### Trend Proxy

A seven-day return is a trend filter only. Combining a positive return with bid-side depth produces the skill's `market_structure_proxy`; it does not become institutional-flow data by combination.

## External Institutional Evidence

ETF flows, exchange reserves, whale wallets, NUPL, funding, and open interest require separate attributable sources. For every claim:

1. Open the actual source page or API response.
2. Record its publication timestamp and measurement window.
3. Distinguish reported values from interpretation.
4. Check whether the source is primary, derived, delayed, or estimated.
5. Omit the signal when the source cannot be verified.

Never claim that the bundled Binance scripts fetched ETF, wallet, exchange-reserve, or institutional-position data. They do not.

## Combining Evidence

Use the bundled checklist's three canonical outcomes:

- `pass`: the measured condition meets its configured rule and evidence is fresh.
- `caution` or `blocked`: stop active buying.
- `unknown`: data is missing, stale, invalid, or unverifiable; stop active buying.

No number of proxy signals overrides missing macro/news evidence. A correlation observed in historical data is not proof of future price direction.
