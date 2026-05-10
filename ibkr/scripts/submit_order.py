from __future__ import annotations

from argparse import ArgumentParser, Namespace
import sys

from ibkr.client import LiveIBKRClient
from ibkr.orders import confirm_live_order, required_confirmation
from ibkr.scripts.common import add_output_arg, config_from_env, run
from ibkr.scripts.create_order_intent import _intent_from_json
from ibkr.serialization import read_json


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Interactively submit a prevalidated live IBKR order intent.")
    parser.add_argument("--input", required=True, help="Validated order intent JSON from create_order_intent.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    data = read_json(args.input)
    if data.get("schema_version") != "ibkr.validated_order_intent.v1":
        raise ValueError("submit_order requires ibkr.validated_order_intent.v1 input.")
    intent = _intent_from_json(data["intent"])
    expected = required_confirmation(intent)

    if not sys.stdin.isatty():
        raise ValueError("submit_order requires an interactive terminal for user confirmation.")

    print("Type this exact phrase to submit the live IBKR order:")
    print(expected)
    supplied = input("Confirmation: ")
    confirmed = confirm_live_order(intent, supplied)

    client = LiveIBKRClient(config_from_env())
    try:
        submission = client.submit_confirmed_stock_order(confirmed)
    finally:
        client.close()

    return {"schema_version": "ibkr.submit_order_result.v1", "submission": submission, "symbol": intent.symbol}


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
