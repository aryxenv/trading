"""IBKR API news models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any


@dataclass(frozen=True)
class NewsProvider:
    code: str
    name: str

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("News provider code is required.")
        object.__setattr__(self, "code", self.code.strip().upper())
        object.__setattr__(self, "name", self.name.strip())


@dataclass(frozen=True)
class NewsHeadline:
    provider_code: str
    article_id: str
    headline: str
    source: str
    time: str | None = None
    timestamp: int | None = None
    extra_data: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_code.strip():
            raise ValueError("News provider code is required.")
        if not self.headline.strip():
            raise ValueError("News headline is required.")
        object.__setattr__(self, "provider_code", self.provider_code.strip().upper())
        object.__setattr__(self, "article_id", self.article_id.strip())
        object.__setattr__(self, "headline", _clean_headline(self.headline))

    @property
    def dedupe_key(self) -> tuple[str, str, str]:
        return (self.provider_code, self.article_id, self.headline)


@dataclass(frozen=True)
class NewsSnapshot:
    target: str
    providers: tuple[NewsProvider, ...]
    headlines: tuple[NewsHeadline, ...]
    con_id: int | None = None
    contract_symbol: str | None = None
    warnings: tuple[str, ...] = ()


def news_snapshot_to_dict(snapshot: NewsSnapshot) -> dict[str, Any]:
    return {
        "schema_version": "ibkr.news_snapshot.v1",
        "target": snapshot.target,
        "con_id": snapshot.con_id,
        "contract_symbol": snapshot.contract_symbol,
        "providers": [_provider_to_dict(provider) for provider in snapshot.providers],
        "headlines": [_headline_to_dict(headline) for headline in snapshot.headlines],
        "warnings": list(snapshot.warnings),
    }


def parse_provider_codes(value: str | tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    raw = "+".join(value) if isinstance(value, tuple | list) else value
    codes = []
    for part in raw.replace(",", "+").split("+"):
        code = part.strip().upper()
        if code and code not in codes:
            codes.append(code)
    return tuple(codes)


def realtime_headline(
    *,
    provider_code: str,
    article_id: str,
    headline: str,
    timestamp: int,
    extra_data: str,
) -> NewsHeadline:
    return NewsHeadline(
        provider_code=provider_code,
        article_id=article_id,
        headline=headline,
        source="realtime",
        time=_timestamp_to_iso(timestamp),
        timestamp=timestamp,
        extra_data=extra_data or None,
    )


def historical_headline(*, provider_code: str, article_id: str, headline: str, time: str) -> NewsHeadline:
    return NewsHeadline(
        provider_code=provider_code,
        article_id=article_id,
        headline=headline,
        source="historical",
        time=time or None,
    )


def sort_headlines(headlines: tuple[NewsHeadline, ...]) -> tuple[NewsHeadline, ...]:
    return tuple(sorted(headlines, key=_headline_sort_key, reverse=True))


def _headline_sort_key(headline: NewsHeadline) -> tuple[int, str]:
    if headline.timestamp is not None:
        return (headline.timestamp, headline.headline)
    if headline.time:
        return (_best_effort_time_key(headline.time), headline.headline)
    return (0, headline.headline)


def _best_effort_time_key(value: str) -> int:
    digits = "".join(character for character in value if character.isdigit())
    return int(digits[:14] or 0)


def _timestamp_to_iso(timestamp: int) -> str:
    seconds = timestamp / 1000 if timestamp > 9_999_999_999 else timestamp
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def _provider_to_dict(provider: NewsProvider) -> dict[str, str]:
    return {"code": provider.code, "name": provider.name}


def _headline_to_dict(headline: NewsHeadline) -> dict[str, Any]:
    return {
        "provider_code": headline.provider_code,
        "article_id": headline.article_id,
        "headline": headline.headline,
        "source": headline.source,
        "time": headline.time,
        "timestamp": headline.timestamp,
        "extra_data": headline.extra_data,
    }


def _clean_headline(value: str) -> str:
    return re.sub(r"^(?:\{[^}]*\})+", "", value).strip()
