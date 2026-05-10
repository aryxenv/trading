"""Live IBKR client scaffolding with confirmation-gated order submission."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from threading import Event, Lock, Thread
from time import monotonic

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.execution import ExecutionFilter
from ibapi.order import Order
from ibapi.order_state import OrderState
from ibapi.wrapper import EWrapper

from .config import IBKRConfig
from .news import (
    NewsHeadline,
    NewsProvider,
    NewsSnapshot,
    historical_headline,
    parse_provider_codes,
    realtime_headline,
    sort_headlines,
)
from .orders import ConfirmedOrderIntent, build_ibapi_order
from .portfolio import CashBalance, Execution, Holding, OpenOrder, PortfolioSnapshot


class IBKRClientError(RuntimeError):
    """Raised when the live IBKR API cannot provide required data."""


NEWS_ABORT_ERROR_CODES = {200, 321, 354, 366, 10090, 10168}


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
        self.request_errors: dict[int, list[str]] = {}
        self._lock = Lock()
        self.news_providers_done = Event()
        self.news_providers: list[NewsProvider] = []
        self.contract_details_events: dict[int, Event] = {}
        self.contract_details: dict[int, list[object]] = {}
        self.news_headline_event = Event()
        self.historical_news_events: dict[int, Event] = {}
        self.news_headlines: list[NewsHeadline] = []
        self._news_keys: set[tuple[str, str, str]] = set()

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

    def newsProviders(self, newsProviders: list) -> None:
        with self._lock:
            self.news_providers = [
                NewsProvider(code=str(getattr(provider, "code", "")), name=str(getattr(provider, "name", "")))
                for provider in newsProviders
                if str(getattr(provider, "code", "")).strip()
            ]
        self.news_providers_done.set()

    def contractDetails(self, reqId: int, contractDetails) -> None:
        with self._lock:
            self.contract_details.setdefault(reqId, []).append(contractDetails)

    def contractDetailsEnd(self, reqId: int) -> None:
        event = self.contract_details_events.get(reqId)
        if event is not None:
            event.set()

    def tickNews(self, tickerId: int, timeStamp: int, providerCode: str, articleId: str, headline: str, extraData: str) -> None:
        self._append_news_headline(
            realtime_headline(
                provider_code=providerCode,
                article_id=articleId,
                headline=headline,
                timestamp=timeStamp,
                extra_data=extraData,
            )
        )

    def historicalNews(self, requestId: int, time: str, providerCode: str, articleId: str, headline: str) -> None:
        self._append_news_headline(
            historical_headline(provider_code=providerCode, article_id=articleId, headline=headline, time=time)
        )

    def historicalNewsEnd(self, requestId: int, hasMore: bool) -> None:
        event = self.historical_news_events.get(requestId)
        if event is not None:
            event.set()

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:
        message = f"{reqId}:{errorCode}:{errorString}"
        if advancedOrderRejectJson:
            message = f"{message}:{advancedOrderRejectJson}"
        self.errors.append(message)
        if reqId >= 0:
            self.request_errors.setdefault(reqId, []).append(message)
            contract_event = self.contract_details_events.get(reqId)
            if contract_event is not None:
                contract_event.set()
            historical_event = self.historical_news_events.get(reqId)
            if historical_event is not None:
                historical_event.set()
            self.news_headline_event.set()

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

    def reset_news_data(self) -> None:
        self.news_providers_done.clear()
        self.news_headline_event.clear()
        with self._lock:
            self.news_providers.clear()
            self.contract_details.clear()
            self.contract_details_events.clear()
            self.historical_news_events.clear()
            self.news_headlines.clear()
            self._news_keys.clear()
        self.request_errors.clear()

    def _append_news_headline(self, headline: NewsHeadline) -> None:
        with self._lock:
            if headline.dedupe_key in self._news_keys:
                return
            self._news_keys.add(headline.dedupe_key)
            self.news_headlines.append(headline)
        self.news_headline_event.set()


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

    def load_news_snapshot(
        self,
        target: str,
        providers: str | tuple[str, ...] | list[str] | None = None,
        *,
        realtime_seconds: float = 30.0,
        max_headlines: int = 25,
        historical_limit: int = 10,
        exchange: str = "SMART",
        currency: str = "USD",
    ) -> NewsSnapshot:
        if not target.strip():
            raise ValueError("News target ticker is required.")
        if realtime_seconds < 0:
            raise ValueError("realtime_seconds must be non-negative.")
        if max_headlines < 0:
            raise ValueError("max_headlines must be non-negative.")
        if historical_limit < 0:
            raise ValueError("historical_limit must be non-negative.")

        self.connect()
        app = self._require_app()
        app.reset_news_data()
        warnings: list[str] = []

        subscribed_providers = self._load_news_providers(app, warnings)
        selected_providers = _select_news_providers(subscribed_providers, parse_provider_codes(providers), warnings)
        if not selected_providers:
            warnings.append("No subscribed IBKR API news providers available; use web news only.")
            return NewsSnapshot(target=target.strip().upper(), providers=(), headlines=(), warnings=tuple(warnings))

        contract = self._resolve_stock_contract(app, target, exchange, currency)
        provider_codes = tuple(provider.code for provider in selected_providers)

        if historical_limit:
            self._request_historical_news(app, contract.conId, provider_codes, historical_limit, warnings)
        if realtime_seconds and max_headlines:
            self._request_realtime_news(app, contract, provider_codes, realtime_seconds, max_headlines, warnings)

        with app._lock:
            headlines = sort_headlines(tuple(app.news_headlines))[:max_headlines]

        warnings.extend(_request_warnings(app))
        return NewsSnapshot(
            target=target.strip().upper(),
            con_id=contract.conId or None,
            contract_symbol=contract.symbol or target.strip().upper(),
            providers=selected_providers,
            headlines=headlines,
            warnings=tuple(dict.fromkeys(warnings)),
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

    def _load_news_providers(self, app: _LiveIBKRApp, warnings: list[str]) -> tuple[NewsProvider, ...]:
        app.reqNewsProviders()
        if not app.news_providers_done.wait(min(self.config.timeout_seconds, 10)):
            warnings.append("Timed out waiting for IBKR API news providers.")
            return ()
        with app._lock:
            return tuple(app.news_providers)

    def _resolve_stock_contract(self, app: _LiveIBKRApp, target: str, exchange: str, currency: str) -> Contract:
        req_id = 9101
        event = Event()
        app.contract_details_events[req_id] = event
        app.reqContractDetails(req_id, stock_contract(target, exchange, currency))
        if not event.wait(min(self.config.timeout_seconds, 15)):
            raise IBKRClientError(f"Timed out resolving IBKR contract for {target.strip().upper()}.")
        errors = app.request_errors.get(req_id, [])
        if errors:
            raise IBKRClientError(f"IBKR contract resolution failed for {target.strip().upper()}: {'; '.join(errors)}")
        with app._lock:
            details = tuple(app.contract_details.get(req_id, ()))
        if not details:
            raise IBKRClientError(f"No IBKR contract details found for {target.strip().upper()}.")
        contract = details[0].contract
        if not contract.conId:
            raise IBKRClientError(f"IBKR contract for {target.strip().upper()} did not include conId.")
        return contract

    def _request_historical_news(
        self,
        app: _LiveIBKRApp,
        con_id: int,
        provider_codes: tuple[str, ...],
        limit: int,
        warnings: list[str],
    ) -> None:
        req_id = 9201
        event = Event()
        app.historical_news_events[req_id] = event
        app.reqHistoricalNews(req_id, con_id, "+".join(provider_codes), "", "", limit, [])
        if not event.wait(min(self.config.timeout_seconds, 15)):
            app.cancelHistoricalData(req_id)
            warnings.append("Timed out waiting for IBKR historical news.")

    def _request_realtime_news(
        self,
        app: _LiveIBKRApp,
        contract: Contract,
        provider_codes: tuple[str, ...],
        seconds: float,
        max_headlines: int,
        warnings: list[str],
    ) -> None:
        req_id = 9202
        generic_ticks = f"mdoff,292:{'+'.join(provider_codes)}"
        app.reqMktData(req_id, contract, generic_ticks, False, False, [])
        deadline = monotonic() + seconds
        try:
            while monotonic() < deadline:
                with app._lock:
                    if len(app.news_headlines) >= max_headlines:
                        break
                if _has_abort_error(app, req_id):
                    warnings.append("IBKR realtime news request stopped after API error.")
                    break
                remaining = max(0.0, deadline - monotonic())
                if remaining == 0:
                    break
                app.news_headline_event.wait(min(remaining, 1.0))
                app.news_headline_event.clear()
        finally:
            app.cancelMktData(req_id)


def stock_contract(symbol: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
    if not symbol.strip():
        raise ValueError("Stock symbol is required.")
    contract = Contract()
    contract.symbol = symbol.strip().upper()
    contract.secType = "STK"
    contract.exchange = exchange
    contract.currency = currency
    return contract


def _select_news_providers(
    subscribed: tuple[NewsProvider, ...],
    requested_codes: tuple[str, ...],
    warnings: list[str],
) -> tuple[NewsProvider, ...]:
    if not requested_codes:
        return subscribed

    subscribed_by_code = {provider.code: provider for provider in subscribed}
    missing = tuple(code for code in requested_codes if code not in subscribed_by_code)
    if missing:
        warnings.append(f"IBKR API news providers not subscribed or unavailable: {', '.join(missing)}.")
    return tuple(subscribed_by_code[code] for code in requested_codes if code in subscribed_by_code)


def _request_warnings(app: _LiveIBKRApp) -> list[str]:
    warnings: list[str] = []
    for errors in app.request_errors.values():
        warnings.extend(errors)
    return warnings


def _has_abort_error(app: _LiveIBKRApp, req_id: int) -> bool:
    return any(_error_code(error) in NEWS_ABORT_ERROR_CODES for error in app.request_errors.get(req_id, ()))


def _error_code(message: str) -> int | None:
    parts = message.split(":", 2)
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _optional_decimal_from_float(value: float | int | None) -> Decimal | None:
    if value is None:
        return None
    if float(value) in {0.0, 1.7976931348623157e308}:
        return None
    return Decimal(str(value))
