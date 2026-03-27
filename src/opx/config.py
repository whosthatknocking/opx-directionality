from __future__ import annotations
# pylint: disable=too-many-instance-attributes

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

try:  # pragma: no cover - import path depends on Python version
    import tomllib as TOML_LIB
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as TOML_LIB
    except ModuleNotFoundError:  # pragma: no cover
        TOML_LIB = None


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
    settings: dict[str, Any] | None = None

    def selected_settings(self) -> dict[str, Any]:
        return dict(self.settings or {})


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

    settings = _section(raw, "settings")
    scoring = ScoringConfig(
        bullish_threshold=int(settings.get("bullish_threshold", 3)),
        bearish_threshold=int(settings.get("bearish_threshold", -3)),
        vwap_band_pct=float(settings.get("vwap_band_pct", 0.15)),
        strong_move_pct=float(settings.get("strong_move_pct", 0.75)),
        relative_strength_pct=float(settings.get("relative_strength_pct", 0.30)),
        volume_multiple_threshold=float(settings.get("volume_multiple_threshold", 1.5)),
    )
    providers_section = _section(raw, "providers")
    provider_name = str(settings.get("data_provider", "yfinance"))
    provider = ProviderConfig(
        name=provider_name,
        settings=_provider_settings(providers_section, provider_name),
    )
    storage_sections = _section(raw, "storage")
    storage_kind = str(settings.get("storage_type", "file"))
    storage_settings = _named_settings(storage_sections, storage_kind)
    storage = StorageConfig(
        kind=storage_kind,
        target=str(storage_settings.get("target", _default_storage_target(storage_kind))),
    )
    logging = LoggingConfig(
        directory=str(settings.get("logging_dir", "logs")),
    )

    tickers = settings.get("tickers", settings.get("watchlist", []))
    if not tickers:
        raise ValueError(f"config at {config_path} must define tickers")

    return EngineConfig(
        tickers=[str(ticker).upper() for ticker in tickers],
        benchmark_primary=str(settings.get("benchmark_primary", "QQQ")).upper(),
        benchmark_secondary=str(settings.get("benchmark_secondary", "SPY")).upper(),
        signal_time_et=str(settings.get("signal_time_et", "09:45")),
        bar_interval=str(settings.get("bar_interval", "5m")),
        lookback_days_intraday=int(settings.get("lookback_days_intraday", 20)),
        lookback_days_daily=int(settings.get("lookback_days_daily", 10)),
        engine_version=str(settings.get("engine_version", "0.1.0")),
        config_version=str(settings.get("config_version", "2")),
        provider=provider,
        storage=storage,
        logging=logging,
        scoring=scoring,
    )


def _load_toml(path: Path) -> dict[str, Any]:
    if TOML_LIB is not None:
        with path.open("rb") as handle:
            return TOML_LIB.load(handle)
    return _load_simple_toml(path)


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    section = raw.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"config section [{name}] must be a table")
    return section


def config_fingerprint(config: EngineConfig) -> str:
    payload = {
        "tickers": config.tickers,
        "benchmark_primary": config.benchmark_primary,
        "benchmark_secondary": config.benchmark_secondary,
        "signal_time_et": config.signal_time_et,
        "bar_interval": config.bar_interval,
        "lookback_days_intraday": config.lookback_days_intraday,
        "lookback_days_daily": config.lookback_days_daily,
        "engine_version": config.engine_version,
        "config_version": config.config_version,
        "provider_name": config.provider.name,
        "provider_settings": config.provider.selected_settings(),
        "scoring": {
            "bullish_threshold": config.scoring.bullish_threshold,
            "bearish_threshold": config.scoring.bearish_threshold,
            "vwap_band_pct": config.scoring.vwap_band_pct,
            "strong_move_pct": config.scoring.strong_move_pct,
            "relative_strength_pct": config.scoring.relative_strength_pct,
            "volume_multiple_threshold": config.scoring.volume_multiple_threshold,
        },
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _load_simple_toml(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current = root
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            current = _nested_section(root, name)
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


def _provider_settings(raw: dict[str, Any], provider_name: str) -> dict[str, Any]:
    selected = raw.get(provider_name, {})
    if not isinstance(selected, dict):
        raise ValueError(f"config section [providers.{provider_name}] must be a table")
    return dict(selected)


def _named_settings(raw: dict[str, Any], name: str) -> dict[str, Any]:
    selected = raw.get(name, {})
    if not isinstance(selected, dict):
        raise ValueError(f"config section [{name}] must be a table")
    return dict(selected)


def _default_storage_target(storage_kind: str) -> str:
    if storage_kind == "sqlite":
        return "output/signals.db"
    return "output/runs"


def _nested_section(root: dict[str, Any], dotted_name: str) -> dict[str, Any]:
    current = root
    for part in dotted_name.split("."):
        existing = current.setdefault(part, {})
        if not isinstance(existing, dict):
            raise ValueError(f"config section [{dotted_name}] conflicts with scalar value")
        current = existing
    return current
