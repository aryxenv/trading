from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ibkr.client import LiveIBKRClient
from ibkr.scripts.common import add_output_arg, config_from_env, run, snapshot_json


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Load a rich live IBKR portfolio snapshot.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    client = LiveIBKRClient(config_from_env())
    try:
        return snapshot_json(client.load_portfolio_snapshot())
    finally:
        client.close()


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
