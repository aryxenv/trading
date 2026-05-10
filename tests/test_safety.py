from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from ibkr import (
    CashBalance,
    ExecutiveDecisionRecord,
    Holding,
    IBKRConfig,
    IBKRConfigError,
    OrderIntent,
    OrderIntentError,
    PortfolioSnapshot,
    confirm_live_order,
    context_for_target,
    report_path,
    required_confirmation,
    require_full_portfolio,
    write_executive_report,
)


class SafetyScaffoldTests(unittest.TestCase):
    def test_rejects_paper_ports(self) -> None:
        with self.assertRaises(IBKRConfigError):
            IBKRConfig(port=7497)

    def test_target_context_uses_existing_holding(self) -> None:
        snapshot = PortfolioSnapshot(
            account_id="DU123",
            holdings=(
                Holding(symbol="GOOGL", quantity=Decimal("2"), market_value=Decimal("300")),
                Holding(symbol="MSFT", quantity=Decimal("1"), market_value=Decimal("400")),
            ),
            cash=(CashBalance(currency="USD", amount=Decimal("1000")),),
        )

        context = context_for_target(snapshot, "GOOGL")

        self.assertEqual(context.mode, "existing_holding")
        self.assertEqual(context.holding.symbol if context.holding else None, "GOOGL")
        self.assertEqual(context.available_cash, Decimal("1000"))
        self.assertEqual(context.shift_candidates[0].symbol, "MSFT")

    def test_target_context_uses_new_investment_path(self) -> None:
        snapshot = PortfolioSnapshot(
            account_id="DU123",
            holdings=(Holding(symbol="MSFT", quantity=Decimal("1"), market_value=Decimal("400")),),
            cash=(CashBalance(currency="USD", amount=Decimal("1000")),),
        )

        context = context_for_target(snapshot, "Cloudflare")

        self.assertEqual(context.mode, "new_investment")
        self.assertIsNone(context.holding)
        self.assertEqual(context.available_cash, Decimal("1000"))
        self.assertEqual(context.shift_candidates[0].symbol, "MSFT")

    def test_restructure_requires_portfolio_data(self) -> None:
        with self.assertRaises(ValueError):
            require_full_portfolio(PortfolioSnapshot(account_id="DU123"))

    def test_report_path_uses_requested_format(self) -> None:
        path = report_path("Cloudflare Inc.", current_date=date(2026, 5, 10))

        self.assertEqual(path, Path("reports") / "20260510-cloudflare-inc.md")

    def test_order_confirmation_is_exact_and_report_backed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            reports_dir = Path(temp_dir) / "reports"
            report = write_executive_report(
                ExecutiveDecisionRecord(
                    target="GOOGL",
                    thesis="test thesis",
                    evidence="test evidence",
                    council_decision="watch",
                    confidence="low",
                    dissent="none",
                    proposed_action="no action",
                    confirmation_status="not confirmed",
                ),
                reports_dir=reports_dir,
                current_date=date(2026, 5, 10),
            )
            intent = OrderIntent(
                account_id="DU123",
                symbol="GOOGL",
                action="BUY",
                quantity=Decimal("1"),
                order_type="LMT",
                limit_price=Decimal("100"),
                research_report_path=str(report),
                rationale="Confirmed after grounded council review.",
            )

            phrase = required_confirmation(intent)

            self.assertEqual(
                phrase,
                "CONFIRM LIVE IBKR DU123 BUY 1 GOOGL LMT LIMIT 100 TIF DAY",
            )
            self.assertEqual(confirm_live_order(intent, phrase).confirmation_text, phrase)
            with self.assertRaises(OrderIntentError):
                confirm_live_order(intent, "confirm")

    def test_order_intent_requires_tracked_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            untracked = Path(temp_dir) / "note.md"
            untracked.write_text("not a tracked report", encoding="utf-8")

            with self.assertRaises(OrderIntentError):
                OrderIntent(
                    account_id="DU123",
                    symbol="GOOGL",
                    action="BUY",
                    quantity=Decimal("1"),
                    order_type="MKT",
                    research_report_path=str(untracked),
                    rationale="Not grounded in tracked report.",
                )


if __name__ == "__main__":
    unittest.main()
