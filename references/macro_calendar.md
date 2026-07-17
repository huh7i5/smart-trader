# Macro and Company Event Evidence

Scheduled event dates and company earnings change frequently. Do not use a hardcoded calendar as live truth.

## Required Workflow

1. Open current primary schedules where possible, such as the Federal Reserve, BLS, SEC/company investor-relations pages, and Binance announcements.
2. Confirm the exact date, time, timezone, affected asset, and publication timestamp.
3. Search current company, sector, security, exchange, and regulatory news for the requested symbol.
4. Save the actual opened URLs with `macro_evidence.py`.
5. Run `pre_trade_checklist.py`; stale or missing evidence becomes `unknown` and blocks active buying.

A `clear` evidence file requires at least two reachable sources. Reachability alone does not prove relevance, so show the URLs and explain what each establishes.

## Risk Classification

- `blocked`: A major event is imminent, an exploit/depeg/halt exists, or material negative information invalidates the trade premise.
- `caution`: Uncertain timing, conflicting reports, earnings or policy risk, or incomplete source coverage.
- `clear`: No material event was found in the defined next-48-hour window after checking at least two relevant sources.
- `unknown`: Search unavailable, URLs inaccessible, evidence stale, or the asset could not be mapped reliably.

Only `clear` passes the third checklist point.

## Events to Check

- CPI, PCE, jobs data, FOMC decisions, minutes, and major central-bank speeches.
- Earnings, guidance, filings, corporate actions, and trading halts for bStocks.
- Binance listings, delistings, maintenance, collateral changes, and symbol status.
- Protocol exploits, token unlocks, governance actions, stablecoin depegs, and regulatory decisions for crypto assets.
- Sector-specific supply, sanctions, export restrictions, litigation, and competitor events.

## Reporting Rules

- Never predict a fixed percentage reaction to an economic surprise.
- Never assume a recurring release occurs on the same day every month.
- Never treat a search-result snippet as the opened source.
- Never turn absence of search capability into a clear calendar.
- Convert all times to UTC and the user's timezone in the final report.
