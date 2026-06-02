"""Tests for prepared visual JSON loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from topdown_shooter.prepared_visual import PreparedVisualLoader


def _contract() -> dict[str, bool]:
    """Return a gameplay-safe prepared visual contract block."""
    return {
        "changes_gameplay": False,
        "changes_collision": False,
        "moves_markers": False,
    }


def _dimensions() -> dict[str, int]:
    """Return tiny fixture dimensions."""
    return {
        "width_tiles": 4,
        "height_tiles": 3,
        "tile_size_px": 16,
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write deterministic JSON fixture data."""
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _write_prepared_visual_fixture(prepared_dir: Path) -> None:
    """Write a minimal prepared visual artifact set."""
    visual_map_dir = prepared_dir / "visual_map"
    visual_map_dir.mkdir(parents=True)
    dimensions = _dimensions()

    _write_json(
        visual_map_dir / "visual_art_layers.json",
        {
            "schema_version": "visual-art-layers-v1",
            "contract": _contract(),
            "dimensions": dimensions,
            "layers": [
                {
                    "id": "layer_000",
                    "layer": "base_ground",
                    "family": "clearing_ground",
                    "kind": "base",
                    "tile": {"x": 0, "y": 0},
                    "variant": 0,
                    "visual_only": True,
                },
            ],
        },
    )
    _write_json(
        visual_map_dir / "visual_art_objects.json",
        {
            "schema_version": "visual-art-objects-v1",
            "contract": _contract(),
            "dimensions": dimensions,
            "objects": [
                {
                    "id": "object_000",
                    "source": "scene_dressing",
                    "layer": "surface_decals",
                    "family": "reed_cluster",
                    "kind": "bank_reeds",
                    "tile": {"x": 1, "y": 1},
                    "variant": 0,
                    "visual_only": True,
                },
            ],
        },
    )
    _write_json(
        visual_map_dir / "visual_art_chunks.json",
        {
            "schema_version": "visual-art-chunks-v1",
            "contract": _contract(),
            "dimensions": dimensions,
            "chunks": [
                {
                    "id": "chunk_000_000",
                    "x": 0,
                    "y": 0,
                    "bounds_tiles": {"x": 0, "y": 0, "w": 4, "h": 3},
                    "layer_elements": 1,
                    "object_elements": 1,
                },
            ],
        },
    )
    _write_json(
        visual_map_dir / "visual_micro_scenes.json",
        {
            "schema_version": "visual-micro-scenes-v1",
            "contract": _contract(),
            "scenes": [
                {
                    "id": "scene_000",
                    "type": "environment_wetland",
                    "preset_id": "water_lowland_mud",
                    "visual_role": "environment_detail",
                    "bounds": {"min_x": 0, "min_y": 0, "max_x": 3, "max_y": 2},
                    "center": {"x": 1, "y": 1},
                },
            ],
        },
    )
    _write_json(
        visual_map_dir / "visual_micro_scene_layouts.json",
        {
            "schema_version": "visual-micro-scene-layouts-v1",
            "contract": _contract(),
            "layouts": [],
        },
    )
    _write_json(
        visual_map_dir / "visual_micro_scene_objects.json",
        {
            "schema_version": "visual-micro-scene-objects-v1",
            "contract": _contract(),
            "objects": [],
        },
    )


def test_loader_accepts_min_max_micro_scene_bounds(tmp_path: Path) -> None:
    """Loader should normalize min/max scene bounds to x/y/w/h bounds."""
    prepared_dir = tmp_path / "prepared"
    _write_prepared_visual_fixture(prepared_dir)

    prepared_visual = PreparedVisualLoader().load(prepared_dir)

    assert len(prepared_visual.micro_scenes) == 1
    scene = prepared_visual.micro_scenes[0]
    assert scene.preset == "water_lowland_mud"
    assert scene.bounds == {"x": 0, "y": 0, "w": 4, "h": 3}
