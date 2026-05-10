---
name: trading-research-workflow
description: Use for ticker or company trading research that must be web-grounded, statistical, unbiased, and top-down.
---

Research checklist:

1. Define the target, thesis, time horizon, and affected portfolio holding.
2. Start top-down: macro, rates, sector, industry, company, valuation, technicals, and catalysts.
3. Resolve company names or typo-prone inputs with `uv run python -m ibkr.scripts.symbol_resolve`.
4. Load IBKR context with `uv run python -m ibkr.scripts.portfolio_snapshot`, then `uv run python -m ibkr.scripts.position_context` using the resolved ticker.
5. Use current trust-worthy, qualitative, and non-opinionated web/news sources. Include at least one disconfirming or contrarian source when available.
6. Separate facts from estimates and opinions.
7. Run Python analysis with `uv run ...` for any calculations.
8. Check historical trends, volatility, drawdowns, valuation ranges, and relevant benchmarks.
9. Strip bias: identify incentives, stale narratives, promotional language, and unsupported claims.
10. Prune routes that do not affect the decision.
11. Prefer no action when evidence is incomplete, stale, or conflicting.

Return concise evidence, statistics, confidence, dissent, and no-action triggers.
