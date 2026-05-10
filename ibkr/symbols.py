"""Ticker/company symbol resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
US_EXCHANGES = {"NYQ", "NMS", "NGM", "NCM", "ASE", "PCX", "BTS", "PNK", "OQB", "OQX"}


@dataclass(frozen=True)
class SymbolResolution:
    query: str
    resolved_symbol: str
    resolved_name: str | None
    exchange: str | None
    exchange_display: str | None
    quote_type: str | None
    confidence: str
    candidates: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...] = ()
    source: str = "yahoo_finance_search"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "ibkr.symbol_resolution.v1",
            "query": self.query,
            "resolved_symbol": self.resolved_symbol,
            "resolved_name": self.resolved_name,
            "exchange": self.exchange,
            "exchange_display": self.exchange_display,
            "quote_type": self.quote_type,
            "confidence": self.confidence,
            "source": self.source,
            "candidates": list(self.candidates),
            "warnings": list(self.warnings),
        }


def fetch_yahoo_search(
    query: str,
    *,
    quotes_count: int = 8,
    country: str = "United States",
    timeout: float = 10.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("Symbol resolution query is required.")

    params = urlencode({"q": query.strip(), "quotes_count": quotes_count, "country": country})
    request = Request(
        f"{YAHOO_SEARCH_URL}?{params}",
        headers={"User-Agent": user_agent, "Accept": "application/json"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def resolve_from_yahoo_response(query: str, data: dict[str, Any]) -> SymbolResolution:
    quotes = data.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        raise ValueError(f"No Yahoo Finance symbol candidates found for {query!r}.")

    ranked = sorted(
        (_candidate(quote, query) for quote in quotes if isinstance(quote, dict)),
        key=lambda candidate: candidate["_rank"],
        reverse=True,
    )
    if not ranked:
        raise ValueError(f"No usable Yahoo Finance symbol candidates found for {query!r}.")

    best = ranked[0]
    warnings: list[str] = []
    if len(ranked) > 1 and ranked[1]["_rank"] >= best["_rank"] - 250:
        warnings.append("Symbol resolution is close; review candidates before trading.")
    if best.get("quote_type") != "EQUITY":
        warnings.append("Top candidate is not an equity.")
    if best.get("exchange") not in US_EXCHANGES:
        warnings.append("Top candidate is not on a preferred US exchange.")

    confidence = _confidence(best, ranked)
    clean_candidates = tuple(_strip_internal(candidate) for candidate in ranked[:8])
    return SymbolResolution(
        query=query.strip(),
        resolved_symbol=str(best["symbol"]),
        resolved_name=best.get("name"),
        exchange=best.get("exchange"),
        exchange_display=best.get("exchange_display"),
        quote_type=best.get("quote_type"),
        confidence=confidence,
        candidates=clean_candidates,
        warnings=tuple(warnings),
    )


def resolve_symbol(query: str, **kwargs: Any) -> SymbolResolution:
    return resolve_from_yahoo_response(query, fetch_yahoo_search(query, **kwargs))


def _candidate(quote: dict[str, Any], query: str) -> dict[str, Any]:
    symbol = str(quote.get("symbol") or "").strip().upper()
    name = str(quote.get("longname") or quote.get("shortname") or "").strip()
    exchange = quote.get("exchange")
    quote_type = quote.get("quoteType")
    yahoo_score = float(quote.get("score") or 0)

    rank = yahoo_score
    normalized_query = _normalize(query)
    normalized_symbol = _normalize(symbol)
    normalized_name = _normalize(name)

    if quote_type == "EQUITY":
        rank += 5_000
    if exchange in US_EXCHANGES:
        rank += 2_500
    if normalized_query == normalized_symbol:
        rank += 25_000
    if normalized_query and normalized_query in normalized_name:
        rank += 10_000
    if symbol and "." not in symbol:
        rank += 1_000

    return {
        "_rank": rank,
        "symbol": symbol,
        "name": name or None,
        "exchange": exchange,
        "exchange_display": quote.get("exchDisp"),
        "quote_type": quote_type,
        "yahoo_score": yahoo_score,
    }


def _confidence(best: dict[str, Any], ranked: list[dict[str, Any]]) -> str:
    if best.get("quote_type") != "EQUITY":
        return "low"
    if best.get("exchange") in US_EXCHANGES and (len(ranked) == 1 or best["_rank"] - ranked[1]["_rank"] > 1_000):
        return "high"
    return "medium"


def _strip_internal(candidate: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in candidate.items() if not key.startswith("_")}


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())
