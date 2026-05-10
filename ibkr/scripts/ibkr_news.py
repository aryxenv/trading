from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ibkr.client import LiveIBKRClient
from ibkr.news import news_snapshot_to_dict
from ibkr.scripts.common import add_output_arg, config_from_env, run


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Collect subscribed IBKR API news headlines for a ticker.")
    parser.add_argument("--target", required=True, help="Resolved ticker symbol, for example NET or GOOGL.")
    parser.add_argument(
        "--providers",
        help="Optional provider filter, separated by + or comma. Default uses all subscribed IBKR API news providers.",
    )
    parser.add_argument("--realtime-seconds", type=float, default=30.0, help="Seconds to listen for realtime headlines.")
    parser.add_argument("--max-headlines", type=int, default=25, help="Maximum headlines to return.")
    parser.add_argument("--historical-limit", type=int, default=10, help="Historical headlines to request before realtime.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    client = LiveIBKRClient(config_from_env())
    try:
        snapshot = client.load_news_snapshot(
            args.target,
            providers=args.providers,
            realtime_seconds=args.realtime_seconds,
            max_headlines=args.max_headlines,
            historical_limit=args.historical_limit,
        )
        return news_snapshot_to_dict(snapshot)
    finally:
        client.close()


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
