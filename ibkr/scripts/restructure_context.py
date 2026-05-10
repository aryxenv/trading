from __future__ import annotations

from argparse import ArgumentParser, Namespace
from decimal import Decimal

from ibkr.portfolio import require_full_portfolio
from ibkr.scripts.common import add_output_arg, read_snapshot, run
from ibkr.scripts.position_context import _holding_context


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Build full-portfolio restructure context.")
    parser.add_argument("--snapshot", required=True, help="Portfolio snapshot JSON path.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    snapshot = read_snapshot(args.snapshot)
    require_full_portfolio(snapshot)

    gross_positions = sum((abs(holding.market_value) for holding in snapshot.holdings), Decimal("0"))
    unrealized_pnl = sum((holding.unrealized_pnl or Decimal("0") for holding in snapshot.holdings), Decimal("0"))
    realized_pnl = sum((holding.realized_pnl or Decimal("0") for holding in snapshot.holdings), Decimal("0"))
    holdings = sorted(snapshot.holdings, key=lambda holding: abs(holding.market_value), reverse=True)

    warnings = list(snapshot.warnings)
    if not snapshot.cash:
        warnings.append("No cash balances returned by IBKR.")
    if not snapshot.account_values:
        warnings.append("No account summary values returned by IBKR.")

    return {
        "schema_version": "ibkr.restructure_context.v1",
        "account_id": snapshot.account_id,
        "as_of": snapshot.as_of.isoformat(),
        "gross_position_value": str(gross_positions),
        "available_cash": str(snapshot.available_cash()),
        "unrealized_pnl": str(unrealized_pnl),
        "realized_pnl": str(realized_pnl),
        "account_values": dict(snapshot.account_values),
        "top_concentrations": [_holding_context(holding, snapshot) for holding in holdings[:10]],
        "open_orders": [order.order_id for order in snapshot.open_orders],
        "execution_count": len(snapshot.executions),
        "warnings": warnings,
    }


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
