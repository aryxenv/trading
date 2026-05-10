"""Portfolio context models for IBKR-backed analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal, Mapping


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: Decimal
    market_value: Decimal
    currency: str = "USD"
    average_cost: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    company_name: str | None = None
    sector: str | None = None

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
class PortfolioSnapshot:
    account_id: str | None
    holdings: tuple[Holding, ...] = ()
    cash: tuple[CashBalance, ...] = ()
    account_values: Mapping[str, str] = field(default_factory=dict)
    as_of: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def holding_for(self, target: str) -> Holding | None:
        for holding in self.holdings:
            if holding.matches(target):
                return holding
        return None

    def available_cash(self, currency: str = "USD") -> Decimal:
        target_currency = currency.strip().upper()
        balances = (
            balance.amount
            for balance in self.cash
            if balance.currency == target_currency
            and balance.kind in {"AvailableFunds", "TotalCashValue", "CashBalance"}
        )
        return sum(balances, Decimal("0"))

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
