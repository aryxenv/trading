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
- Every trade idea must be grounded in web/news evidence, statistical checks, historical trends, top-down analysis, bias checks, and discarded weak routes.
- Prefer no action when evidence is stale, weak, conflicting, or risk limits are unspecified.
- Research agents must write scratch work under `sandbox/<run-id>/<agent-name>/`.
- Final executive decision records go in `reports/YYYYMMDD-<ticker-or-company>.md`.
- Use the bound skills in `.github/skills`; do not create free-floating skills.
