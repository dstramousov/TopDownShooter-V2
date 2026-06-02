"""Tests for prepared visual runtime debug rendering."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from topdown_shooter.config.runtime_config import WindowConfig
from topdown_shooter.prepared_visual import (
    PreparedVisualChunk,
    PreparedVisualElement,
    PreparedVisualMap,
    PreparedVisualObject,
)
from topdown_shooter.rendering.camera import (
    CameraAimOffset,
    CameraLookahead,
    CameraVelocity,
    RuntimeCamera,
)
from topdown_shooter.rendering.prepared_visual_debug_renderer import (
    PreparedVisualDebugRenderer,
)
from topdown_shooter.world.coordinates import WorldCoord


class FakeRaylib:
    """Small raylib test double collecting primitive draw calls."""

    def __init__(self) -> None:
        """Initialize the draw-call collector."""
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def Color(self, red: int, green: int, blue: int, alpha: int) -> tuple[int, int, int, int]:
        """Return a comparable color tuple."""
        return (red, green, blue, alpha)

    def Rectangle(self, x: float, y: float, width: float, height: float) -> SimpleNamespace:
        """Return a rectangle-like object."""
        return SimpleNamespace(x=x, y=y, width=width, height=height)

    def draw_rectangle(self, *args: Any) -> None:
        """Record a rectangle call."""
        self.calls.append(("rectangle", args))

    def draw_rectangle_rounded(self, *args: Any) -> None:
        """Record a rounded rectangle call."""
        self.calls.append(("rounded", args))

    def draw_circle(self, *args: Any) -> None:
        """Record a circle call."""
        self.calls.append(("circle", args))


def _camera() -> RuntimeCamera:
    """Build a camera centered over the tiny fixture map."""
    return RuntimeCamera(
        target=WorldCoord(x=16.0, y=16.0),
        desired_target=WorldCoord(x=16.0, y=16.0),
        zoom=1.0,
        follow_player=False,
        velocity=CameraVelocity(x=0.0, y=0.0),
        lookahead_offset=CameraLookahead(x=0.0, y=0.0),
        aim_offset=CameraAimOffset(x=0.0, y=0.0),
        dead_zone_radius_px=0.0,
    )


def _prepared_visual_map() -> PreparedVisualMap:
    """Build a minimal prepared visual map fixture."""
    return PreparedVisualMap(
        prepared_dir=Path("/tmp/prepared"),
        visual_map_dir=Path("/tmp/prepared/visual_map"),
        width_tiles=2,
        height_tiles=2,
        tile_size_px=16,
        layers=(
            PreparedVisualElement(
                element_id="base_0000_0000",
                layer="base_ground",
                family="clearing_ground",
                kind="clearing",
                x=0,
                y=0,
                variant=0,
                alpha=1.0,
                visual_only=True,
                raw={},
            ),
            PreparedVisualElement(
                element_id="forest_blob_000",
                layer="structures_and_blockers",
                family="forest_canopy_blob",
                kind="region_scale_canopy_blob",
                x=1,
                y=0,
                variant=0,
                alpha=0.5,
                visual_only=True,
                raw={},
            ),
        ),
        objects=(
            PreparedVisualObject(
                object_id="dressing_000",
                source="scene_dressing",
                layer="surface_decals",
                family="reed_cluster",
                kind="bank_reeds",
                x=0,
                y=1,
                variant=0,
                visual_only=True,
                raw={},
            ),
        ),
        chunks=(
            PreparedVisualChunk(
                chunk_id="chunk_000_000",
                x=0,
                y=0,
                bounds_tiles={"x": 0, "y": 0, "w": 2, "h": 2},
                layer_elements=2,
                object_elements=1,
                raw={},
            ),
        ),
        micro_scenes=(),
        micro_scene_layouts={},
        micro_scene_objects={},
    )


def test_prepared_visual_debug_renderer_draws_layers_and_objects() -> None:
    """Renderer should draw prepared visual layer and object elements."""
    raylib = FakeRaylib()
    renderer = PreparedVisualDebugRenderer(raylib)

    stats = renderer.draw(
        prepared_visual_map=_prepared_visual_map(),
        camera=_camera(),
        window_config=WindowConfig(
            title="test",
            target_fps=60,
            width=64,
            height=64,
        ),
    )

    assert stats.drawn_layer_elements == 2
    assert stats.drawn_object_elements == 1
    assert stats.total_layer_elements == 2
    assert stats.total_object_elements == 1
    call_names = [call[0] for call in raylib.calls]
    assert call_names.count("rectangle") >= 2
    assert "circle" in call_names
