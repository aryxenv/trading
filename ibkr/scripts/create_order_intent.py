from __future__ import annotations

from argparse import ArgumentParser, Namespace
from decimal import Decimal

from ibkr.orders import OrderIntent, required_confirmation
from ibkr.scripts.common import add_output_arg, run
from ibkr.serialization import read_json


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Validate a report-backed live order intent.")
    parser.add_argument("--input", required=True, help="Order intent JSON input path.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    data = read_json(args.input)
    intent = _intent_from_json(data)
    return {
        "schema_version": "ibkr.validated_order_intent.v1",
        "intent": _intent_to_json(intent),
        "required_confirmation": required_confirmation(intent),
        "warnings": ["Do not submit unless the user types the exact confirmation into the interactive submit_order prompt."],
    }


def _intent_from_json(data: dict) -> OrderIntent:
    return OrderIntent(
        account_id=str(data["account_id"]),
        symbol=str(data["symbol"]),
        action=str(data["action"]).upper(),
        quantity=Decimal(str(data["quantity"])),
        order_type=str(data["order_type"]).upper(),
        research_report_path=str(data["research_report_path"]),
        rationale=str(data["rationale"]),
        time_in_force=str(data.get("time_in_force") or "DAY").upper(),
        limit_price=_optional_decimal(data.get("limit_price")),
        stop_price=_optional_decimal(data.get("stop_price")),
    )


def _intent_to_json(intent: OrderIntent) -> dict[str, object]:
    return {
        "account_id": intent.account_id,
        "symbol": intent.symbol,
        "action": intent.action,
        "quantity": str(intent.quantity),
        "order_type": intent.order_type,
        "time_in_force": intent.time_in_force,
        "limit_price": None if intent.limit_price is None else str(intent.limit_price),
        "stop_price": None if intent.stop_price is None else str(intent.stop_price),
        "research_report_path": intent.research_report_path,
        "rationale": intent.rationale,
    }


def _optional_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
