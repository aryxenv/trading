from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ibkr.scripts.common import add_output_arg, run
from ibkr.serialization import read_json
from ibkr.symbols import resolve_from_yahoo_response, resolve_symbol


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Resolve a company name or ticker to a likely Yahoo/IBKR ticker.")
    parser.add_argument("--query", required=True, help="Company name or ticker, including imperfect names like CLOUDFLARE.")
    parser.add_argument("--quotes-count", type=int, default=8, help="Number of Yahoo Finance candidates to request.")
    parser.add_argument("--country", default="United States", help="Yahoo Finance search country hint.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    parser.add_argument("--response-json", help="Use a saved Yahoo Finance response JSON instead of calling the endpoint.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    if args.response_json:
        resolution = resolve_from_yahoo_response(args.query, read_json(args.response_json))
    else:
        resolution = resolve_symbol(
            args.query,
            quotes_count=args.quotes_count,
            country=args.country,
            timeout=args.timeout,
        )
    return resolution.to_dict()


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
