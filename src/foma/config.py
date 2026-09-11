"""Configuration loading and validation for FOMA.

The config is expressed as TOML on disk and frozen dataclasses in code. Full
validation happens once at startup so every downstream module can rely on
well-formed values.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = "config.toml"

ALLOWED_BROWSERS = ("chrome", "edge", "firefox")

DEFAULTS: dict[str, Any] = {
    "app": {
        "poll_interval_s": 0.5,
        "cooldown_s": 4.0,
        "browsers": ["chrome", "firefox"],
        "log_dir": "logs",
        "cursor_restore": True,
        "console_summary_interval_s": 30.0,
        "ram_sample_interval_s": 5.0,
    },
    "detection": {
        "uia_enabled": True,
        "screen_fallback": True,
        "template_dir": "assets/templates",
        "name_patterns": [r"skip\s*(ads?)?\s*$", ".*ad.*skip.*"],
        "confidence": 0.85,
        "search_depth": 64,
    },
}


class ConfigError(ValueError):
    """Raised when the configuration is invalid."""


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@dataclass(frozen=True)
class AppConfig:
    poll_interval_s: float = 0.5
    cooldown_s: float = 4.0
    browsers: tuple[str, ...] = ("chrome", "firefox")
    log_dir: Path = Path("logs")
    cursor_restore: bool = True
    console_summary_interval_s: float = 30.0
    ram_sample_interval_s: float = 5.0


@dataclass(frozen=True)
class DetectionConfig:
    uia_enabled: bool = True
    screen_fallback: bool = True
    template_dir: Path = Path("assets/templates")
    name_patterns: tuple[str, ...] = (r"skip\s*(ads?)?\s*$", ".*ad.*skip.*")
    confidence: float = 0.85
    search_depth: int = 64


@dataclass(frozen=True)
class FomaConfig:
    app: AppConfig
    detection: DetectionConfig

    @classmethod
    def load(cls, path: str | Path | None = None) -> FomaConfig:
        """Load and validate configuration from a TOML file (or defaults)."""
        data = _deep_merge(DEFAULTS, {})
        if path is None:
            path = Path(DEFAULT_CONFIG_PATH)
        path = Path(path)
        if path.exists():
            with path.open("rb") as fh:
                data = _deep_merge(DEFAULTS, tomllib.load(fh))
        return cls.from_mapping(data)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> FomaConfig:
        app_raw = dict(data.get("app", {}))
        det_raw = dict(data.get("detection", {}))
        app = AppConfig(**cls._validated(**app_raw))  # type: ignore[arg-type]
        detection = DetectionConfig(**cls._validated(**det_raw))  # type: ignore[arg-type]
        return cls(app=app, detection=detection)

    @staticmethod
    def _validated(**kwargs: Any) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in kwargs.items():
            try:
                out[key] = _VALIDATORS[key](value)
            except KeyError:
                raise ConfigError(f"Unknown configuration key: {key!r}") from None
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"Invalid value for {key!r}: {value!r} ({exc})") from None
        return out


def _bounded(predicate, message: str):
    def validate(value):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError("expected a number")
        if not predicate(float(value)):
            raise ValueError(message)
        return float(value)

    return validate


def _val_browsers(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("expected a non-empty list of browser names")
    browsers = tuple(str(b).lower() for b in value)
    unknown = [b for b in browsers if b not in ALLOWED_BROWSERS]
    if unknown:
        raise ValueError(f"unsupported browser(s): {', '.join(unknown)}")
    return browsers


def _val_paths(value: Any) -> Path:
    return Path(str(value))


def _val_patterns(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("expected a non-empty list of regex patterns")
    patterns = tuple(str(p) for p in value)
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid regex {pattern!r}: {exc}") from None
    return patterns


def _val_depth(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("expected an integer")
    if not 1 <= value <= 128:
        raise ValueError("expected a depth between 1 and 128")
    return value


_VALIDATORS: dict[str, Any] = {
    "poll_interval_s": _bounded(lambda v: 0.05 <= v <= 60, "must be between 0.05 and 60"),
    "cooldown_s": _bounded(lambda v: 0.1 <= v <= 3600, "must be between 0.1 and 3600"),
    "browsers": _val_browsers,
    "log_dir": _val_paths,
    "cursor_restore": lambda v: bool(v),
    "console_summary_interval_s": _bounded(lambda v: 1 <= v <= 3600, "must be between 1 and 3600"),
    "ram_sample_interval_s": _bounded(lambda v: 0.2 <= v <= 3600, "must be between 0.2 and 3600"),
    "uia_enabled": lambda v: bool(v),
    "screen_fallback": lambda v: bool(v),
    "template_dir": _val_paths,
    "name_patterns": _val_patterns,
    "confidence": _bounded(lambda v: 0.0 <= v <= 1.0, "must be between 0 and 1"),
    "search_depth": _val_depth,
}
