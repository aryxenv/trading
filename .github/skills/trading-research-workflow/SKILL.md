---
name: trading-research-workflow
description: Checklist for root-driven or autonomous ticker/company research with IBKR context, artifact validation, and council handoff.
---

Invocation boundary:

- Bare ticker/company input defaults to root-driven dev/foreground workflow.
- Root assistant may use this checklist directly when it owns the visible workflow.
- `research-orchestrator` is for explicit autonomous/background mode and must follow the same artifact and validation rules.
- Do not treat synchronous custom agents as visible progress; nested agent tool calls remain hidden.

Dev/foreground phase loop:

1. Root creates `sandbox/<run-id>/` and reports phase checkpoints to the user.
2. Root runs deterministic setup scripts directly: symbol resolution, portfolio snapshot, position context, target context, and IBKR news.
3. Root launches horizon research routes directly. Prefer synchronous/serial calls when visibility matters; use background only for independent routes when user opts into speed/autonomy.
4. Each route writes `sandbox/<run-id>/<route-name>/findings.json`.
5. Root or autonomous orchestrator writes `research-packet.json`, then runs `uv run python -m ibkr.scripts.validate_research_packet --input sandbox/<run-id>/research-packet.json`.
6. Council starts only after structural validation passes.
7. Each council member writes `vote.json`; critique writes `critique.json`.
8. Council record is written to `report-input.json`, then validated with `uv run python -m ibkr.scripts.validate_council_record --input sandbox/<run-id>/report-input.json`.

Prior-report exclusion:

- Files under `reports/` are audit logs, not evidence sources for a fresh research run.
- Do not read or cite prior reports when forming a current thesis, research packet, or council vote.
- If a prior report was accidentally read, treat it as contaminated context: do not cite it, do not use its conclusion as an anchor, and re-ground the run in current artifacts and external sources.
- Exception: read prior reports only when the user explicitly asks to review/compare an old decision, or when validating an order intent that references its own tracked report.

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

Evidence ownership:

- IBKR scripts own symbol, portfolio, target/position context, broker news, and live-account constraints.
- Market routes own web/news citations, filings, consensus, technicals, valuation, historical stats, peers, and contrarian evidence.
- Council owns decision quality, horizon conflicts, dissent, confidence, no-action triggers, and required confirmations.
- Validators own structural integrity. A packet may not claim completed routes or council votes without matching files.

Return concise evidence, statistics, confidence, dissent, and no-action triggers grouped by short-term, medium-term, long-term, then an overall conclusion.
