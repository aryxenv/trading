---
name: portfolio-restructure-workflow
description: Use for portfolio restructure analysis that must use full IBKR portfolio data.
---

Portfolio checklist:
1. Load the full IBKR snapshot: holdings, cash, account values, concentration, and P/L where available.
2. Identify concentration, weak holdings, correlated exposures, cash constraints, and tax-sensitive assumptions.
3. For ticker/company requests, use the user's holding data. If absent, treat it as a new investment funded by cash or candidate shifts.
4. For restructure requests, compare the current portfolio against proposed shifts and a no-action baseline.
5. Require evidence for every sell, trim, add, or buy candidate.
6. Rank changes by expected impact, risk reduction, confidence, and reversibility.
7. Prefer no action when portfolio data is incomplete or risk limits are unspecified.

Return an executive restructure packet, not raw logs.
