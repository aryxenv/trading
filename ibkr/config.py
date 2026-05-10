"""IBKR live connection configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


class IBKRConfigError(ValueError):
    """Raised when IBKR configuration is unsafe or invalid."""


PAPER_PORTS = {4002, 7497}
DEFAULT_LIVE_PORT = 7496


@dataclass(frozen=True)
class IBKRConfig:
    host: str = "127.0.0.1"
    port: int = DEFAULT_LIVE_PORT
    client_id: int = 7
    account_id: str | None = None
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise IBKRConfigError("IBKR host is required.")
        if self.port in PAPER_PORTS:
            raise IBKRConfigError("Paper trading ports are not allowed; configure a live IBKR port.")
        if self.port <= 0:
            raise IBKRConfigError("IBKR port must be positive.")
        if self.client_id < 0:
            raise IBKRConfigError("IBKR client_id must be non-negative.")
        if self.timeout_seconds <= 0:
            raise IBKRConfigError("IBKR timeout_seconds must be positive.")
        if self.account_id is not None and not self.account_id.strip():
            raise IBKRConfigError("IBKR account_id cannot be blank.")

    @classmethod
    def from_env(cls, prefix: str = "IBKR_") -> "IBKRConfig":
        load_env_file()
        return cls(
            host=os.getenv(f"{prefix}HOST", "127.0.0.1"),
            port=_int_env(f"{prefix}PORT", DEFAULT_LIVE_PORT),
            client_id=_int_env(f"{prefix}CLIENT_ID", 7),
            account_id=os.getenv(f"{prefix}ACCOUNT_ID") or None,
            timeout_seconds=_float_env(f"{prefix}TIMEOUT_SECONDS", 30.0),
        )


def load_env_file(path: Path | str | None = None, *, override: bool = False) -> Path | None:
    env_path = Path(path) if path is not None else _find_env_file()
    if env_path is None or not env_path.exists():
        return None

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key or (key in os.environ and not override):
            continue
        os.environ[key] = _clean_env_value(raw_value)
    return env_path


def _find_env_file() -> Path | None:
    for directory in (Path.cwd(), *Path.cwd().parents):
        candidate = directory / ".env"
        if candidate.exists():
            return candidate
    return None


def _clean_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise IBKRConfigError(f"{name} must be an integer.") from exc


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise IBKRConfigError(f"{name} must be a number.") from exc
