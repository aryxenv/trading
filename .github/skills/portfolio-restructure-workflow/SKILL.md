---
name: portfolio-restructure-workflow
description: Use for portfolio restructure analysis that must use full IBKR portfolio data.
---

Portfolio checklist:
1. Load the full IBKR snapshot with `uv run python -m ibkr.scripts.portfolio_snapshot`.
2. Read or update `PROFILE.md` from the snapshot. Use it as the sizing, cash-buffer, concentration, and speculative-exposure basis.
3. Build restructure context with `uv run python -m ibkr.scripts.restructure_context`.
4. Identify concentration, weak holdings, correlated exposures, cash constraints, and tax-sensitive assumptions.
5. For ticker/company requests, use the user's holding data. If absent, treat it as a new investment funded by cash or candidate shifts and governed by `PROFILE.md`.
6. For restructure requests, compare the current portfolio against proposed shifts and a no-action baseline.
7. Separate impacts across short-term (1-3 months), medium-term (3-12 months), and long-term (1+ years), including liquidity, concentration, tax-sensitive assumptions, opportunity cost, and profile fit.
8. Require evidence for every sell, trim, add, or buy candidate in the horizon where it is proposed.
9. Rank changes by expected impact, risk reduction, confidence, reversibility, and horizon fit.
10. Prefer no action when portfolio data is incomplete, profile gates fail, or horizon conflicts are unresolved. Do not claim risk limits are unspecified when `PROFILE.md` provides a relevant gate.

Return an executive restructure packet grouped by short-term, medium-term, long-term, then an overall portfolio conclusion.
