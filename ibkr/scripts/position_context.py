from __future__ import annotations

from argparse import ArgumentParser, Namespace
from decimal import Decimal

from ibkr.portfolio import Holding, context_for_target, snapshot_to_dict
from ibkr.scripts.common import add_output_arg, read_snapshot, run


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Build target-specific holding/new-investment context.")
    parser.add_argument("--target", required=True, help="Ticker or company name.")
    parser.add_argument("--snapshot", required=True, help="Portfolio snapshot JSON path.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    snapshot = read_snapshot(args.snapshot)
    context = context_for_target(snapshot, args.target)
    warnings = list(snapshot.warnings)
    if context.holding is None:
        warnings.append("Target is not currently held; treat as a new investment using cash and shift candidates.")

    return {
        "schema_version": "ibkr.position_context.v1",
        "target": context.target,
        "mode": context.mode,
        "available_cash": str(context.available_cash),
        "holding": _holding_context(context.holding, snapshot) if context.holding else None,
        "shift_candidates": [_holding_context(holding, snapshot) for holding in context.shift_candidates],
        "portfolio": snapshot_to_dict(snapshot),
        "warnings": warnings,
    }


def _holding_context(holding: Holding, snapshot) -> dict[str, object]:
    total = _net_liquidation(snapshot)
    allocation = holding.market_value / total if total and total != 0 else None
    return {
        "symbol": holding.symbol,
        "quantity": str(holding.quantity),
        "market_price": _str_or_none(holding.market_price),
        "market_value": str(holding.market_value),
        "average_cost": _str_or_none(holding.average_cost),
        "cost_basis": _str_or_none(holding.cost_basis),
        "unrealized_pnl": _str_or_none(holding.unrealized_pnl),
        "realized_pnl": _str_or_none(holding.realized_pnl),
        "gain_loss_pct": _str_or_none(holding.gain_loss_pct),
        "allocation_pct": _str_or_none(allocation),
        "currency": holding.currency,
        "con_id": holding.con_id,
        "sec_type": holding.sec_type,
        "exchange": holding.exchange,
    }


def _net_liquidation(snapshot) -> Decimal | None:
    for key, value in snapshot.account_values.items():
        if "NetLiquidation" in key:
            return Decimal(str(value))
    total = sum((holding.market_value for holding in snapshot.holdings), Decimal("0"))
    cash = snapshot.available_cash()
    return total + cash if total or cash else None


def _str_or_none(value) -> str | None:
    return None if value is None else str(value)


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
