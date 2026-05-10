from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ibkr.client import LiveIBKRClient
from ibkr.scripts.common import add_output_arg, config_from_env, run


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Validate IBKR live configuration and optional connectivity.")
    parser.add_argument("--connect", action="store_true", help="Attempt a live IBKR API connection.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    config = config_from_env()
    result: dict[str, object] = {
        "schema_version": "ibkr.health_check.v1",
        "host": config.host,
        "port": config.port,
        "client_id": config.client_id,
        "account_id_configured": config.account_id is not None,
        "connectivity": "not_checked",
        "warnings": [],
    }
    if config.account_id is None:
        result["warnings"] = ["IBKR_ACCOUNT_ID is not configured; portfolio scripts will fail closed."]

    if args.connect:
        client = LiveIBKRClient(config)
        try:
            client.connect()
            result["connectivity"] = "connected"
        finally:
            client.close()
    return result


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
