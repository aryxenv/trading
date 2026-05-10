---
name: trading-research-workflow
description: Internal checklist for research agents. Do not invoke directly for bare ticker/company prompts; route those to research-orchestrator first.
---

Invocation boundary:

- Root assistant must not invoke this skill directly for user ticker/company prompts.
- Bare ticker/company input must start `research-orchestrator`; that agent and its delegated agents invoke `/trading-research-workflow`.
- Use this skill only after orchestration has begun, or when an agent explicitly needs the research checklist.

Research checklist:

1. Define the target, thesis, and affected portfolio holding.
2. Split the analysis into mandatory horizons: short-term (1-3 months), medium-term (3-12 months), and long-term (1+ years). Do not blend conflicting horizon signals into one recommendation.
3. Start top-down for each horizon: macro, rates, sector, industry, company, valuation, technicals, and catalysts.
4. Resolve company names or typo-prone inputs with `uv run python -m ibkr.scripts.symbol_resolve`.
5. Load IBKR context with `uv run python -m ibkr.scripts.portfolio_snapshot`, then `uv run python -m ibkr.scripts.position_context` using the resolved ticker.
6. Load supplemental IBKR API news with `uv run python -m ibkr.scripts.ibkr_news`; absence of IBKR headlines is not a signal.
7. Use the agent built-in `web` tool for current trust-worthy, qualitative, and non-opinionated web/news sources. Do not use shell web scraping or ad hoc HTTP fetches (`curl`, `wget`, `Invoke-WebRequest`, Python `urllib`/`requests`/`httpx`) for public web/news research. Include at least one disconfirming or contrarian source when available.
8. Separate facts from estimates and opinions.
9. Run Python analysis with `uv run ...` for any calculations.
10. Check historical trends, volatility, drawdowns, valuation ranges, and relevant benchmarks separately for each horizon.
11. Strip bias: identify incentives, stale narratives, promotional language, and unsupported claims.
12. Prune routes that do not affect the decision.
13. Prefer no action when evidence is incomplete, stale, conflicting, or only supports one horizon while risk limits imply another.

Return concise evidence, statistics, confidence, dissent, and no-action triggers grouped by short-term, medium-term, long-term, then an overall conclusion.
