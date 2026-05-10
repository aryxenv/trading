# IBKR Trading Research Orchestration

Agentic orchestration of trading on IBKR with Github Copilot agents. Starts with researching following a top-down approach, passes research onto council agents (GPT-5.5, Opus 4.6, Gemini 3.1 Pro) and defines actionable decision report.

It gives Copilot agents deterministic Python commands for:

- resolving company names to tickers
- loading live IBKR portfolio context
- loading supplemental subscribed IBKR API news
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

Install one official IBKR app:

- Trader Workstation: https://www.interactivebrokers.com/en/trading/tws.php -> Get TWS.
- IB Gateway: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php.

Use TWS if you want full desktop UI. Use IB Gateway if you want a lighter app for API access. Log in with your live IBKR account, then enable API/socket access in the app settings.

On TWS, make sure to turn off "Read-Only API", unless you explicitly do not want to make actions via API.

Create local config:

```powershell
cp .env.example .env
```

Then fill `.env`:

- `IBKR_HOST`: TWS/IB Gateway host, usually `127.0.0.1`.
- `IBKR_PORT`: live API socket port from TWS/IB Gateway API settings, usually `7496`. Paper ports are blocked.
- `IBKR_CLIENT_ID`: stable API client id, default `7`.
- `IBKR_ACCOUNT_ID`: live account id from IBKR/TWS account selector.
- `IBKR_TIMEOUT_SECONDS`: API timeout, default `30`.

Where to find values:

- Host: use `127.0.0.1` when TWS/IB Gateway runs on this machine.
- Port: TWS/IB Gateway -> API settings -> Socket port. Live TWS is usually `7496`; live IB Gateway is usually `4001`.
- Client ID: choose any unused integer. Keep `7` unless TWS says client id already connected.
- Account ID: TWS account selector or Account Window, or IBKR Client Portal account selector. Use live account id, not paper.
- Timeout: keep `30` unless your local IBKR connection is slow.

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

5. Load subscribed IBKR API news:

   ```powershell
   uv run python -m ibkr.scripts.ibkr_news --target NET --output sandbox/run/ibkr-news.json
   ```

6. Run web-grounded research through `research-orchestrator`; it writes the research packet and invokes `council-orchestrator`.
7. The council writes the final report by running:

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
4. Use `portfolio-restructure-agent`; it writes the restructure packet and invokes `council-orchestrator`.
5. Act only through trade execution gate.

## Agent roles

- `research-orchestrator`: turns ticker/company input into research run.
- `market-research-agent`: independent web/stat route in own `sandbox/` folder.
- `council-orchestrator`: runs model council and records decision.
- `portfolio-restructure-agent`: uses full portfolio context for rebalance work.
- `trade-execution-gate`: final order safety gate.

Reports go in `reports/`. Agent scratch work goes in `sandbox/`.
