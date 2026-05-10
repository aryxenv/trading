# Copilot instructions

- This is a Python `>=3.11` project for IBKR-backed trading research and execution safeguards.
- Always use `uv`: `uv run ...` for commands and `uv add ...` for dependencies.
- Keep Markdown lean, factual, and easy to scan.
- Use IBKR for portfolio context and trading workflows. Never use mock portfolio facts when IBKR data is required.
- Treat a prompt that is only a ticker or company name as a research-orchestrator request.
- Treat portfolio restructure requests as full-portfolio IBKR analysis, not single-name research.
- For ticker/company research, use the user's IBKR data for the affected holding. If there is no holding, analyze it as a potential new investment using available cash and possible portfolio shifts.
- Live trading only. Do not assume or switch to paper trading.
- Never place, stage, modify, cancel, or submit any trade without explicit confirmation of the exact live order details.
- Do not write ad hoc IBKR access code. Use deterministic commands under `ibkr.scripts`.
- For IBKR context, run `uv run python -m ibkr.scripts.portfolio_snapshot --output sandbox/<run-id>/portfolio.json`, then derive target or restructure context from that snapshot.
- For company names or typo-prone inputs, first run `uv run python -m ibkr.scripts.symbol_resolve --query <input> --output sandbox/<run-id>/symbol.json` and pass the resolved ticker to later scripts.
- For ticker/company research, run `uv run python -m ibkr.scripts.ibkr_news --target <resolved-symbol> --output sandbox/<run-id>/ibkr-news.json`; treat it as supplemental to web news.
- For order intent, run `uv run python -m ibkr.scripts.create_order_intent`; live submit is only through interactive `uv run python -m ibkr.scripts.submit_order`.
- Every trade idea must be grounded in web/news evidence, statistical checks, historical trends, top-down analysis, bias checks, and discarded weak routes.
- Prefer no action when evidence is stale, weak, conflicting, or risk limits are unspecified.
- Research agents must write scratch work under `sandbox/<run-id>/<agent-name>/`.
- Final executive decision records go in `reports/YYYYMMDD-<ticker-or-company>.md`.
