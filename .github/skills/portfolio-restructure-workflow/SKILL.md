---
name: portfolio-restructure-workflow
description: Use for portfolio restructure analysis that must use full IBKR portfolio data.
---

Portfolio checklist:
1. Load the full IBKR snapshot with `uv run python -m ibkr.scripts.portfolio_snapshot`.
2. Build restructure context with `uv run python -m ibkr.scripts.restructure_context`.
3. Identify concentration, weak holdings, correlated exposures, cash constraints, and tax-sensitive assumptions.
4. For ticker/company requests, use the user's holding data. If absent, treat it as a new investment funded by cash or candidate shifts.
5. For restructure requests, compare the current portfolio against proposed shifts and a no-action baseline.
6. Require evidence for every sell, trim, add, or buy candidate.
7. Rank changes by expected impact, risk reduction, confidence, and reversibility.
8. Prefer no action when portfolio data is incomplete or risk limits are unspecified.

Return an executive restructure packet, not raw logs.
