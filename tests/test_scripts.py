from __future__ import annotations

from argparse import Namespace
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ibkr import (
    CashBalance,
    ExecutiveDecisionRecord,
    Holding,
    NewsProvider,
    NewsSnapshot,
    OpenOrder,
    PortfolioSnapshot,
    news_snapshot_to_dict,
    snapshot_to_dict,
    write_executive_report,
)
from ibkr.client import _LiveIBKRApp
from ibkr.news import parse_provider_codes, realtime_headline
from ibkr.serialization import write_json


class DeterministicScriptTests(unittest.TestCase):
    def test_news_snapshot_serialization_and_provider_parsing(self) -> None:
        headline = realtime_headline(
            provider_code="brfg",
            article_id="A1",
            headline="{A:1:L:en}Cloudflare headline",
            timestamp=1_714_000_000_000,
            extra_data="NET",
        )
        data = news_snapshot_to_dict(
            NewsSnapshot(
                target="NET",
                con_id=123,
                contract_symbol="NET",
                providers=(NewsProvider(code="BRFG", name="Briefing.com"),),
                headlines=(headline,),
                warnings=("supplemental source",),
            )
        )

        self.assertEqual(parse_provider_codes("BRFG, brfupdn+DJNL"), ("BRFG", "BRFUPDN", "DJNL"))
        self.assertEqual(data["schema_version"], "ibkr.news_snapshot.v1")
        self.assertEqual(data["providers"][0]["code"], "BRFG")
        self.assertEqual(data["headlines"][0]["provider_code"], "BRFG")
        self.assertEqual(data["headlines"][0]["headline"], "Cloudflare headline")
        self.assertEqual(data["headlines"][0]["source"], "realtime")
        self.assertIn("2024", data["headlines"][0]["time"])

    def test_live_app_collects_and_deduplicates_news_callbacks(self) -> None:
        app = _LiveIBKRApp()
        provider = type("Provider", (), {"code": "brfg", "name": "Briefing.com"})()

        app.newsProviders([provider])
        app.tickNews(9202, 1_714_000_000_000, "BRFG", "A1", "Cloudflare headline", "NET")
        app.tickNews(9202, 1_714_000_000_000, "BRFG", "A1", "Cloudflare headline", "NET")
        app.historicalNews(9201, "20260510 12:00:00", "DJNL", "A2", "Older headline")
        app.error(9202, 366, "No news provider subscriptions found")

        self.assertTrue(app.news_providers_done.is_set())
        self.assertEqual(app.news_providers[0].code, "BRFG")
        self.assertEqual(len(app.news_headlines), 2)
        self.assertEqual(app.news_headlines[0].headline, "Cloudflare headline")
        self.assertIn("9202:366", app.request_errors[9202][0])

    def test_ibkr_news_script_uses_deterministic_client(self) -> None:
        from ibkr.scripts import ibkr_news

        test_case = self

        class FakeClient:
            closed = False

            def __init__(self, config) -> None:
                self.config = config

            def load_news_snapshot(
                self,
                target,
                providers=None,
                *,
                realtime_seconds=30.0,
                max_headlines=25,
                historical_limit=10,
            ) -> NewsSnapshot:
                test_case.assertEqual(target, "NET")
                test_case.assertEqual(providers, "BRFG")
                test_case.assertEqual(realtime_seconds, 0)
                test_case.assertEqual(max_headlines, 1)
                test_case.assertEqual(historical_limit, 0)
                return NewsSnapshot(
                    target=target,
                    providers=(NewsProvider(code="BRFG", name="Briefing.com"),),
                    headlines=(
                        realtime_headline(
                            provider_code="BRFG",
                            article_id="A1",
                            headline="Cloudflare headline",
                            timestamp=1_714_000_000_000,
                            extra_data="NET",
                        ),
                    ),
                )

            def close(self) -> None:
                type(self).closed = True

        with (
            patch.object(ibkr_news, "LiveIBKRClient", FakeClient),
            patch.object(ibkr_news, "config_from_env", lambda: object()),
        ):
            result = ibkr_news.main_impl(
                Namespace(
                    target="NET",
                    providers="BRFG",
                    realtime_seconds=0,
                    max_headlines=1,
                    historical_limit=0,
                )
            )

        self.assertTrue(FakeClient.closed)
        self.assertEqual(result["schema_version"], "ibkr.news_snapshot.v1")
        self.assertEqual(result["headlines"][0]["headline"], "Cloudflare headline")

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
                    "horizon_analysis": "short: watch; medium: watch; long: watch",
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
            self.assertIn(
                "**Horizon analysis:** short: watch; medium: watch; long: watch",
                report_path.read_text(encoding="utf-8"),
            )

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

    def test_write_report_collision_uses_run_id_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            reports_dir = base / "reports"
            report_input = base / "record.json"
            first_result = base / "first-result.json"
            second_result = base / "second-result.json"
            write_json(
                report_input,
                {
                    "run_id": "run-1",
                    "target": "GOOGL",
                    "thesis": "test thesis",
                    "horizon_analysis": "short: watch; medium: watch; long: watch",
                    "evidence": "test evidence",
                    "council_decision": "watch",
                    "confidence": "low",
                    "dissent": "none",
                    "proposed_action": "no action",
                    "confirmation_status": "not confirmed",
                },
            )

            first = _run_script(
                "ibkr.scripts.write_report",
                "--input",
                str(report_input),
                "--reports-dir",
                str(reports_dir),
                "--output",
                str(first_result),
            )
            second = _run_script(
                "ibkr.scripts.write_report",
                "--input",
                str(report_input),
                "--reports-dir",
                str(reports_dir),
                "--output",
                str(second_result),
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            first_data = json.loads(first_result.read_text(encoding="utf-8"))
            second_data = json.loads(second_result.read_text(encoding="utf-8"))
            self.assertEqual(first_data["path"], first_data["canonical_path"])
            self.assertEqual(second_data["collision_reason"], "canonical_exists")
            self.assertTrue(Path(second_data["path"]).stem.endswith("googl-run-1"))

    def test_research_packet_validator_accepts_complete_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            packet_path = _write_research_packet_fixture(base)
            output_path = base / "validation.json"

            result = _run_script(
                "ibkr.scripts.validate_research_packet",
                "--input",
                str(packet_path),
                "--base-dir",
                str(base),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(data["valid"])
            self.assertEqual(data["error_count"], 0)

    def test_research_packet_validator_rejects_empty_route_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            packet_path = _write_research_packet_fixture(base, write_findings=False)
            output_path = base / "validation.json"

            result = _run_script(
                "ibkr.scripts.validate_research_packet",
                "--input",
                str(packet_path),
                "--base-dir",
                str(base),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 1)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(data["valid"])
            self.assertTrue(any(issue["code"] == "route.findings_missing" for issue in data["issues"]))

    def test_research_packet_validator_flags_unsupported_agent_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            packet_path = _write_research_packet_fixture(base, unsupported_agent_claim=True)
            output_path = base / "validation.json"

            result = _run_script(
                "ibkr.scripts.validate_research_packet",
                "--input",
                str(packet_path),
                "--base-dir",
                str(base),
                "--fail-on-warnings",
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 1)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(any(issue["code"] == "finding.unsupported_agent_claim" for issue in data["issues"]))

    def test_research_packet_validator_rejects_prior_report_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            packet_path = _write_research_packet_fixture(base, prior_report_source=True)
            output_path = base / "validation.json"

            result = _run_script(
                "ibkr.scripts.validate_research_packet",
                "--input",
                str(packet_path),
                "--base-dir",
                str(base),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 1)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(any(issue["code"] == "finding.prior_report_source" for issue in data["issues"]))

    def test_council_record_validator_accepts_member_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            record_path = _write_council_record_fixture(base)
            output_path = base / "validation.json"

            result = _run_script(
                "ibkr.scripts.validate_council_record",
                "--input",
                str(record_path),
                "--base-dir",
                str(base),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(data["valid"])

    def test_council_record_validator_rejects_missing_vote_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            record_path = _write_council_record_fixture(base, write_votes=False)
            output_path = base / "validation.json"

            result = _run_script(
                "ibkr.scripts.validate_council_record",
                "--input",
                str(record_path),
                "--base-dir",
                str(base),
                "--output",
                str(output_path),
            )

            self.assertEqual(result.returncode, 1)
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(any(issue["code"] == "council.vote_missing" for issue in data["issues"]))

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


def _write_research_packet_fixture(
    base: Path,
    *,
    write_findings: bool = True,
    unsupported_agent_claim: bool = False,
    prior_report_source: bool = False,
) -> Path:
    run_id = "20260510-test-net"
    run_dir = base / "sandbox" / run_id
    run_dir.mkdir(parents=True)
    for name in ("symbol.json", "portfolio.json", "position-context.json", "target-context.json", "ibkr-news.json"):
        write_json(run_dir / name, {"fixture": name})

    routes = (
        ("short-term-1-3m", "short_term_1_3m"),
        ("medium-term-3-12m", "medium_term_3_12m"),
        ("long-term-1y-plus", "long_term_1y_plus"),
    )
    agent_routes = []
    for route_name, horizon in routes:
        folder = run_dir / route_name
        folder.mkdir()
        if write_findings:
            write_json(
                folder / "findings.json",
                {
                    "target": "NET",
                    "run_id": run_id,
                    "horizon": horizon,
                    "sources": [{"id": "src-1", "url": "https://example.com/net", "date": "2026-05-10"}],
                    "facts": [{"id": "fact-1", "text": "fixture fact"}],
                    "stats": [{"metric": "return_1m_pct", "value": "1.0"}],
                    "contrarian_evidence": ["fixture risk"],
                    "pruned_routes": ["fixture dead end"],
                    "missing_evidence": ["fixture gap"],
                    "no_action_triggers": ["fixture trigger"],
                    "confidence": "medium",
                },
            )
        agent_routes.append(
            {
                "name": route_name,
                "folder": f"sandbox\\{run_id}\\{route_name}",
                "route": "fixture route",
                "status": "completed",
            }
        )

    if prior_report_source:
        source = "reports\\20260510-net.md"
    elif unsupported_agent_claim:
        source = "market-research-agent summary"
    else:
        source = "https://example.com/net"
    finding = "agent-reported price was 100" if unsupported_agent_claim else "fixture sourced finding"
    packet_path = run_dir / "research-packet.json"
    write_json(
        packet_path,
        {
            "schema_version": "ibkr.research_packet.v1",
            "target": {"resolved_symbol": "NET", "resolved_name": "Cloudflare, Inc."},
            "run_id": run_id,
            "artifact_paths": {
                "symbol_resolution": f"sandbox\\{run_id}\\symbol.json",
                "portfolio_snapshot": f"sandbox\\{run_id}\\portfolio.json",
                "position_context": f"sandbox\\{run_id}\\position-context.json",
                "target_context": f"sandbox\\{run_id}\\target-context.json",
                "ibkr_news": f"sandbox\\{run_id}\\ibkr-news.json",
            },
            "agent_routes": agent_routes,
            "sourced_findings": [
                {
                    "finding": finding,
                    "source": source,
                    "date": "2026-05-10",
                    "horizons": list(HORIZONS_FOR_TESTS),
                    "confidence": "high",
                }
            ],
            "horizon_analysis": {horizon: {"decision_view": "watch"} for horizon in HORIZONS_FOR_TESTS},
        },
    )
    return packet_path


HORIZONS_FOR_TESTS = ("short_term_1_3m", "medium_term_3_12m", "long_term_1y_plus")


def _write_council_record_fixture(base: Path, *, write_votes: bool = True) -> Path:
    run_id = "20260510-test-net"
    run_dir = base / "sandbox" / run_id
    run_dir.mkdir(parents=True)
    member = "council-gpt-55"
    member_dir = run_dir / member
    member_dir.mkdir()
    if write_votes:
        decisions = {
            horizon: {
                "decision": "watch",
                "confidence": "medium",
                "evidence_ids": ["fact-1"],
                "disconfirming_evidence": ["fixture risk"],
            }
            for horizon in HORIZONS_FOR_TESTS
        }
        write_json(member_dir / "vote.json", {"member": member, "decisions": decisions, "overall": {"decision": "watch"}})
        write_json(member_dir / "critique.json", {"member": member, "strongest_opposing_view": "fixture"})

    record_path = run_dir / "report-input.json"
    write_json(
        record_path,
        {
            "schema_version": "ibkr.executive_decision_record_input.v1",
            "run_id": run_id,
            "target": "NET",
            "thesis": "fixture",
            "horizon_analysis": "fixture",
            "horizon_analysis_structured": {horizon: {"decision": "watch"} for horizon in HORIZONS_FOR_TESTS},
            "evidence": "fixture",
            "council_decision": "watch",
            "confidence": "medium",
            "dissent": "fixture",
            "proposed_action": "no action",
            "confirmation_status": "not confirmed",
            "council_process": {
                "members": [member],
                "vote_summary": {
                    **{horizon: {"votes": {member: "watch"}, "final_consensus": "watch"} for horizon in HORIZONS_FOR_TESTS},
                    "overall": {"votes": {member: "watch"}, "final_consensus": "watch"},
                },
            },
        },
    )
    return record_path


def _run_script(module: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        text=True,
        capture_output=True,
        input="",
        check=False,
    )
