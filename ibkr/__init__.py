"""Safe IBKR trading research scaffolding."""

from .audit import ExecutiveDecisionRecord, report_path, write_executive_report
from .client import IBKRClientError, LiveIBKRClient, stock_contract
from .config import IBKRConfig, IBKRConfigError
from .orders import (
    ConfirmedOrderIntent,
    OrderIntent,
    OrderIntentError,
    build_ibapi_order,
    confirm_live_order,
    required_confirmation,
)
from .portfolio import (
    CashBalance,
    Holding,
    PortfolioSnapshot,
    TargetContext,
    context_for_target,
    require_full_portfolio,
)

__all__ = [
    "CashBalance",
    "ConfirmedOrderIntent",
    "ExecutiveDecisionRecord",
    "Holding",
    "IBKRClientError",
    "IBKRConfig",
    "IBKRConfigError",
    "LiveIBKRClient",
    "OrderIntent",
    "OrderIntentError",
    "PortfolioSnapshot",
    "TargetContext",
    "build_ibapi_order",
    "confirm_live_order",
    "context_for_target",
    "report_path",
    "required_confirmation",
    "require_full_portfolio",
    "stock_contract",
    "write_executive_report",
]
