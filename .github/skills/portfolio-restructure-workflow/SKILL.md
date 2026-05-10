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
6. Separate impacts across short-term (1-3 months), medium-term (3-12 months), and long-term (1+ years), including liquidity, concentration, tax-sensitive assumptions, and opportunity cost.
7. Require evidence for every sell, trim, add, or buy candidate in the horizon where it is proposed.
8. Rank changes by expected impact, risk reduction, confidence, reversibility, and horizon fit.
9. Prefer no action when portfolio data is incomplete, risk limits are unspecified, or horizon conflicts are unresolved.

Return an executive restructure packet grouped by short-term, medium-term, long-term, then an overall portfolio conclusion.
