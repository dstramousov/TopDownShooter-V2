"""Tests for prepared visual runtime render mode selection."""

from pathlib import Path

import pytest

from topdown_shooter.app.run_game import _resolve_prepared_visual
from topdown_shooter.config.runtime_config import RuntimeConfigError
from topdown_shooter.prepared_visual import PreparedVisualLoadError


class FakeLoader:
    """Small prepared visual loader test double."""

    def __init__(self, result: object | None = None, error: Exception | None = None) -> None:
        """Initialize the fake loader."""
        self.result = result if result is not None else object()
        self.error = error
        self.calls: list[Path] = []

    def load(self, prepared_dir: Path) -> object:
        """Record load calls and return or raise the configured result."""
        self.calls.append(prepared_dir)
        if self.error is not None:
            raise self.error
        return self.result


def test_visual_render_legacy_never_loads_prepared_visual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy visual mode should ignore prepared visual artifacts."""
    loader = FakeLoader()
    monkeypatch.setattr("topdown_shooter.app.run_game.PreparedVisualLoader", lambda: loader)

    result = _resolve_prepared_visual(
        package_dir=tmp_path,
        visual_render="legacy",
        renderer="2d",
    )

    assert result is None
    assert loader.calls == []


def test_visual_render_auto_falls_back_when_artifacts_are_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auto visual mode should fall back to legacy when prepared data is absent."""
    loader = FakeLoader()
    monkeypatch.setattr("topdown_shooter.app.run_game.PreparedVisualLoader", lambda: loader)

    result = _resolve_prepared_visual(
        package_dir=tmp_path,
        visual_render="auto",
        renderer="2d",
    )

    assert result is None
    assert loader.calls == []


def test_visual_render_prepared_debug_requires_artifacts(tmp_path: Path) -> None:
    """Explicit prepared-debug mode should fail when artifacts are absent."""
    with pytest.raises(RuntimeConfigError, match="Prepared visual debug rendering"):
        _resolve_prepared_visual(
            package_dir=tmp_path,
            visual_render="prepared-debug",
            renderer="2d",
        )


def test_visual_render_prepared_debug_loads_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit prepared-debug mode should load prepared visual data."""
    visual_map_dir = tmp_path / "visual_map"
    visual_map_dir.mkdir()
    (visual_map_dir / "visual_art_layers.json").write_text("{}", encoding="utf-8")
    prepared_visual = object()
    loader = FakeLoader(result=prepared_visual)
    monkeypatch.setattr("topdown_shooter.app.run_game.PreparedVisualLoader", lambda: loader)

    result = _resolve_prepared_visual(
        package_dir=tmp_path,
        visual_render="prepared-debug",
        renderer="2d",
    )

    assert result is prepared_visual
    assert loader.calls == [tmp_path]


def test_visual_render_prepared_debug_reports_invalid_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit prepared-debug mode should surface invalid prepared visual data."""
    visual_map_dir = tmp_path / "visual_map"
    visual_map_dir.mkdir()
    (visual_map_dir / "visual_art_layers.json").write_text("{}", encoding="utf-8")
    loader = FakeLoader(error=PreparedVisualLoadError("bad data"))
    monkeypatch.setattr("topdown_shooter.app.run_game.PreparedVisualLoader", lambda: loader)

    with pytest.raises(RuntimeConfigError, match="bad data"):
        _resolve_prepared_visual(
            package_dir=tmp_path,
            visual_render="prepared-debug",
            renderer="2d",
        )


def test_visual_render_3d_ignores_prepared_visual(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """3D renderer should not load 2D prepared visual data."""
    visual_map_dir = tmp_path / "visual_map"
    visual_map_dir.mkdir()
    (visual_map_dir / "visual_art_layers.json").write_text("{}", encoding="utf-8")
    loader = FakeLoader()
    monkeypatch.setattr("topdown_shooter.app.run_game.PreparedVisualLoader", lambda: loader)

    result = _resolve_prepared_visual(
        package_dir=tmp_path,
        visual_render="prepared-debug",
        renderer="3d",
    )

    assert result is None
    assert loader.calls == []
