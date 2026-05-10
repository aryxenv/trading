from __future__ import annotations

from ibkr.scripts.position_context import build_parser, main_impl
from ibkr.scripts.common import run


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
