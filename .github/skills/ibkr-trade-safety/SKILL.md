---
name: ibkr-trade-safety
description: Use before any IBKR trade action, order intent, or portfolio change recommendation.
---

Safety rules:
- Live trading only; never assume paper trading.
- Never place, stage, modify, cancel, or submit a trade without explicit user confirmation of exact order details.
- Confirmation must include account, symbol, side, quantity, order type, time in force, and prices when applicable.
- Do not use old confirmation for a new or changed order.
- Do not trade on stale news, missing IBKR portfolio context, unclear risk limits, or weak council consensus.
- If risk limits are unspecified, prefer no action.
- Write final executive records to `reports/YYYYMMDD-<ticker-or-company>.md`.
- Do not commit credentials, account secrets, raw tokens, or broker session data.
