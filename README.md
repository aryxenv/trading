# IBKR Trading Research Orchestration

Agentic orchestration of trading on IBKR with Github Copilot agents. Starts with researching following a top-down approach, passes research onto council agents (GPT-5.5, Opus 4.6, Gemini 3.1 Pro) and defines actionable decision report.

It gives Copilot agents deterministic Python commands for:

- resolving company names to tickers
- loading live IBKR portfolio context
- building target or restructure context
- writing research/council reports
- validating order intent
- blocking live order submit until exact human confirmation

## Safety model

- Live IBKR only. Paper ports `4002` and `7497` are rejected.
- No trade can be placed from research alone.
- Every order needs current portfolio context, sourced research, council review, tracked report, and exact interactive user confirmation.
- If evidence, risk limits, or consensus are weak, default is no action.

## Setup

```powershell
uv venv
```

```powershell
uv sync
```

Set IBKR live API env vars:

```powershell
$env:IBKR_HOST = "127.0.0.1"
$env:IBKR_PORT = "7496"
$env:IBKR_CLIENT_ID = "7"
$env:IBKR_ACCOUNT_ID = "<your-live-account-id>"
```

Check config:

```powershell
uv run python -m ibkr.scripts.health_check
uv run python -m ibkr.scripts.health_check --connect
```

## Normal flow

Not to be done by user, give the input in natural language to Github Copilot / Copilot CLI and it will run everything for you.

1. User gives target, like `CLOUDFLARE` or `GOOGL`.
2. Resolve symbol:

   ```powershell
   uv run python -m ibkr.scripts.symbol_resolve --query CLOUDFLARE --output sandbox/run/symbol.json
   ```

3. Pull live portfolio:

   ```powershell
   uv run python -m ibkr.scripts.portfolio_snapshot --output sandbox/run/portfolio.json
   ```

4. Build target context:

   ```powershell
   uv run python -m ibkr.scripts.position_context --target NET --snapshot sandbox/run/portfolio.json --output sandbox/run/position-context.json
   uv run python -m ibkr.scripts.target_context --target NET --snapshot sandbox/run/portfolio.json --output sandbox/run/target-context.json
   ```

5. Run web-grounded research through `research-orchestrator`.
6. Run council review through `council-orchestrator`.
7. Write final report:

   ```powershell
   uv run python -m ibkr.scripts.write_report --input sandbox/run/report-input.json
   ```

8. If action exists, validate intent:

   ```powershell
   uv run python -m ibkr.scripts.create_order_intent --input sandbox/run/order-intent.json --output sandbox/run/validated-intent.json
   ```

9. Submit only after exact user confirmation in interactive terminal:

   ```powershell
   uv run python -m ibkr.scripts.submit_order --input sandbox/run/validated-intent.json
   ```

## Portfolio restructure flow

1. Pull live portfolio.
2. Build restructure context:

   ```powershell
   uv run python -m ibkr.scripts.restructure_context --snapshot sandbox/run/portfolio.json --output sandbox/run/restructure-context.json
   ```

3. Run holding-level context for each affected ticker.
4. Use `portfolio-restructure-agent`.
5. Send packet to council.
6. Act only through trade execution gate.

## Agent roles

- `research-orchestrator`: turns ticker/company input into research run.
- `market-research-agent`: independent web/stat route in own `sandbox/` folder.
- `council-orchestrator`: runs model council and records decision.
- `portfolio-restructure-agent`: uses full portfolio context for rebalance work.
- `trade-execution-gate`: final order safety gate.

Reports go in `reports/`. Agent scratch work goes in `sandbox/`.
