"""Shared CLI helpers for deterministic IBKR scripts."""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from pathlib import Path
import sys
from typing import Any

from ibkr.config import IBKRConfig
from ibkr.portfolio import PortfolioSnapshot, snapshot_from_dict, snapshot_to_dict
from ibkr.serialization import read_json, write_json


MainFunc = Callable[[Namespace], dict[str, Any]]


def run(parser: ArgumentParser, func: MainFunc) -> int:
    args = parser.parse_args()
    try:
        result = func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = getattr(args, "output", None)
    if output:
        write_json(output, result)
    else:
        print_json(result)
    return 0


def print_json(data: Any) -> None:
    import json

    from ibkr.serialization import to_jsonable

    print(json.dumps(to_jsonable(data), indent=2, sort_keys=True))


def add_output_arg(parser: ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, help="Write JSON output to this path.")


def config_from_env() -> IBKRConfig:
    return IBKRConfig.from_env()


def read_snapshot(path: Path | str) -> PortfolioSnapshot:
    return snapshot_from_dict(read_json(path))


def snapshot_json(snapshot: PortfolioSnapshot) -> dict[str, Any]:
    return snapshot_to_dict(snapshot)
