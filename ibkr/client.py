"""Live IBKR client scaffolding with confirmation-gated order submission."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from threading import Event, Thread

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper

from .config import IBKRConfig
from .orders import ConfirmedOrderIntent, build_ibapi_order
from .portfolio import CashBalance, Holding, PortfolioSnapshot


class IBKRClientError(RuntimeError):
    """Raised when the live IBKR API cannot provide required data."""


class _LiveIBKRApp(EWrapper, EClient):
    def __init__(self) -> None:
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)
        self.ready = Event()
        self.account_download_done = Event()
        self.summary_done = Event()
        self.next_order_id: int | None = None
        self.holdings: dict[str, Holding] = {}
        self.cash: list[CashBalance] = []
        self.account_values: dict[str, str] = {}
        self.errors: list[str] = []

    def nextValidId(self, orderId: int) -> None:
        self.next_order_id = orderId
        self.ready.set()

    def updatePortfolio(
        self,
        contract: Contract,
        position: float,
        marketPrice: float,
        marketValue: float,
        averageCost: float,
        unrealizedPNL: float,
        realizedPNL: float,
        accountName: str,
    ) -> None:
        symbol = contract.symbol.strip().upper()
        if not symbol:
            return
        self.holdings[symbol] = Holding(
            symbol=symbol,
            quantity=Decimal(str(position)),
            market_value=Decimal(str(marketValue)),
            average_cost=Decimal(str(averageCost)),
            unrealized_pnl=Decimal(str(unrealizedPNL)),
            currency=contract.currency or "USD",
        )

    def accountDownloadEnd(self, accountName: str) -> None:
        self.account_download_done.set()

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str) -> None:
        key = f"{account}:{tag}:{currency or 'BASE'}"
        self.account_values[key] = value
        if tag in {"AvailableFunds", "TotalCashValue", "CashBalance"}:
            try:
                amount = Decimal(value)
            except InvalidOperation:
                return
            self.cash.append(CashBalance(currency=currency or "BASE", amount=amount, kind=tag))

    def accountSummaryEnd(self, reqId: int) -> None:
        self.summary_done.set()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:
        message = f"{reqId}:{errorCode}:{errorString}"
        if advancedOrderRejectJson:
            message = f"{message}:{advancedOrderRejectJson}"
        self.errors.append(message)

    def reset_account_data(self) -> None:
        self.account_download_done.clear()
        self.summary_done.clear()
        self.holdings.clear()
        self.cash.clear()
        self.account_values.clear()


class LiveIBKRClient:
    def __init__(self, config: IBKRConfig) -> None:
        self.config = config
        self._app: _LiveIBKRApp | None = None
        self._thread: Thread | None = None

    def connect(self) -> None:
        if self._app is not None and self._app.isConnected():
            return
        app = _LiveIBKRApp()
        app.connect(self.config.host, self.config.port, self.config.client_id)
        thread = Thread(target=app.run, name="ibkr-api-client", daemon=True)
        thread.start()
        if not app.ready.wait(self.config.timeout_seconds):
            app.disconnect()
            raise IBKRClientError("Timed out waiting for IBKR live API readiness.")
        self._app = app
        self._thread = thread

    def close(self) -> None:
        if self._app is not None:
            self._app.disconnect()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._app = None
        self._thread = None

    def load_portfolio_snapshot(self) -> PortfolioSnapshot:
        self.connect()
        app = self._require_app()
        app.reset_account_data()

        account = self.config.account_id or ""
        app.reqAccountUpdates(True, account)
        if not app.account_download_done.wait(self.config.timeout_seconds):
            app.reqAccountUpdates(False, account)
            raise IBKRClientError("Timed out waiting for IBKR portfolio data.")
        app.reqAccountUpdates(False, account)

        req_id = 9001
        tags = "NetLiquidation,TotalCashValue,AvailableFunds,BuyingPower"
        app.reqAccountSummary(req_id, "All", tags)
        if not app.summary_done.wait(self.config.timeout_seconds):
            app.cancelAccountSummary(req_id)
            raise IBKRClientError("Timed out waiting for IBKR account summary.")
        app.cancelAccountSummary(req_id)

        return PortfolioSnapshot(
            account_id=self.config.account_id,
            holdings=tuple(app.holdings.values()),
            cash=tuple(app.cash),
            account_values=dict(app.account_values),
        )

    def submit_confirmed_stock_order(
        self,
        confirmed: ConfirmedOrderIntent,
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> int:
        self.connect()
        app = self._require_app()
        if app.next_order_id is None:
            raise IBKRClientError("IBKR did not provide a live order id.")

        order_id = app.next_order_id
        app.next_order_id += 1
        app.placeOrder(order_id, stock_contract(confirmed.intent.symbol, exchange, currency), build_ibapi_order(confirmed))
        return order_id

    def _require_app(self) -> _LiveIBKRApp:
        if self._app is None or not self._app.isConnected():
            raise IBKRClientError("IBKR client is not connected.")
        return self._app


def stock_contract(symbol: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
    if not symbol.strip():
        raise ValueError("Stock symbol is required.")
    contract = Contract()
    contract.symbol = symbol.strip().upper()
    contract.secType = "STK"
    contract.exchange = exchange
    contract.currency = currency
    return contract
