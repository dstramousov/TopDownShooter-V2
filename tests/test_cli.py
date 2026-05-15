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


def test_cli_missing_map_path_prints_recovery_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI should explain how to recover from a missing map path."""
    missing_dir = tmp_path / "missing-package"

    exit_code = main(["--map", str(missing_dir), "--inspect-map"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Map package is not valid or not generated yet." in captured.err
    assert "The --map path does not exist." in captured.err
    assert "Expected a TopDownMapGen output directory:" in captured.err


def test_cli_missing_manifest_prints_missing_file_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI should name a missing required map package file."""
    package_dir = tmp_path / "package"
    package_dir.mkdir()

    exit_code = main(["--map", str(package_dir), "--inspect-map"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Missing required file:" in captured.err
    assert "_manifest.json" in captured.err
    assert "--map points to the generated output directory" in captured.err


def test_cli_file_path_prints_directory_hint(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI should reject a file path passed as --map."""
    map_file = tmp_path / "tactical_map.json"
    map_file.write_text("{}", encoding="utf-8")

    exit_code = main(["--map", str(map_file), "--inspect-map"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "The --map path must be a directory, not a file." in captured.err
    assert "--map does not point to a single JSON file" in captured.err
