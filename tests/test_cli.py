"""Tests for CLI behavior."""

from pathlib import Path

import pytest

from topdown_shooter.app.cli import main


def test_cli_inspect_map_prints_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI should print an inspection summary for a valid package."""
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "_manifest.json").write_text(
        """
        {
          "schema_version": "generation-manifest-v3",
          "versions": {
            "generator": "0.0.10",
            "pipeline": "pipeline-v1",
            "schemas": {"tactical_map": "tactical-map-v0.22"}
          },
          "profile": "clear_map",
          "seed": "random",
          "resolved_seed": 123,
          "dimensions": {"width_tiles": 3, "height_tiles": 1, "tile_size_px": 16}
        }
        """,
        encoding="utf-8",
    )
    (package_dir / "validation_report.json").write_text(
        """
        {"status": "passed", "errors": [], "warnings": []}
        """,
        encoding="utf-8",
    )
    (package_dir / "tactical_map.json").write_text(
        """
        {
          "map": {"tile_grid_format": "ascii_rows", "tile_grid": ["S+G"]},
          "movement_costs": {"S": 1, "G": 1, "+": 1},
          "combat_zones": [],
          "cover_points": [],
          "choke_points": [],
          "flank_routes": [],
          "enemy_spawn_zones": [],
          "fallback_positions": []
        }
        """,
        encoding="utf-8",
    )

    exit_code = main(["--map", str(package_dir), "--inspect-map"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Map package loaded" in captured.out
    assert "generator: 0.0.10" in captured.out
