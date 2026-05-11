---
name: risk-profiler
description: Derive or refresh local PROFILE.md from live IBKR portfolio context. WHEN - "profile me", "create my profile", "update my risk profile", "risk profile", "refresh PROFILE.md", "personalize decisions".
---

Purpose:

- Create or refresh `PROFILE.md` so trading research and council decisions have a deterministic risk/sizing basis.
- Keep the profile local and lean. `PROFILE.md` is ignored by git.

Inputs:

- Prefer a fresh IBKR snapshot from `uv run python -m ibkr.scripts.portfolio_snapshot --output sandbox/<run-id>/portfolio.json`.
- If the user explicitly says not to pull fresh data, use the latest same-day `sandbox/<run-id>/portfolio.json` snapshots and say so.

Steps:

1. Create `sandbox/<run-id>/` with a deterministic timestamp/slug.
2. Run or locate `portfolio.json`.
3. Derive:
   - net liquidation
   - gross position value and gross exposure %
   - cash / available funds and cash %
   - margin posture from margin fields
   - open order count
   - holding count
   - top 3, top 5, top 10 concentration
   - top holdings by NAV %
   - obvious exposure clusters from symbols and current holdings
   - speculative/thematic exposure where visible
   - largest winners/losers if useful
4. Write `PROFILE.md` with:
   - snapshot basis
   - observed portfolio posture
   - concentration map
   - decision gates for agents/council
   - agent interpretation notes
5. Do not include account id, secrets, credentials, or exact personal identifiers in `PROFILE.md`.
6. Keep decision gates deterministic:
   - starter high-volatility/thematic positions as NAV % bands
   - cash-buffer rule
   - concentration caps
   - speculative cluster cap
   - add/hold/trim/sell expectations for existing holdings
   - starter/watchlist/reject expectations for new targets
7. Ensure `.gitignore` contains `PROFILE.md`.
8. Do not place, stage, modify, cancel, submit, or prepare any trade/order intent.

Output:

- `PROFILE.md` updated.
- Brief summary: source snapshot, NAV, cash %, key concentration, main gates.
