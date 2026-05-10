"""Safe IBKR trading research scaffolding."""

from .audit import ExecutiveDecisionRecord, report_path, write_executive_report
from .client import IBKRClientError, LiveIBKRClient, stock_contract
from .config import IBKRConfig, IBKRConfigError, load_env_file
from .news import NewsHeadline, NewsProvider, NewsSnapshot, news_snapshot_to_dict
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
    Execution,
    Holding,
    OpenOrder,
    PortfolioSnapshot,
    TargetContext,
    context_for_target,
    require_full_portfolio,
    snapshot_from_dict,
    snapshot_to_dict,
)

__all__ = [
    "CashBalance",
    "ConfirmedOrderIntent",
    "ExecutiveDecisionRecord",
    "Execution",
    "Holding",
    "IBKRClientError",
    "IBKRConfig",
    "IBKRConfigError",
    "LiveIBKRClient",
    "NewsHeadline",
    "NewsProvider",
    "NewsSnapshot",
    "OpenOrder",
    "OrderIntent",
    "OrderIntentError",
    "PortfolioSnapshot",
    "TargetContext",
    "build_ibapi_order",
    "confirm_live_order",
    "context_for_target",
    "load_env_file",
    "news_snapshot_to_dict",
    "report_path",
    "required_confirmation",
    "require_full_portfolio",
    "stock_contract",
    "snapshot_from_dict",
    "snapshot_to_dict",
    "write_executive_report",
]
