from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ibkr import (
    CashBalance,
    ExecutiveDecisionRecord,
    Holding,
    OpenOrder,
    PortfolioSnapshot,
    snapshot_to_dict,
    write_executive_report,
)
from ibkr.serialization import write_json


class DeterministicScriptTests(unittest.TestCase):
    def test_symbol_resolve_from_yahoo_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            response_path = base / "yahoo.json"
            output_path = base / "symbol.json"
            write_json(response_path, _yahoo_cloudflare_fixture())

            result = _run_script(
                "ibkr.scripts.symbol_resolve",
                "--query",
                "CLOUDFLARE",
                "--response-json",
                str(response_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "ibkr.symbol_resolution.v1")
            self.assertEqual(data["resolved_symbol"], "NET")
            self.assertEqual(data["confidence"], "high")

    def test_symbol_resolve_typo_uses_candidates_and_warns_on_close_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            response_path = base / "yahoo.json"
            output_path = base / "symbol.json"
            fixture = _yahoo_cloudflare_fixture()
            fixture["quotes"].insert(
                1,
                {
                    "exchange": "NYQ",
                    "shortname": "Close Candidate, Inc.",
                    "quoteType": "EQUITY",
                    "symbol": "NXT",
                    "score": 20500.0,
                    "longname": "Close Candidate, Inc.",
                    "exchDisp": "NYSE",
                },
            )
            write_json(response_path, fixture)

            result = _run_script(
                "ibkr.scripts.symbol_resolve",
                "--query",
                "cloudfare",
                "--response-json",
                str(response_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["resolved_symbol"], "NET")
            self.assertTrue(any("close" in warning for warning in data["warnings"]))

    def test_position_context_existing_holding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            snapshot_path = base / "portfolio.json"
            output_path = base / "position.json"
            write_json(snapshot_path, _snapshot_fixture())

            result = _run_script(
                "ibkr.scripts.position_context",
                "--target",
                "GOOGL",
                "--snapshot",
                str(snapshot_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "ibkr.position_context.v1")
            self.assertEqual(data["mode"], "existing_holding")
            self.assertEqual(data["holding"]["quantity"], "2")
            self.assertEqual(data["available_cash"], "1000")
            self.assertEqual(data["shift_candidates"][0]["symbol"], "MSFT")

    def test_position_context_new_investment_warns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            snapshot_path = base / "portfolio.json"
            output_path = base / "position.json"
            write_json(snapshot_path, _snapshot_fixture())

            result = _run_script(
                "ibkr.scripts.position_context",
                "--target",
                "NET",
                "--snapshot",
                str(snapshot_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["mode"], "new_investment")
            self.assertTrue(any("not currently held" in warning for warning in data["warnings"]))

    def test_restructure_context_preserves_rich_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            snapshot_path = base / "portfolio.json"
            output_path = base / "restructure.json"
            write_json(snapshot_path, _snapshot_fixture())

            result = _run_script(
                "ibkr.scripts.restructure_context",
                "--snapshot",
                str(snapshot_path),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "ibkr.restructure_context.v1")
            self.assertEqual(data["available_cash"], "1000")
            self.assertEqual(data["unrealized_pnl"], "50")
            self.assertEqual(data["execution_count"], 0)
            self.assertEqual(data["top_concentrations"][0]["symbol"], "MSFT")

    def test_write_report_and_create_order_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            report_input = base / "record.json"
            reports_dir = base / "reports"
            report_result = base / "report-result.json"
            write_json(
                report_input,
                {
                    "target": "GOOGL",
                    "thesis": "test thesis",
                    "evidence": "test evidence",
                    "council_decision": "watch",
                    "confidence": "low",
                    "dissent": "none",
                    "proposed_action": "no action",
                    "confirmation_status": "not confirmed",
                },
            )

            result = _run_script(
                "ibkr.scripts.write_report",
                "--input",
                str(report_input),
                "--reports-dir",
                str(reports_dir),
                "--output",
                str(report_result),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report_path = Path(json.loads(report_result.read_text(encoding="utf-8"))["path"])
            self.assertTrue(report_path.is_file())

            intent_input = base / "intent.json"
            intent_output = base / "validated.json"
            write_json(
                intent_input,
                {
                    "account_id": "DU123",
                    "symbol": "GOOGL",
                    "action": "BUY",
                    "quantity": "1",
                    "order_type": "LMT",
                    "time_in_force": "DAY",
                    "limit_price": "100",
                    "research_report_path": str(report_path),
                    "rationale": "Grounded test rationale.",
                },
            )

            result = _run_script(
                "ibkr.scripts.create_order_intent",
                "--input",
                str(intent_input),
                "--output",
                str(intent_output),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            validated = json.loads(intent_output.read_text(encoding="utf-8"))
            self.assertEqual(validated["schema_version"], "ibkr.validated_order_intent.v1")
            self.assertEqual(
                validated["required_confirmation"],
                "CONFIRM LIVE IBKR DU123 BUY 1 GOOGL LMT LIMIT 100 TIF DAY",
            )

    def test_submit_order_refuses_noninteractive_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            report_path = write_executive_report(
                ExecutiveDecisionRecord(
                    target="GOOGL",
                    thesis="test",
                    evidence="test",
                    council_decision="watch",
                    confidence="low",
                    dissent="none",
                    proposed_action="none",
                    confirmation_status="not confirmed",
                ),
                reports_dir=base / "reports",
                current_date=date(2026, 5, 10),
            )
            validated_path = base / "validated.json"
            write_json(
                validated_path,
                {
                    "schema_version": "ibkr.validated_order_intent.v1",
                    "intent": {
                        "account_id": "DU123",
                        "symbol": "GOOGL",
                        "action": "BUY",
                        "quantity": "1",
                        "order_type": "MKT",
                        "time_in_force": "DAY",
                        "limit_price": None,
                        "stop_price": None,
                        "research_report_path": str(report_path),
                        "rationale": "Grounded test rationale.",
                    },
                    "required_confirmation": "CONFIRM LIVE IBKR DU123 BUY 1 GOOGL MKT NO PRICE TIF DAY",
                },
            )

            result = _run_script("ibkr.scripts.submit_order", "--input", str(validated_path))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("interactive terminal", result.stderr)


def _snapshot_fixture() -> dict:
    return snapshot_to_dict(
        PortfolioSnapshot(
            account_id="DU123",
            holdings=(
                Holding(
                    symbol="GOOGL",
                    quantity=Decimal("2"),
                    market_value=Decimal("300"),
                    market_price=Decimal("150"),
                    average_cost=Decimal("125"),
                    unrealized_pnl=Decimal("50"),
                    realized_pnl=Decimal("0"),
                    con_id=123,
                    sec_type="STK",
                    exchange="SMART",
                ),
                Holding(symbol="MSFT", quantity=Decimal("1"), market_value=Decimal("400")),
            ),
            cash=(
                CashBalance(currency="USD", amount=Decimal("1000"), kind="AvailableFunds"),
                CashBalance(currency="USD", amount=Decimal("2000"), kind="TotalCashValue"),
            ),
            account_values={"DU123:NetLiquidation:USD": "1700", "DU123:BuyingPower:USD": "2500"},
            open_orders=(
                OpenOrder(order_id=1, symbol="GOOGL", action="BUY", quantity=Decimal("1"), order_type="LMT", status="Submitted"),
            ),
            warnings=("fixture warning",),
            as_of=datetime(2026, 5, 10, tzinfo=timezone.utc),
        )
    )


def _yahoo_cloudflare_fixture() -> dict:
    return {
        "quotes": [
            {
                "exchange": "NYQ",
                "shortname": "Cloudflare, Inc.",
                "quoteType": "EQUITY",
                "symbol": "NET",
                "score": 20619.0,
                "longname": "Cloudflare, Inc.",
                "exchDisp": "NYSE",
                "sector": "Technology",
                "industry": "Software-Infrastructure",
            },
            {
                "exchange": "DUS",
                "shortname": "Cloudflare Inc.",
                "quoteType": "EQUITY",
                "symbol": "8CF.DU",
                "score": 20002.0,
                "longname": "Cloudflare, Inc.",
                "exchDisp": "Dusseldorf Stock Exchange",
            },
        ]
    }


def _run_script(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        text=True,
        capture_output=True,
        input="",
        check=False,
    )
