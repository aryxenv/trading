"""Live IBKR client scaffolding with confirmation-gated order submission."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from threading import Event, Thread

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.execution import ExecutionFilter
from ibapi.order import Order
from ibapi.order_state import OrderState
from ibapi.wrapper import EWrapper

from .config import IBKRConfig
from .orders import ConfirmedOrderIntent, build_ibapi_order
from .portfolio import CashBalance, Execution, Holding, OpenOrder, PortfolioSnapshot


class IBKRClientError(RuntimeError):
    """Raised when the live IBKR API cannot provide required data."""


class _LiveIBKRApp(EWrapper, EClient):
    def __init__(self) -> None:
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)
        self.ready = Event()
        self.account_download_done = Event()
        self.summary_done = Event()
        self.open_orders_done = Event()
        self.executions_done = Event()
        self.next_order_id: int | None = None
        self.holdings: dict[str, Holding] = {}
        self.cash: list[CashBalance] = []
        self.account_values: dict[str, str] = {}
        self.open_orders: dict[int, OpenOrder] = {}
        self.executions: list[Execution] = []
        self.order_statuses: dict[int, dict[str, str]] = {}
        self.order_status_events: dict[int, Event] = {}
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
            market_price=Decimal(str(marketPrice)),
            average_cost=Decimal(str(averageCost)),
            unrealized_pnl=Decimal(str(unrealizedPNL)),
            realized_pnl=Decimal(str(realizedPNL)),
            currency=contract.currency or "USD",
            con_id=contract.conId or None,
            sec_type=contract.secType or None,
            exchange=contract.exchange or None,
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

    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState: OrderState) -> None:
        self.open_orders[orderId] = OpenOrder(
            order_id=orderId,
            symbol=contract.symbol or "",
            action=order.action or "",
            quantity=Decimal(str(order.totalQuantity)),
            order_type=order.orderType or "",
            status=orderState.status or None,
            time_in_force=order.tif or None,
            limit_price=_optional_decimal_from_float(order.lmtPrice),
            stop_price=_optional_decimal_from_float(order.auxPrice),
        )

    def openOrderEnd(self) -> None:
        self.open_orders_done.set()

    def orderStatus(
        self,
        orderId: int,
        status: str,
        filled: float,
        remaining: float,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float,
    ) -> None:
        self.order_statuses[orderId] = {
            "status": status,
            "filled": str(filled),
            "remaining": str(remaining),
            "avg_fill_price": str(avgFillPrice),
            "last_fill_price": str(lastFillPrice),
        }
        event = self.order_status_events.get(orderId)
        if event is not None:
            event.set()

    def execDetails(self, reqId: int, contract: Contract, execution) -> None:
        self.executions.append(
            Execution(
                execution_id=execution.execId,
                symbol=contract.symbol or "",
                side=execution.side or "",
                shares=Decimal(str(execution.shares)),
                price=Decimal(str(execution.price)),
                time=execution.time or None,
                account_id=execution.acctNumber or None,
            )
        )

    def execDetailsEnd(self, reqId: int) -> None:
        self.executions_done.set()

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
        self.open_orders_done.clear()
        self.executions_done.clear()
        self.open_orders.clear()
        self.executions.clear()


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

        if self.config.account_id is None:
            raise IBKRClientError("IBKR_ACCOUNT_ID is required to load a deterministic portfolio snapshot.")

        account = self.config.account_id
        app.reqAccountUpdates(True, account)
        if not app.account_download_done.wait(self.config.timeout_seconds):
            app.reqAccountUpdates(False, account)
            raise IBKRClientError("Timed out waiting for IBKR portfolio data.")
        app.reqAccountUpdates(False, account)

        req_id = 9001
        tags = ",".join(
            [
                "NetLiquidation",
                "TotalCashValue",
                "CashBalance",
                "AvailableFunds",
                "BuyingPower",
                "GrossPositionValue",
                "ExcessLiquidity",
                "InitMarginReq",
                "MaintMarginReq",
                "UnrealizedPnL",
                "RealizedPnL",
            ]
        )
        app.reqAccountSummary(req_id, "All", tags)
        if not app.summary_done.wait(self.config.timeout_seconds):
            app.cancelAccountSummary(req_id)
            raise IBKRClientError("Timed out waiting for IBKR account summary.")
        app.cancelAccountSummary(req_id)

        app.reqOpenOrders()
        if not app.open_orders_done.wait(min(self.config.timeout_seconds, 10)):
            app.errors.append("Timed out waiting for IBKR open orders.")

        exec_req_id = 9002
        app.reqExecutions(exec_req_id, ExecutionFilter())
        if not app.executions_done.wait(min(self.config.timeout_seconds, 10)):
            app.errors.append("Timed out waiting for IBKR executions.")

        return PortfolioSnapshot(
            account_id=self.config.account_id,
            holdings=tuple(app.holdings.values()),
            cash=tuple(app.cash),
            account_values=dict(app.account_values),
            open_orders=tuple(app.open_orders.values()),
            executions=tuple(app.executions),
            warnings=tuple(app.errors),
        )

    def submit_confirmed_stock_order(
        self,
        confirmed: ConfirmedOrderIntent,
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> dict[str, object]:
        self.connect()
        app = self._require_app()
        if app.next_order_id is None:
            raise IBKRClientError("IBKR did not provide a live order id.")

        order_id = app.next_order_id
        app.next_order_id += 1
        status_event = Event()
        app.order_status_events[order_id] = status_event
        app.placeOrder(order_id, stock_contract(confirmed.intent.symbol, exchange, currency), build_ibapi_order(confirmed))
        acknowledged = status_event.wait(min(self.config.timeout_seconds, 30))
        status = app.order_statuses.get(order_id, {})
        return {
            "order_id": order_id,
            "acknowledged": acknowledged,
            "status": status.get("status"),
            "filled": status.get("filled"),
            "remaining": status.get("remaining"),
            "avg_fill_price": status.get("avg_fill_price"),
            "warning": None if acknowledged else "Timed out waiting for IBKR order status acknowledgement.",
        }

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


def _optional_decimal_from_float(value: float | int | None) -> Decimal | None:
    if value is None:
        return None
    if float(value) in {0.0, 1.7976931348623157e308}:
        return None
    return Decimal(str(value))
