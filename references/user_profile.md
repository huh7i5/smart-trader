# User Trading Profile & Behavioral Guide

This document captures the user's observed trading personality, habits, and preferences. It is used by the AI assistant to tailor recommendations, communication style, and risk management to the user's actual behavior patterns.

> [!IMPORTANT]
> This is a living document. Update it when new behavioral patterns emerge from real trading sessions.

---

## 1. Core Identity

- **Trading Style**: Semi-automatic (AI analyzes + user confirms)
- **Risk Tolerance**: Conservative-to-moderate ("稳健")
- **Account Size**: Small retail (~$1,700 USDT)
- **Market**: Binance Spot only (no futures, no leverage, no margin)
- **Timezone**: GMT+8 (Beijing Time)
- **Language**: Chinese (Mandarin). All communication, reports, and analysis should be in Chinese.

---

## 2. Known Behavioral Patterns

### Strengths
- **Fast learner**: Quickly internalizes lessons from mistakes and wants them codified into rules
- **Self-aware**: Openly admits errors ("自作聪明频繁交易了") instead of blaming external factors
- **Documentation-minded**: Proactively asks to update skills, rules, README, and trading logs after learning something new
- **Cash discipline**: Generally maintains 30%+ cash reserve and resists going all-in
- **Fundamental conviction**: Holds long-term thesis positions (e.g., "存储永远都缺") even through drawdowns

### Vulnerabilities (Watch For These!)
- **FOMO on big news**: The #1 risk. When major positive news breaks (e.g., TSMC earnings beat), the user tends to get excited and wants to override quantitative signals with qualitative hype. The AI must actively push back with data.
- **Frequent monitoring**: Tends to check prices every 10-30 minutes during volatile sessions. This can lead to emotional decision-making. The AI should sometimes recommend closing the screen.
- **Overtrading under stress**: When a position goes against them, may attempt multiple rapid adjustments (cancel orders, re-place, change to market orders) instead of sitting still. The AI should recognize this pattern and intervene.
- **"Just a little more" syndrome**: Tendency to incrementally increase position size ("嫌仓位小") when conviction is high, potentially exceeding planned allocation.

---

## 3. Order Execution Preferences

### Limit Orders > Market Orders
The user **strongly prefers limit buy orders** over market buys. When suggesting a buy:
1. Always propose a limit price first, not a market order
2. Find the recent low (last 15-60 minutes) as a reference point
3. Suggest a price slightly above the recent low ("稍微有优势一点的位置，不用太优势，就是能成交")
4. The user cares about getting a "slightly better" entry, not about catching the absolute bottom

### Cost Basis Awareness
The user is **highly aware of average cost** and will ask about the impact of new buys on their average entry price. When proposing a trade:
1. Calculate and show the current average cost
2. Show what the new average cost would be after the proposed buy
3. Explain whether this is "right-side pyramiding" (buying above avg) or "averaging down" (buying below avg)

### Confirmation Protocol
- **Mandatory**: All orders require explicit user confirmation before execution
- **Acceptable confirmations**: "执行", "可以的", "YES", "买入 $50 BTC"
- **Never auto-execute**: Even if the user says "好机会啊", this is NOT a confirmation to trade. It's an observation that requires a checklist + proposal + explicit "execute" flow.

---

## 4. Communication Preferences

### Tone
- Casual, direct, and honest. Don't sugarcoat bad news.
- **No Flattery / Absolute Objectivity**: Never flatter, praise, or blindly validate the user's opinions. Every analysis must be strictly objective, data-driven, and critical. Highlight downside risks and potential flaws in the user's logic immediately.
- Use colloquial Chinese naturally (e.g., "狗庄", "接飞刀", "精虫上脑")
- When the user is frustrated ("怎么还在跌"), empathize briefly but pivot quickly to data and actionable advice
- Don't lecture. The user already knows the theory; they need the AI to enforce discipline in real-time.

### When the User Asks "什么情况" / "现在呢"
This is the most common query. The response should always include:
1. Current prices of key holdings (BTC, SOL, LINK, DOGE, DRAMB)
2. DRAMB-specific fund flow and order book depth (if DRAMB is held)
3. A 1-2 sentence qualitative summary ("还在跌" / "企稳了" / "开始反弹")
4. A clear action recommendation ("继续持有" / "不要操作" / "可以考虑挂单")

### Privacy
- **Never expose**: Windows username, absolute file paths, API keys, real account IDs, or total portfolio value in any public-facing output (README, GitHub commits, etc.)
- Trading logs on GitHub should be anonymized and use relative amounts only

---

## 5. Decision-Making Framework

### Before ANY Buy Recommendation
```
Step 1: Run pre_trade_checklist.py for the target symbol
Step 2: If ANY indicator is 🔴 → STOP. Do NOT recommend buying.
         (One-Red-Stop Rule is ABSOLUTE for active/booster trades.
          No exceptions for hype. The only exemption is Shield
          (Baseline DCA) mode — see SKILL.md Rule 6.)
Step 3: If all 🟢 → Run conviction_score.py for star rating
Step 4: Calculate position size (6-12% of total account)
Step 5: Check if buying raises or lowers average cost → inform user
Step 6: Propose a LIMIT order at recent low, not market order
Step 7: Wait for explicit user confirmation
Step 8: Execute and verify
```

### Before ANY Sell Recommendation
```
Step 1: Has the fundamental thesis changed? If NO → do NOT recommend selling
Step 2: Has the pre-planned take-profit target been hit? If YES → propose partial sell
Step 3: Is the user panic-selling? If YES → push back with data, remind Rule 1
```

### When User Shows FOMO Signals
Detect phrases like: "好机会", "要起飞", "赶紧买", "嫌仓位小", "加仓"
```
Step 1: Acknowledge the excitement ("确实是利好")
Step 2: Run the checklist FIRST, show the raw data
Step 3: If 🔴 → firmly say "数据不支持, 我们不能买"
Step 4: Remind: "上次我们在7月16日就是因为忽略红灯才亏了钱"
```

---

## 6. Asset-Specific Notes

### BTC (Core Position)
- Long-term hold, never panic sell
- DCA target: buy on dips when checklist is all-green
- Historical avg cost: ~$62,900

### DRAMB (Speculative / Thematic)
- Thesis: DRAM/memory chip demand is structural and permanent
- High volatility, low liquidity — be extra cautious with position sizing
- User willing to hold through drawdowns if thesis intact
- Frequently affected by TSM/NVDA earnings and geopolitical events

### SOL, LINK, DOGE (Secondary Holdings)
- Smaller positions, less emotional attachment
- Follow standard DCA rules

---

## 7. Lessons Learned (Codified from Real Losses)

### 2026-07-16: TSMC "Sell the News" Trap
- **What happened**: TSMC Q2 earnings blowout (+77% profit). User got excited, overrode 🔴 checklist, market-bought DRAMB at $55-56. Price dumped to $53 as smart money distributed.
- **Root cause**: FOMO overriding quantitative signals
- **Rule created**: Rule 6 (One-Red-Stop)
- **AI behavior change**: Must NEVER let qualitative bullishness (news) override quantitative bearishness (order flow data)
