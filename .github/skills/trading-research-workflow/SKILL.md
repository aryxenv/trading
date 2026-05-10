---
name: trading-research-workflow
description: Use for ticker or company trading research that must be web-grounded, statistical, unbiased, and top-down.
---

Research checklist:

1. Define the target, thesis, time horizon, and affected portfolio holding.
2. Start top-down: macro, rates, sector, industry, company, valuation, technicals, and catalysts.
3. Resolve company names or typo-prone inputs with `uv run python -m ibkr.scripts.symbol_resolve`.
4. Load IBKR context with `uv run python -m ibkr.scripts.portfolio_snapshot`, then `uv run python -m ibkr.scripts.position_context` using the resolved ticker.
5. Load supplemental IBKR API news with `uv run python -m ibkr.scripts.ibkr_news`; absence of IBKR headlines is not a signal.
6. Use the agent built-in `web` tool for current trust-worthy, qualitative, and non-opinionated web/news sources. Do not use shell web scraping or ad hoc HTTP fetches (`curl`, `wget`, `Invoke-WebRequest`, Python `urllib`/`requests`/`httpx`) for public web/news research. Include at least one disconfirming or contrarian source when available.
7. Separate facts from estimates and opinions.
8. Run Python analysis with `uv run ...` for any calculations.
9. Check historical trends, volatility, drawdowns, valuation ranges, and relevant benchmarks.
10. Strip bias: identify incentives, stale narratives, promotional language, and unsupported claims.
11. Prune routes that do not affect the decision.
12. Prefer no action when evidence is incomplete, stale, or conflicting.

Return concise evidence, statistics, confidence, dissent, and no-action triggers.
