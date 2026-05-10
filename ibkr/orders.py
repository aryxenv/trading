"""Live order intent and confirmation gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from ibapi.order import Order


Action = Literal["BUY", "SELL"]
OrderType = Literal["MKT", "LMT", "STP", "STP LMT"]
TimeInForce = Literal["DAY", "GTC", "IOC"]


class OrderIntentError(ValueError):
    """Raised when a live order intent is unsafe or incomplete."""


@dataclass(frozen=True)
class OrderIntent:
    account_id: str
    symbol: str
    action: Action
    quantity: Decimal
    order_type: OrderType
    research_report_path: str
    rationale: str
    time_in_force: TimeInForce = "DAY"
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None

    def __post_init__(self) -> None:
        account_id = self.account_id.strip()
        symbol = self.symbol.strip().upper()
        action = self.action.upper()
        order_type = self.order_type.upper()
        time_in_force = self.time_in_force.upper()

        if not account_id:
            raise OrderIntentError("Account ID is required for live order intent.")
        if not symbol:
            raise OrderIntentError("Symbol is required for live order intent.")
        if action not in {"BUY", "SELL"}:
            raise OrderIntentError("Action must be BUY or SELL.")
        if self.quantity <= 0:
            raise OrderIntentError("Quantity must be positive.")
        if order_type not in {"MKT", "LMT", "STP", "STP LMT"}:
            raise OrderIntentError("Unsupported order type.")
        if time_in_force not in {"DAY", "GTC", "IOC"}:
            raise OrderIntentError("Unsupported time in force.")
        if order_type in {"LMT", "STP LMT"} and self.limit_price is None:
            raise OrderIntentError("Limit price is required for limit orders.")
        if order_type in {"STP", "STP LMT"} and self.stop_price is None:
            raise OrderIntentError("Stop price is required for stop orders.")
        if not self.research_report_path.strip():
            raise OrderIntentError("Grounded research report path is required.")
        report_path = Path(self.research_report_path)
        if not report_path.is_file():
            raise OrderIntentError("Grounded research report must exist before creating a live order intent.")
        if "reports" not in report_path.parts:
            raise OrderIntentError("Live order intents must reference a tracked report under reports.")
        if not self.rationale.strip():
            raise OrderIntentError("Order rationale is required.")

        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "order_type", order_type)
        object.__setattr__(self, "time_in_force", time_in_force)


@dataclass(frozen=True)
class ConfirmedOrderIntent:
    intent: OrderIntent
    confirmation_text: str
    confirmed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def required_confirmation(intent: OrderIntent) -> str:
    price_parts: list[str] = []
    if intent.limit_price is not None:
        price_parts.append(f"LIMIT {_format_decimal(intent.limit_price)}")
    if intent.stop_price is not None:
        price_parts.append(f"STOP {_format_decimal(intent.stop_price)}")
    prices = " ".join(price_parts) if price_parts else "NO PRICE"
    return (
        "CONFIRM LIVE IBKR "
        f"{intent.account_id} {intent.action} {_format_decimal(intent.quantity)} "
        f"{intent.symbol} {intent.order_type} {prices} TIF {intent.time_in_force}"
    )


def confirm_live_order(intent: OrderIntent, confirmation_text: str) -> ConfirmedOrderIntent:
    expected = required_confirmation(intent)
    supplied = confirmation_text.strip()
    if supplied != expected:
        raise OrderIntentError(f"Confirmation mismatch. Expected exactly: {expected}")
    return ConfirmedOrderIntent(intent=intent, confirmation_text=supplied)


def build_ibapi_order(confirmed: ConfirmedOrderIntent, *, transmit: bool = True, what_if: bool = False) -> Order:
    intent = confirmed.intent
    order = Order()
    order.account = intent.account_id
    order.action = intent.action
    order.totalQuantity = float(intent.quantity)
    order.orderType = intent.order_type
    order.tif = intent.time_in_force
    order.transmit = transmit
    order.whatIf = what_if
    if intent.limit_price is not None:
        order.lmtPrice = float(intent.limit_price)
    if intent.stop_price is not None:
        order.auxPrice = float(intent.stop_price)
    return order


def _format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
