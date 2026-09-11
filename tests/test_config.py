"""Configuration loading and validation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from foma.config import ConfigError, FomaConfig


def test_load_missing_file_uses_defaults(tmp_path: Path) -> None:
    config = FomaConfig.load(tmp_path / "does-not-exist.toml")
    assert config.app.poll_interval_s == 0.5
    assert config.app.cooldown_s == 4.0
    assert config.app.browsers == ("chrome", "firefox")
    assert config.detection.uia_enabled is True
    assert config.detection.screen_fallback is True


def test_partial_override_merges_with_defaults(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        "[app]\npoll_interval_s = 1.25\n[detection]\nconfidence = 0.9\n",
        encoding="utf-8",
    )
    config = FomaConfig.load(tmp_path / "config.toml")
    assert config.app.poll_interval_s == 1.25
    assert config.app.browsers == ("chrome", "firefox")  # untouched default
    assert config.detection.confidence == 0.9
    assert config.detection.uia_enabled is True


def test_construct_inline(make_config) -> None:
    config = make_config(app={"cooldown_s": 2.0}, detection={"name_patterns": ("skip",)})
    assert config.app.cooldown_s == 2.0
    assert config.detection.name_patterns == ("skip",)


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("app", "poll_interval_s", 0.001),
        ("app", "poll_interval_s", 61.0),
        ("app", "cooldown_s", 0.0),
        ("app", "ram_sample_interval_s", 0.0),
        ("detection", "confidence", 1.5),
        ("detection", "confidence", -0.1),
        ("detection", "search_depth", 0),
        ("detection", "search_depth", 200),
    ],
)
def test_invalid_values_rejected(tmp_path: Path, section: str, key: str, value) -> None:
    (tmp_path / "config.toml").write_text(
        f"[{section}]\n{key} = {value!r}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        FomaConfig.load(tmp_path / "config.toml")


def test_invalid_browser_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text('[app]\nbrowsers = ["safari"]\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="unsupported browser"):
        FomaConfig.load(tmp_path / "config.toml")


def test_empty_browser_list_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text("[app]\nbrowsers = []\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        FomaConfig.load(tmp_path / "config.toml")


def test_invalid_regex_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        '[detection]\nname_patterns = ["[unclosed"]\n',
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="invalid regex"):
        FomaConfig.load(tmp_path / "config.toml")


def test_unknown_key_rejected(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text("[app]\nnonsense = true\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unknown configuration key"):
        FomaConfig.load(tmp_path / "config.toml")
