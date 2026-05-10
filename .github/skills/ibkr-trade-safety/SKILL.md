---
name: ibkr-trade-safety
description: Use before any IBKR trade action, order intent, or portfolio change recommendation.
---

IMPORTANT: User override allowed if explicitly mentioned to override safety rules. Otherwise, do not override.

Safety rules:

- Live trading only; never assume paper trading.
- Never place, stage, modify, cancel, or submit a trade without explicit user confirmation of exact order details.
- Confirmation must include account, symbol, side, quantity, order type, time in force, and prices when applicable.
- Do not use old confirmation for a new or changed order.
- Do not trade on stale news, missing IBKR portfolio context, unclear risk limits, or weak council consensus.
- Do not trade when the proposed action is only justified for a different horizon than the user's stated intent; unresolved short-, medium-, and long-term conflicts default to no action.
- If risk limits are unspecified, prefer no action.
- Write final executive records to `reports/YYYYMMDD-<ticker-or-company>.md`.
- Do not commit credentials, account secrets, raw tokens, or broker session data.
- Do not write ad hoc IBKR code. Use deterministic Python commands:
  - `uv run python -m ibkr.scripts.symbol_resolve`
  - `uv run python -m ibkr.scripts.portfolio_snapshot`
  - `uv run python -m ibkr.scripts.position_context`
  - `uv run python -m ibkr.scripts.restructure_context`
  - `uv run python -m ibkr.scripts.create_order_intent`
  - `uv run python -m ibkr.scripts.submit_order`
- `submit_order` must be interactive; do not generate, store, or pass the confirmation phrase for the user.
