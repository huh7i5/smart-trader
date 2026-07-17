# Quant Architecture Patterns

Use these public, mature system patterns to keep the skill modular and auditable. Do not copy institutional complexity that does not improve a personal Binance Spot workflow.

## Sources

- [QuantConnect LEAN Algorithm Framework](https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview): separates Universe Selection, Alpha, Portfolio Construction, Risk Management, and Execution.
- [QuantConnect Reality Modeling](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/key-concepts): models fills, slippage, transaction fees, settlement, and brokerage behavior rather than assuming ideal execution.
- [Microsoft Qlib Workflow](https://qlib.readthedocs.io/en/latest/component/workflow.html): records data, parameters, artifacts, and metrics through reproducible experiment workflows and supports point-in-time data.
- [NautilusTrader Architecture](https://nautilustrader.io/docs/latest/concepts/overview/): separates data, risk, execution, portfolio, cache, and reconciliation components across backtest and live environments.

## Adopted Mapping

| Mature pattern | Repository component | Required behavior |
|---|---|---|
| Universe selection | `binance_market_scan.py` | Discover the live Binance universe; do not use a manual symbol list. |
| Point-in-time data and features | `research_snapshot.py` | Timestamp every research dimension, retain source lineage, reject future news, and persist the artifact. |
| Alpha/signal gate | `pre_trade_checklist.py` | Keep research separate from trade permission; require all three checks. |
| Portfolio construction | `position_sizing.md` and sizing scripts | Size from account value, concentration, and reserve constraints. |
| Risk engine | `order_safety.py` | Enforce caps, cash reserve, checklist freshness, token binding, and core-position rules in code. |
| Execution engine | order scripts | Preview first, confirm later, and bind confirmation to exact parameters. |
| Reality model | limit-first execution and backtests | Include fees, slippage assumptions, liquidity limits, and non-ideal fills. |
| Recorder | timestamped `.state` artifacts | Preserve inputs and outputs needed to reproduce a decision. |
| Reconciliation | `check_portfolio.py` | Verify open orders or fills after submission; command acceptance is not execution proof. |

## Deliberately Not Copied

- High-frequency order routing, co-location, leverage optimization, and derivatives risk are outside scope.
- Headline sentiment does not become an automatic alpha signal.
- A current-universe snapshot must not be used as historical constituent data in a backtest; that would introduce survivorship bias.
- Underlying-stock history may fill a short bStock history, but it must remain labeled as a reference because 24/7 bStock prices can diverge from exchange-session equity prices.
