"""Portfolio context models for IBKR-backed analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Mapping


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: Decimal
    market_value: Decimal
    currency: str = "USD"
    market_price: Decimal | None = None
    average_cost: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal | None = None
    company_name: str | None = None
    sector: str | None = None
    con_id: int | None = None
    sec_type: str | None = None
    exchange: str | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("Holding symbol is required.")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "currency", self.currency.strip().upper() or "USD")

    def matches(self, target: str) -> bool:
        normalized = target.strip().casefold()
        return normalized == self.symbol.casefold() or (
            self.company_name is not None and normalized == self.company_name.strip().casefold()
        )

    @property
    def cost_basis(self) -> Decimal | None:
        if self.average_cost is None:
            return None
        return self.average_cost * self.quantity

    @property
    def gain_loss_pct(self) -> Decimal | None:
        basis = self.cost_basis
        if basis is None or basis == 0 or self.unrealized_pnl is None:
            return None
        return self.unrealized_pnl / basis


@dataclass(frozen=True)
class CashBalance:
    currency: str
    amount: Decimal
    kind: str = "AvailableFunds"

    def __post_init__(self) -> None:
        if not self.currency.strip():
            raise ValueError("Cash currency is required.")
        object.__setattr__(self, "currency", self.currency.strip().upper())


@dataclass(frozen=True)
class OpenOrder:
    order_id: int
    symbol: str
    action: str
    quantity: Decimal
    order_type: str
    status: str | None = None
    time_in_force: str | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "action", self.action.strip().upper())
        object.__setattr__(self, "order_type", self.order_type.strip().upper())


@dataclass(frozen=True)
class Execution:
    execution_id: str
    symbol: str
    side: str
    shares: Decimal
    price: Decimal
    time: str | None = None
    account_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "side", self.side.strip().upper())


@dataclass(frozen=True)
class PortfolioSnapshot:
    account_id: str | None
    holdings: tuple[Holding, ...] = ()
    cash: tuple[CashBalance, ...] = ()
    account_values: Mapping[str, str] = field(default_factory=dict)
    open_orders: tuple[OpenOrder, ...] = ()
    executions: tuple[Execution, ...] = ()
    warnings: tuple[str, ...] = ()
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def holding_for(self, target: str) -> Holding | None:
        for holding in self.holdings:
            if holding.matches(target):
                return holding
        return None

    def available_cash(self, currency: str = "USD") -> Decimal:
        target_currency = currency.strip().upper()
        for preferred_kind in ("AvailableFunds", "TotalCashValue", "CashBalance"):
            for balance in self.cash:
                if balance.currency == target_currency and balance.kind == preferred_kind:
                    return balance.amount
        return Decimal("0")

    def shift_candidates(self, excluded_symbol: str | None = None, limit: int = 5) -> tuple[Holding, ...]:
        excluded = excluded_symbol.upper() if excluded_symbol else None
        candidates = [holding for holding in self.holdings if holding.symbol != excluded]
        candidates.sort(key=lambda holding: abs(holding.market_value), reverse=True)
        return tuple(candidates[:limit])


TargetMode = Literal["existing_holding", "new_investment"]


@dataclass(frozen=True)
class TargetContext:
    target: str
    mode: TargetMode
    holding: Holding | None
    available_cash: Decimal
    shift_candidates: tuple[Holding, ...]


def context_for_target(snapshot: PortfolioSnapshot, target: str, currency: str = "USD") -> TargetContext:
    if not target.strip():
        raise ValueError("Target ticker or company is required.")

    holding = snapshot.holding_for(target)
    if holding is not None:
        return TargetContext(
            target=target.strip(),
            mode="existing_holding",
            holding=holding,
            available_cash=snapshot.available_cash(currency),
            shift_candidates=snapshot.shift_candidates(excluded_symbol=holding.symbol),
        )

    return TargetContext(
        target=target.strip(),
        mode="new_investment",
        holding=None,
        available_cash=snapshot.available_cash(currency),
        shift_candidates=snapshot.shift_candidates(),
    )


def require_full_portfolio(snapshot: PortfolioSnapshot) -> None:
    if not snapshot.holdings and not snapshot.cash:
        raise ValueError("Full IBKR portfolio snapshot is required for restructure analysis.")


def snapshot_to_dict(snapshot: PortfolioSnapshot) -> dict[str, Any]:
    return {
        "schema_version": "ibkr.portfolio_snapshot.v1",
        "account_id": snapshot.account_id,
        "as_of": snapshot.as_of.isoformat(),
        "account_values": dict(snapshot.account_values),
        "cash": [_cash_to_dict(balance) for balance in snapshot.cash],
        "holdings": [_holding_to_dict(holding, snapshot) for holding in snapshot.holdings],
        "open_orders": [_open_order_to_dict(order) for order in snapshot.open_orders],
        "executions": [_execution_to_dict(execution) for execution in snapshot.executions],
        "warnings": list(snapshot.warnings),
    }


def snapshot_from_dict(data: Mapping[str, Any]) -> PortfolioSnapshot:
    if data.get("schema_version") != "ibkr.portfolio_snapshot.v1":
        raise ValueError("Unsupported portfolio snapshot schema_version.")
    as_of_raw = data.get("as_of")
    as_of = datetime.fromisoformat(as_of_raw) if isinstance(as_of_raw, str) else datetime.now(timezone.utc)
    return PortfolioSnapshot(
        account_id=data.get("account_id"),
        holdings=tuple(_holding_from_dict(item) for item in data.get("holdings", [])),
        cash=tuple(_cash_from_dict(item) for item in data.get("cash", [])),
        account_values=dict(data.get("account_values", {})),
        open_orders=tuple(_open_order_from_dict(item) for item in data.get("open_orders", [])),
        executions=tuple(_execution_from_dict(item) for item in data.get("executions", [])),
        warnings=tuple(str(warning) for warning in data.get("warnings", [])),
        as_of=as_of,
    )


def _holding_to_dict(holding: Holding, snapshot: PortfolioSnapshot | None = None) -> dict[str, Any]:
    total_value = _net_liquidation(snapshot) if snapshot is not None else None
    allocation = None
    if total_value is not None and total_value != 0:
        allocation = holding.market_value / total_value
    return {
        "symbol": holding.symbol,
        "quantity": _decimal_to_str(holding.quantity),
        "market_value": _decimal_to_str(holding.market_value),
        "currency": holding.currency,
        "market_price": _optional_decimal_to_str(holding.market_price),
        "average_cost": _optional_decimal_to_str(holding.average_cost),
        "cost_basis": _optional_decimal_to_str(holding.cost_basis),
        "unrealized_pnl": _optional_decimal_to_str(holding.unrealized_pnl),
        "realized_pnl": _optional_decimal_to_str(holding.realized_pnl),
        "gain_loss_pct": _optional_decimal_to_str(holding.gain_loss_pct),
        "allocation_pct": _optional_decimal_to_str(allocation),
        "company_name": holding.company_name,
        "sector": holding.sector,
        "con_id": holding.con_id,
        "sec_type": holding.sec_type,
        "exchange": holding.exchange,
    }


def _holding_from_dict(data: Mapping[str, Any]) -> Holding:
    return Holding(
        symbol=str(data["symbol"]),
        quantity=_decimal(data["quantity"]),
        market_value=_decimal(data["market_value"]),
        currency=str(data.get("currency") or "USD"),
        market_price=_optional_decimal(data.get("market_price")),
        average_cost=_optional_decimal(data.get("average_cost")),
        unrealized_pnl=_optional_decimal(data.get("unrealized_pnl")),
        realized_pnl=_optional_decimal(data.get("realized_pnl")),
        company_name=data.get("company_name"),
        sector=data.get("sector"),
        con_id=data.get("con_id"),
        sec_type=data.get("sec_type"),
        exchange=data.get("exchange"),
    )


def _cash_to_dict(balance: CashBalance) -> dict[str, Any]:
    return {"currency": balance.currency, "amount": _decimal_to_str(balance.amount), "kind": balance.kind}


def _cash_from_dict(data: Mapping[str, Any]) -> CashBalance:
    return CashBalance(currency=str(data["currency"]), amount=_decimal(data["amount"]), kind=str(data.get("kind") or "AvailableFunds"))


def _open_order_to_dict(order: OpenOrder) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "symbol": order.symbol,
        "action": order.action,
        "quantity": _decimal_to_str(order.quantity),
        "order_type": order.order_type,
        "status": order.status,
        "time_in_force": order.time_in_force,
        "limit_price": _optional_decimal_to_str(order.limit_price),
        "stop_price": _optional_decimal_to_str(order.stop_price),
    }


def _open_order_from_dict(data: Mapping[str, Any]) -> OpenOrder:
    return OpenOrder(
        order_id=int(data["order_id"]),
        symbol=str(data["symbol"]),
        action=str(data["action"]),
        quantity=_decimal(data["quantity"]),
        order_type=str(data["order_type"]),
        status=data.get("status"),
        time_in_force=data.get("time_in_force"),
        limit_price=_optional_decimal(data.get("limit_price")),
        stop_price=_optional_decimal(data.get("stop_price")),
    )


def _execution_to_dict(execution: Execution) -> dict[str, Any]:
    return {
        "execution_id": execution.execution_id,
        "symbol": execution.symbol,
        "side": execution.side,
        "shares": _decimal_to_str(execution.shares),
        "price": _decimal_to_str(execution.price),
        "time": execution.time,
        "account_id": execution.account_id,
    }


def _execution_from_dict(data: Mapping[str, Any]) -> Execution:
    return Execution(
        execution_id=str(data["execution_id"]),
        symbol=str(data["symbol"]),
        side=str(data["side"]),
        shares=_decimal(data["shares"]),
        price=_decimal(data["price"]),
        time=data.get("time"),
        account_id=data.get("account_id"),
    )


def _net_liquidation(snapshot: PortfolioSnapshot | None) -> Decimal | None:
    if snapshot is None:
        return None
    for key, value in snapshot.account_values.items():
        if "NetLiquidation" in key:
            try:
                return _decimal(value)
            except Exception:
                return None
    return None


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return _decimal(value)


def _decimal_to_str(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _optional_decimal_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return _decimal_to_str(value)
