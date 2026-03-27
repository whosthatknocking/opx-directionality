from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import path depends on Python version
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None


DEFAULT_CONFIG_PATH = Path("~/.config/opx-directionality/config.toml").expanduser()


@dataclass(frozen=True)
class ScoringConfig:
    bullish_threshold: int = 3
    bearish_threshold: int = -3
    vwap_band_pct: float = 0.15
    strong_move_pct: float = 0.75
    relative_strength_pct: float = 0.30
    volume_multiple_threshold: float = 1.5


@dataclass(frozen=True)
class StorageConfig:
    kind: str = "file"
    target: str = "output/runs"


@dataclass(frozen=True)
class LoggingConfig:
    directory: str = "logs"
    aggregate_filename: str = "opx_runs.log"


@dataclass(frozen=True)
class ProviderConfig:
    name: str = "yfinance"


@dataclass(frozen=True)
class EngineConfig:
    tickers: list[str]
    benchmark_primary: str
    benchmark_secondary: str
    signal_time_et: str
    bar_interval: str
    lookback_days_intraday: int
    lookback_days_daily: int
    engine_version: str
    config_version: str
    provider: ProviderConfig
    storage: StorageConfig
    logging: LoggingConfig
    scoring: ScoringConfig


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> EngineConfig:
    config_path = Path(path).expanduser()
    raw = _load_toml(config_path)

    scoring = ScoringConfig(**_section(raw, "scoring"))
    provider = ProviderConfig(**_section(raw, "provider"))
    storage = StorageConfig(**_section(raw, "storage"))
    logging = LoggingConfig(**_section(raw, "logging"))

    tickers = raw.get("tickers", raw.get("watchlist", []))
    if not tickers:
        raise ValueError(f"config at {config_path} must define tickers")

    return EngineConfig(
        tickers=[str(ticker).upper() for ticker in tickers],
        benchmark_primary=str(raw.get("benchmark_primary", "QQQ")).upper(),
        benchmark_secondary=str(raw.get("benchmark_secondary", "SPY")).upper(),
        signal_time_et=str(raw.get("signal_time_et", "09:45")),
        bar_interval=str(raw.get("bar_interval", "5m")),
        lookback_days_intraday=int(raw.get("lookback_days_intraday", 20)),
        lookback_days_daily=int(raw.get("lookback_days_daily", 10)),
        engine_version=str(raw.get("engine_version", "0.1.0")),
        config_version=str(raw.get("config_version", "2")),
        provider=provider,
        storage=storage,
        logging=logging,
        scoring=scoring,
    )


def _load_toml(path: Path) -> dict[str, Any]:
    if tomllib is not None:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    return _load_simple_toml(path)


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    section = raw.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"config section [{name}] must be a table")
    return section


def _load_simple_toml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current = root
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            current = root.setdefault(name, {})
            continue
        if "=" not in line:
            raise ValueError(f"invalid config line: {raw_line}")
        key, value = [part.strip() for part in line.split("=", 1)]
        current[key] = _parse_scalar(value)
    return root


def _parse_scalar(value: str) -> Any:
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    stripped = value.strip().strip('"').strip("'")
    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in stripped:
            return float(stripped)
        return int(stripped)
    except ValueError:
        return stripped
