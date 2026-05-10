from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path

from ibkr.research_quality import has_blocking_issues, validate_council_record, validation_result
from ibkr.scripts.common import add_output_arg, print_json
from ibkr.serialization import write_json


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Validate a council record and member vote artifacts.")
    parser.add_argument("--input", required=True, type=Path, help="report-input.json or sandbox run directory.")
    parser.add_argument("--base-dir", type=Path, default=Path("."), help="Base directory for relative artifact paths.")
    parser.add_argument("--fail-on-warnings", action="store_true", help="Exit non-zero when warnings are present.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    issues = validate_council_record(args.input, base_dir=args.base_dir)
    return validation_result("council_record", args.input, issues)


def main() -> int:
    args = build_parser().parse_args()
    issues = validate_council_record(args.input, base_dir=args.base_dir)
    result = validation_result("council_record", args.input, issues)
    if args.output:
        write_json(args.output, result)
    else:
        print_json(result)
    return 1 if has_blocking_issues(issues, fail_on_warnings=args.fail_on_warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
