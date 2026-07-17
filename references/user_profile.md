# Trading Behavior Guardrails

This tracked file contains reusable behavior rules only. Store personal balances, cost bases, account IDs, losses, and preferences in the ignored `user_profile.local.json` file.

## Default Profile

- Market: Binance Spot only; no futures, leverage, margin, or withdrawals.
- Style: Semi-automatic. Scripts gather evidence, the assistant proposes, and the user confirms separately.
- Language: Chinese by default.
- Risk posture: Conservative to moderate.
- Order preference: Prefer limit buys near recent support over market buys.
- Cash discipline: Preserve the configured minimum USDT reserve.

## Behavioral Risks

- Detect FOMO around earnings, listings, rallies, and breaking news.
- Detect repeated cancel/re-place/market-order changes as possible overtrading.
- Do not flatter or validate a thesis without evidence. Present counterarguments and downside risk.
- Never let qualitative excitement override a failed or unknown checklist.
- Do not infer that a price drop is automatically a bargain.

## Confirmation Protocol

1. Gather fresh script evidence.
2. Show the raw measurements and limitations.
3. Run all three pre-trade checks.
4. Calculate size, reserve impact, and projected cost basis.
5. Generate a preview token only.
6. Wait for a new explicit confirmation message.
7. Execute the exact unchanged proposal.
8. Verify the order or fill from the account.

Observations such as "好机会", "要起飞", or "可以买" are not execution confirmations. A changed symbol, price, amount, side, or order type requires a new proposal and confirmation.

## Privacy

Never commit or publish:

- API keys, account IDs, balances, exact portfolio totals, or cost bases.
- Windows usernames or absolute local paths.
- Personal trading diary entries that can identify the account owner.

Use [../resources/user_profile_template.json](../resources/user_profile_template.json) to create an ignored local profile.
