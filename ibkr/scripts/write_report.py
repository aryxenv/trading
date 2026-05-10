from __future__ import annotations

from argparse import ArgumentParser, Namespace

from ibkr.audit import ExecutiveDecisionRecord, write_executive_report
from ibkr.scripts.common import add_output_arg, run
from ibkr.serialization import read_json


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Write an executive decision report.")
    parser.add_argument("--input", required=True, help="ExecutiveDecisionRecord JSON input path.")
    parser.add_argument("--reports-dir", default="reports", help="Directory for tracked executive reports.")
    add_output_arg(parser)
    return parser


def main_impl(args: Namespace) -> dict[str, object]:
    data = read_json(args.input)
    record = ExecutiveDecisionRecord(
        target=str(data["target"]),
        thesis=str(data["thesis"]),
        horizon_analysis=str(data.get("horizon_analysis", "")),
        evidence=str(data["evidence"]),
        council_decision=str(data["council_decision"]),
        confidence=str(data["confidence"]),
        dissent=str(data["dissent"]),
        proposed_action=str(data["proposed_action"]),
        confirmation_status=str(data["confirmation_status"]),
    )
    path = write_executive_report(record, reports_dir=args.reports_dir)
    return {"schema_version": "ibkr.write_report_result.v1", "path": str(path)}


def main() -> int:
    return run(build_parser(), main_impl)


if __name__ == "__main__":
    raise SystemExit(main())
