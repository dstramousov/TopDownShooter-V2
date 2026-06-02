"""Pilot artistic preview rendering for prepared map baking."""

from __future__ import annotations

import struct
import zlib
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any


Color = tuple[int, int, int]
Point = tuple[int, int]


@dataclass(frozen=True, slots=True)
class PilotArtPreviewResult:
    """Pilot artistic preview rendering output.

    Attributes:
        preview_png: PNG image bytes.
        legend: Color and rendering-policy legend artifact.
        preview_report: Compact preview report for preparation tracking.
        preview_summary: Human-readable preview summary.
    """

    preview_png: bytes
    legend: dict[str, Any]
    preview_report: dict[str, Any]
    preview_summary: str


class PilotArtPreviewRenderer:
    """Render a deterministic painter-style pilot preview for prepared maps.

    The renderer is intentionally separate from the game renderer. It creates a
    non-gameplay PNG for checking whether prepared visual data moves toward a
    cohesive painted map rather than a per-tile debug overlay.
    """

    COLLECTION_KEYS = ("items", "objects", "visual_objects")
    DEFAULT_TILE_SIZE_PX = 16
    MAX_PREVIEW_SIZE_PX = 4096
    FOREST_CONTEXTS = frozenset({"forest_inner", "forest_edge", "forest_outer_corner", "forest_single"})
    ROAD_CONTEXTS = frozenset({"road_straight", "road_turn", "road_junction", "road_dead_end", "road_isolated"})
    WATER_CONTEXTS = frozenset({"water_patch", "water_single"})
    RUIN_CONTEXTS = frozenset({"ruin_floor", "ruin_wall"})

    BASE_COLORS: dict[str, Color] = {
        "clearing": (82, 110, 60),
        "blocked_structure": (54, 51, 45),
        "unknown": (76, 70, 66),
        "road": (112, 96, 66),
        "road_core": (150, 121, 78),
        "road_wet": (101, 84, 60),
        "road_grass_intrusion": (91, 124, 69),
        "road_shoulder": (130, 109, 75),
        "water": (34, 70, 76),
        "water_deep": (27, 55, 66),
        "water_shallow": (49, 86, 88),
        "water_bank": (91, 98, 60),
        "wet_mud": (91, 79, 54),
        "reeds": (119, 122, 64),
        "reed_dark": (68, 86, 45),
        "reed_tip": (154, 135, 74),
        "water_highlight": (79, 111, 110),
        "ruin_floor": (102, 100, 91),
        "ruin_floor_light": (134, 129, 112),
        "ruin_floor_dark": (61, 59, 54),
        "ruin_wall": (72, 72, 68),
        "ruin_wall_dark": (34, 34, 31),
        "ruin_wall_shadow": (24, 24, 22),
        "ruin_rubble": (148, 140, 116),
        "ruin_moss": (82, 111, 64),
        "ruin_dirt": (105, 88, 61),
        "forest_deep": (19, 43, 30),
        "forest_mid": (28, 61, 38),
        "forest_light": (42, 83, 49),
        "forest_crown": (49, 98, 56),
        "forest_shadow": (30, 54, 33),
        "grass_detail": (96, 130, 71),
        "road_detail": (146, 119, 77),
        "ruin_detail": (114, 111, 99),
        "mud_detail": (83, 72, 54),
        "object_muted": (133, 118, 82),
        "large_object": (112, 83, 62),
        "dressing_small": (86, 116, 67),
        "dressing_medium": (119, 103, 73),
        "dressing_large": (98, 79, 65),
    }

    def render(
        self,
        *,
        visual_context: dict[str, Any],
        scene_dressing: dict[str, Any],
        dressed_visual_objects: dict[str, Any],
    ) -> PilotArtPreviewResult:
        """Render a pilot artistic preview image.

        Args:
            visual_context: Per-tile visual context artifact.
            scene_dressing: Generated scene dressing artifact.
            dressed_visual_objects: Normalized objects with dressing appended.

        Returns:
            Pilot art preview PNG plus legend and reports.
        """
        dimensions = self._dimensions(visual_context)
        scale = self._preview_scale(
            width_tiles=dimensions["width_tiles"],
            height_tiles=dimensions["height_tiles"],
            tile_size_px=dimensions["tile_size_px"],
        )
        rows = self._context_rows(visual_context)
        canvas = _ArtCanvas(
            width=max(1, dimensions["width_tiles"] * scale),
            height=max(1, dimensions["height_tiles"] * scale),
            background=self.BASE_COLORS["unknown"],
        )

        terrain_stats = self._draw_base_terrain(canvas=canvas, rows=rows, scale=scale)
        forest_stats = self._paint_forest_regions(canvas=canvas, rows=rows, scale=scale)
        road_stats = self._paint_road_details(canvas=canvas, rows=rows, scale=scale)
        ruin_stats = self._paint_ruin_details(canvas=canvas, rows=rows, scale=scale)
        water_stats = self._paint_water_details(canvas=canvas, rows=rows, scale=scale)
        object_stats = self._paint_visual_objects(
            canvas=canvas,
            dressed_visual_objects=dressed_visual_objects,
            scale=scale,
            tile_size_px=dimensions["tile_size_px"],
        )
        dressing_stats = self._paint_scene_dressing(
            canvas=canvas,
            scene_dressing=scene_dressing,
            scale=scale,
            tile_size_px=dimensions["tile_size_px"],
        )
        report = self._build_report(
            dimensions=dimensions,
            scale=scale,
            terrain_stats=terrain_stats,
            forest_stats=forest_stats,
            road_stats=road_stats,
            ruin_stats=ruin_stats,
            water_stats=water_stats,
            object_stats=object_stats,
            dressing_stats=dressing_stats,
        )
        return PilotArtPreviewResult(
            preview_png=canvas.to_png_bytes(),
            legend=self._build_legend(dimensions=dimensions, scale=scale),
            preview_report=report,
            preview_summary=self.format_summary(report),
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format pilot art preview as readable text.

        Args:
            report: Preview report dictionary.

        Returns:
            Human-readable summary.
        """
        rendered = self._dict_value(report, "rendered")
        dimensions = self._dict_value(report, "dimensions")
        return "\n".join(
            [
                "Pilot artistic preview",
                f"- status: {report.get('status', 'unknown')}",
                (
                    "- image: "
                    f"{dimensions.get('preview_width_px', 'unknown')}x"
                    f"{dimensions.get('preview_height_px', 'unknown')} px"
                ),
                f"- preview scale: {dimensions.get('preview_scale_px_per_tile', 'unknown')}",
                f"- terrain tiles: {rendered.get('terrain_tiles', 'unknown')}",
                f"- forest paint stamps: {rendered.get('forest_stamps', 'unknown')}",
                f"- forest region blobs: {rendered.get('forest_region_blobs', 'unknown')}",
                f"- road details: {rendered.get('road_details', 'unknown')}",
                f"- road shoulders: {rendered.get('road_external_shoulder_tiles', 'unknown')}",
                f"- road grass intrusions: {rendered.get('road_grass_intrusions', 'unknown')}",
                f"- ruin details: {rendered.get('ruin_details', 'unknown')}",
                f"- ruin rubble: {rendered.get('ruin_rubble', 'unknown')}",
                f"- ruin moss: {rendered.get('ruin_moss', 'unknown')}",
                f"- ruin wall shadows: {rendered.get('ruin_wall_shadows', 'unknown')}",
                f"- water details: {rendered.get('water_details', 'unknown')}",
                f"- water region bodies: {rendered.get('water_region_bodies', 'unknown')}",
                f"- water bank tiles: {rendered.get('water_bank_tiles', 'unknown')}",
                f"- water reeds: {rendered.get('water_reeds', 'unknown')}",
                f"- rendered objects: {rendered.get('normalized_objects', 'unknown')}",
                f"- rendered dressing: {rendered.get('dressing_objects', 'unknown')}",
            ],
        )

    def _draw_base_terrain(
        self,
        *,
        canvas: _ArtCanvas,
        rows: list[list[dict[str, Any]]],
        scale: int,
    ) -> dict[str, int]:
        """Draw the muted base terrain layer.

        Args:
            canvas: RGB canvas.
            rows: Context rows.
            scale: Preview pixels per tile.

        Returns:
            Tile counts by primary context.
        """
        counts: Counter[str] = Counter()
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                primary = self._primary(cell)
                counts[primary] += 1
                color = self._base_color(primary=primary, x=x, y=y)
                canvas.fill_rect(x * scale, y * scale, scale, scale, color)
                if primary == "clearing" and self._stable_mod("grass-detail", x, y, modulo=7) == 0:
                    canvas.blend_rect(
                        x * scale + scale // 4,
                        y * scale + scale // 4,
                        max(1, scale // 2),
                        max(1, scale // 3),
                        self.BASE_COLORS["grass_detail"],
                        alpha=0.20,
                    )
        return dict(sorted(counts.items()))

    def _paint_forest_regions(
        self,
        *,
        canvas: _ArtCanvas,
        rows: list[list[dict[str, Any]]],
        scale: int,
    ) -> dict[str, int]:
        """Paint forest as connected masses with internal crown stamps.

        Args:
            canvas: RGB canvas.
            rows: Context rows.
            scale: Preview pixels per tile.

        Returns:
            Forest painting counters.
        """
        forest_mask = self._mask_for(rows, self.FOREST_CONTEXTS)
        depth_map = self._forest_depth_map(forest_mask)
        forest_tiles = 0
        stamps = 0
        soft_shadow_tiles = 0
        height = len(rows)
        width = len(rows[0]) if rows else 0
        for y in range(height):
            for x in range(width):
                if not forest_mask[y][x]:
                    if self._touches_mask(forest_mask, x=x, y=y):
                        soft_shadow_tiles += 1
                        canvas.blend_rect(
                            x * scale,
                            y * scale,
                            scale,
                            scale,
                            self.BASE_COLORS["forest_shadow"],
                            alpha=0.10,
                        )
                    continue
                forest_tiles += 1
                depth = depth_map[y][x]
                base = self._forest_mass_color(x=x, y=y, depth=depth)
                canvas.fill_rect(x * scale, y * scale, scale, scale, base)
                if self._should_draw_forest_tile_stamp(x=x, y=y, depth=depth):
                    self._draw_forest_stamp(canvas=canvas, x=x, y=y, scale=scale, depth=depth, index=0)
                    stamps += 1

        region_stats = self._paint_forest_region_blobs(
            canvas=canvas,
            forest_mask=forest_mask,
            depth_map=depth_map,
            scale=scale,
        )
        return {
            "forest_tiles": forest_tiles,
            "forest_stamps": stamps,
            "forest_region_blobs": region_stats["region_blobs"],
            "forest_regions_painted": region_stats["regions_painted"],
            "soft_shadow_tiles": soft_shadow_tiles,
        }

    def _paint_road_details(
        self,
        *,
        canvas: _ArtCanvas,
        rows: list[list[dict[str, Any]]],
        scale: int,
    ) -> dict[str, int]:
        """Paint roads as soft path regions instead of full-tile strips.

        Args:
            canvas: RGB canvas.
            rows: Context rows.
            scale: Preview pixels per tile.

        Returns:
            Road painter counters.
        """
        road_mask = self._mask_for(rows, self.ROAD_CONTEXTS)
        road_tiles = 0
        shoulder_tiles = 0
        grass_intrusions = 0
        junction_tiles = 0
        dirt_noise = 0
        height = len(rows)
        width = len(rows[0]) if rows else 0

        for y in range(height):
            for x in range(width):
                if not road_mask[y][x]:
                    if self._touches_mask(road_mask, x=x, y=y):
                        shoulder_tiles += 1
                        self._draw_road_external_shoulder(canvas=canvas, x=x, y=y, scale=scale)
                    continue

                road_tiles += 1
                connections = self._road_connections(road_mask, x=x, y=y)
                if sum(connections.values()) >= 3:
                    junction_tiles += 1
                self._draw_road_tile_base(canvas=canvas, x=x, y=y, scale=scale)
                self._draw_road_shoulder(canvas=canvas, x=x, y=y, scale=scale, connections=connections)
                self._draw_road_core(canvas=canvas, x=x, y=y, scale=scale, connections=connections)
                dirt_noise += self._draw_road_noise(canvas=canvas, x=x, y=y, scale=scale, connections=connections)
                grass_intrusions += self._draw_road_grass_intrusions(canvas=canvas, x=x, y=y, scale=scale)

        return {
            "road_details": road_tiles,
            "road_tiles": road_tiles,
            "road_external_shoulder_tiles": shoulder_tiles,
            "road_junction_tiles": junction_tiles,
            "road_dirt_noise": dirt_noise,
            "road_grass_intrusions": grass_intrusions,
        }

    def _draw_road_tile_base(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> None:
        """Blend a road tile toward grass before painting the continuous path body.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
        """
        base = self._shift_color(self.BASE_COLORS["clearing"], self._stable_mod("road-base", x, y, modulo=9) - 4)
        canvas.blend_rect(x * scale, y * scale, scale, scale, base, alpha=0.24)

    def _draw_road_external_shoulder(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> None:
        """Draw a very faint dirt wash on non-road cells adjacent to a road.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
        """
        if self._stable_mod("road-ext-shoulder-skip", x, y, modulo=2) == 0:
            return
        offset_x = self._stable_mod("road-ext-x", x, y, modulo=max(1, scale // 3)) - scale // 6
        offset_y = self._stable_mod("road-ext-y", y, x, modulo=max(1, scale // 3)) - scale // 6
        canvas.blend_ellipse(
            x * scale + scale // 2 + offset_x,
            y * scale + scale // 2 + offset_y,
            max(2, scale * 3 // 5),
            max(2, scale // 2),
            self.BASE_COLORS["road_shoulder"],
            alpha=0.08,
        )

    def _draw_road_shoulder(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        connections: dict[str, bool],
    ) -> None:
        """Draw the broad faded dirt body of a continuous path.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            connections: Cardinal road connections.
        """
        left = x * scale
        top = y * scale
        center = scale // 2
        connection_count = sum(connections.values())
        body_width = max(4, scale * 3 // 4)
        half = body_width // 2
        color = self.BASE_COLORS["road_shoulder"]
        alpha = 0.48 if connection_count >= 3 else 0.40
        canvas.blend_ellipse(left + center, top + center, max(3, half), max(3, half), color, alpha=alpha)
        if connections["N"]:
            canvas.blend_rect(left + center - half, top, body_width, center + half, color, alpha=alpha)
        if connections["S"]:
            canvas.blend_rect(left + center - half, top + center - half, body_width, center + half + 1, color, alpha=alpha)
        if connections["W"]:
            canvas.blend_rect(left, top + center - half, center + half, body_width, color, alpha=alpha)
        if connections["E"]:
            canvas.blend_rect(left + center - half, top + center - half, center + half + 1, body_width, color, alpha=alpha)
        if connection_count == 0:
            canvas.blend_ellipse(left + center, top + center, max(3, scale * 2 // 5), max(3, scale // 3), color, alpha=0.38)

    def _draw_road_core(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        connections: dict[str, bool],
    ) -> None:
        """Draw the continuous worn center of the path.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            connections: Cardinal road connections.
        """
        left = x * scale
        top = y * scale
        center = scale // 2
        connection_count = sum(connections.values())
        core = max(4, scale * 7 // 16)
        half = max(2, core // 2)
        color = self.BASE_COLORS["road_core"]
        alpha = 0.62 if connection_count < 3 else 0.70
        canvas.blend_ellipse(left + center, top + center, max(3, half), max(3, half), color, alpha=alpha)
        if connections["N"]:
            canvas.blend_rect(left + center - half, top, core, center + half, color, alpha=alpha)
        if connections["S"]:
            canvas.blend_rect(left + center - half, top + center - half, core, center + half + 1, color, alpha=alpha)
        if connections["W"]:
            canvas.blend_rect(left, top + center - half, center + half, core, color, alpha=alpha)
        if connections["E"]:
            canvas.blend_rect(left + center - half, top + center - half, center + half + 1, core, color, alpha=alpha)
        if connection_count >= 3:
            canvas.blend_ellipse(left + center, top + center, max(4, scale * 3 // 5), max(4, scale // 2), color, alpha=0.28)
        if connection_count == 0:
            canvas.blend_ellipse(left + center, top + center, max(3, scale * 2 // 5), max(2, scale // 3), color, alpha=0.50)

    def _draw_road_noise(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        connections: dict[str, bool],
    ) -> int:
        """Draw sparse larger worn-dirt patches on a road tile.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            connections: Cardinal road connections.

        Returns:
            Number of noise marks drawn.
        """
        marks = 1 if self._stable_mod("road-noise-a", x, y, modulo=4) == 0 else 0
        if sum(connections.values()) >= 3 and self._stable_mod("road-noise-junction", x, y, modulo=2) == 0:
            marks += 1
        for mark_index in range(marks):
            width = max(2, scale // 2)
            height = max(2, scale // 3)
            offset_x = self._stable_mod(f"road-noise-x-{mark_index}", x, y, modulo=max(1, scale - width))
            offset_y = self._stable_mod(f"road-noise-y-{mark_index}", y, x, modulo=max(1, scale - height))
            canvas.blend_ellipse(
                x * scale + offset_x + width // 2,
                y * scale + offset_y + height // 2,
                max(1, width // 2),
                max(1, height // 2),
                self.BASE_COLORS["road_wet"],
                alpha=0.12,
            )
        return marks

    def _draw_road_grass_intrusions(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> int:
        """Draw rare grass patches intruding into the road body.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.

        Returns:
            Number of grass intrusion marks drawn.
        """
        if self._stable_mod("road-grass-skip", x, y, modulo=7) != 0:
            return 0
        width = max(3, scale // 2)
        height = max(2, scale // 4)
        offset_x = self._stable_mod("road-grass-x", x, y, modulo=max(1, scale - width))
        offset_y = self._stable_mod("road-grass-y", y, x, modulo=max(1, scale - height))
        canvas.blend_ellipse(
            x * scale + offset_x + width // 2,
            y * scale + offset_y + height // 2,
            max(1, width // 2),
            max(1, height // 2),
            self.BASE_COLORS["road_grass_intrusion"],
            alpha=0.12,
        )
        return 1

    def _mask_connections(self, mask: list[list[bool]], *, x: int, y: int) -> dict[str, bool]:
        """Return cardinal connections for a boolean mask cell.

        Args:
            mask: Boolean mask.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            Dictionary with N/E/S/W boolean connections.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        return {
            "N": y > 0 and mask[y - 1][x],
            "E": x + 1 < width and mask[y][x + 1],
            "S": y + 1 < height and mask[y + 1][x],
            "W": x > 0 and mask[y][x - 1],
        }

    def _road_connections(self, road_mask: list[list[bool]], *, x: int, y: int) -> dict[str, bool]:
        """Return cardinal road connections for a road tile.

        Args:
            road_mask: True for road cells.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            Dictionary with N/E/S/W boolean connections.
        """
        height = len(road_mask)
        width = len(road_mask[0]) if road_mask else 0
        return {
            "N": y > 0 and road_mask[y - 1][x],
            "E": x + 1 < width and road_mask[y][x + 1],
            "S": y + 1 < height and road_mask[y + 1][x],
            "W": x > 0 and road_mask[y][x - 1],
        }

    def _paint_ruin_details(
        self,
        *,
        canvas: _ArtCanvas,
        rows: list[list[dict[str, Any]]],
        scale: int,
    ) -> dict[str, int]:
        """Paint ruins as broken stone places with rubble, dirt, and moss.

        Args:
            canvas: RGB canvas.
            rows: Context rows.
            scale: Preview pixels per tile.

        Returns:
            Ruin painter counters.
        """
        ruin_mask = self._mask_for(rows, self.RUIN_CONTEXTS)
        wall_mask = self._mask_for(rows, frozenset({"ruin_wall"}))
        floor_tiles = 0
        wall_tiles = 0
        cracks = 0
        rubble = 0
        moss = 0
        dirt = 0
        wall_shadows = 0
        broken_hints = 0
        debris_clusters = 0
        height = len(rows)
        width = len(rows[0]) if rows else 0

        for y in range(height):
            for x in range(width):
                primary = self._primary(rows[y][x])
                if primary == "ruin_floor":
                    floor_tiles += 1
                    self._draw_ruin_floor(canvas=canvas, x=x, y=y, scale=scale, near_wall=self._touches_mask(wall_mask, x=x, y=y))
                    if self._stable_mod("ruin-floor-crack", x, y, modulo=2) == 0:
                        cracks += 1
                        self._draw_ruin_crack(canvas=canvas, x=x, y=y, scale=scale)
                    if self._touches_mask(wall_mask, x=x, y=y) and self._stable_mod("ruin-floor-moss", x, y, modulo=2) == 0:
                        moss += 1
                        self._draw_ruin_moss(canvas=canvas, x=x, y=y, scale=scale)
                    if self._stable_mod("ruin-floor-dirt", x, y, modulo=4) == 0:
                        dirt += 1
                        self._draw_ruin_dirt(canvas=canvas, x=x, y=y, scale=scale)
                    continue

                if primary == "ruin_wall":
                    wall_tiles += 1
                    connections = self._mask_connections(wall_mask, x=x, y=y)
                    self._draw_ruin_wall_mass(canvas=canvas, x=x, y=y, scale=scale, connections=connections)
                    wall_shadows += self._draw_ruin_wall_shadow(canvas=canvas, x=x, y=y, scale=scale, connections=connections)
                    if self._stable_mod("ruin-wall-broken", x, y, modulo=2) == 0:
                        broken_hints += 1
                        self._draw_ruin_broken_hint(canvas=canvas, x=x, y=y, scale=scale, connections=connections)
                    if self._stable_mod("ruin-wall-rubble", x, y, modulo=1) == 0:
                        rubble += 1
                        self._draw_ruin_rubble(canvas=canvas, x=x, y=y, scale=scale, on_wall=True)
                    continue

                if self._touches_mask(ruin_mask, x=x, y=y) and self._allows_ruin_debris(primary):
                    if self._stable_mod("ruin-adjacent-rubble", x, y, modulo=2) == 0:
                        rubble += 1
                        debris_clusters += 1
                        self._draw_ruin_rubble(canvas=canvas, x=x, y=y, scale=scale, on_wall=False)
                    if self._stable_mod("ruin-adjacent-moss", x, y, modulo=3) == 0:
                        moss += 1
                        self._draw_ruin_moss(canvas=canvas, x=x, y=y, scale=scale)

        return {
            "ruin_details": floor_tiles + wall_tiles,
            "ruin_floor_tiles": floor_tiles,
            "ruin_wall_tiles": wall_tiles,
            "ruin_floor_cracks": cracks,
            "ruin_rubble": rubble,
            "ruin_moss": moss,
            "ruin_dirt": dirt,
            "ruin_wall_shadows": wall_shadows,
            "ruin_broken_hints": broken_hints,
            "ruin_debris_clusters": debris_clusters,
        }

    def _draw_ruin_floor(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int, near_wall: bool) -> None:
        """Draw a muted irregular stone floor tile.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            near_wall: Whether the tile is adjacent to a wall tile.
        """
        alpha = 0.48 if near_wall else 0.38
        left = x * scale
        top = y * scale
        canvas.blend_rect(left, top, scale, scale, self.BASE_COLORS["ruin_floor_dark"], alpha=0.20)
        canvas.blend_rect(
            left + max(1, scale // 8),
            top + max(1, scale // 8),
            max(2, scale * 3 // 4),
            max(2, scale * 3 // 4),
            self.BASE_COLORS["ruin_floor"],
            alpha=0.44,
        )
        if self._stable_mod("ruin-floor-light", x, y, modulo=2) == 0:
            canvas.blend_rect(
                left + scale // 5,
                top + scale // 5,
                max(2, scale * 3 // 5),
                max(2, scale // 2),
                self.BASE_COLORS["ruin_floor_light"],
                alpha=alpha,
            )
        if near_wall:
            canvas.blend_rect(
                left,
                top + scale * 3 // 4,
                scale,
                max(1, scale // 5),
                self.BASE_COLORS["ruin_wall_shadow"],
                alpha=0.18,
            )

    def _draw_ruin_wall_mass(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        connections: dict[str, bool],
    ) -> None:
        """Draw a heavier broken wall mass inside a wall tile.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            connections: Cardinal wall connections.
        """
        left = x * scale
        top = y * scale
        center = scale // 2
        half = max(4, scale * 7 // 16)
        color = self.BASE_COLORS["ruin_wall_dark"]
        canvas.blend_rect(left + center - half, top + center - half, half * 2, half * 2, color, alpha=0.70)
        canvas.blend_rect(
            left + center - max(2, half * 2 // 3),
            top + center - max(2, half * 2 // 3),
            max(3, half * 4 // 3),
            max(3, half * 4 // 3),
            self.BASE_COLORS["ruin_wall"],
            alpha=0.32,
        )
        if connections["N"]:
            canvas.blend_rect(left + center - half, top, half * 2, center, color, alpha=0.62)
        if connections["S"]:
            canvas.blend_rect(left + center - half, top + center, half * 2, center, color, alpha=0.62)
        if connections["W"]:
            canvas.blend_rect(left, top + center - half, center, half * 2, color, alpha=0.62)
        if connections["E"]:
            canvas.blend_rect(left + center, top + center - half, center, half * 2, color, alpha=0.62)

    def _draw_ruin_wall_shadow(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        connections: dict[str, bool],
    ) -> int:
        """Draw subtle wall-base shadow into adjacent wall gaps.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            connections: Cardinal wall connections.

        Returns:
            Number of shadow marks drawn.
        """
        marks = 0
        left = x * scale
        top = y * scale
        shadow = self.BASE_COLORS["ruin_wall_shadow"]
        if not connections["S"]:
            marks += 1
            canvas.blend_rect(left + scale // 5, top + scale * 2 // 3, scale * 3 // 5, max(1, scale // 5), shadow, alpha=0.44)
        if not connections["E"] and self._stable_mod("ruin-shadow-east", x, y, modulo=2) == 0:
            marks += 1
            canvas.blend_rect(left + scale * 2 // 3, top + scale // 5, max(1, scale // 5), scale * 3 // 5, shadow, alpha=0.22)
        return marks

    def _draw_ruin_crack(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> None:
        """Draw a short stone crack on ruin floor.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
        """
        horizontal = self._stable_mod("ruin-crack-dir", x, y, modulo=2) == 0
        width = max(2, scale // 2 if horizontal else scale // 5)
        height = max(1, scale // 6 if horizontal else scale // 2)
        offset_x = self._stable_mod("ruin-crack-x", x, y, modulo=max(1, scale - width))
        offset_y = self._stable_mod("ruin-crack-y", y, x, modulo=max(1, scale - height))
        canvas.blend_rect(x * scale + offset_x, y * scale + offset_y, width, height, self.BASE_COLORS["ruin_detail"], alpha=0.34)

    def _draw_ruin_rubble(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int, on_wall: bool) -> None:
        """Draw a small deterministic rubble cluster.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            on_wall: Whether the rubble belongs to a wall cell.
        """
        count = 5 if on_wall else 4
        for index in range(count):
            size = max(2, scale // (4 if on_wall else 5))
            ox = self._stable_mod(f"ruin-rubble-x-{index}", x, y, modulo=max(1, scale - size))
            oy = self._stable_mod(f"ruin-rubble-y-{index}", y, x, modulo=max(1, scale - size))
            canvas.blend_rect(x * scale + ox, y * scale + oy, size, size, self.BASE_COLORS["ruin_rubble"], alpha=0.58)

    def _draw_ruin_moss(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> None:
        """Draw a muted moss patch near ruins.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
        """
        width = max(3, scale * 2 // 3)
        height = max(2, scale // 2)
        ox = self._stable_mod("ruin-moss-x", x, y, modulo=max(1, scale - width))
        oy = self._stable_mod("ruin-moss-y", y, x, modulo=max(1, scale - height))
        canvas.blend_ellipse(
            x * scale + ox + width // 2,
            y * scale + oy + height // 2,
            max(1, width // 2),
            max(1, height // 2),
            self.BASE_COLORS["ruin_moss"],
            alpha=0.42,
        )

    def _draw_ruin_dirt(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> None:
        """Draw a dirty floor patch on ruin tiles.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
        """
        canvas.blend_ellipse(
            x * scale + scale // 2,
            y * scale + scale // 2,
            max(2, scale // 3),
            max(2, scale // 4),
            self.BASE_COLORS["ruin_dirt"],
            alpha=0.32,
        )

    def _draw_ruin_broken_hint(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        connections: dict[str, bool],
    ) -> None:
        """Draw a small gap or highlight to break wall regularity.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            connections: Cardinal wall connections.
        """
        del connections
        width = max(3, scale // 2)
        height = max(2, scale // 4)
        ox = self._stable_mod("ruin-break-x", x, y, modulo=max(1, scale - width))
        oy = self._stable_mod("ruin-break-y", y, x, modulo=max(1, scale - height))
        canvas.blend_rect(x * scale + ox, y * scale + oy, width, height, self.BASE_COLORS["ruin_floor_light"], alpha=0.42)

    def _allows_ruin_debris(self, primary: str) -> bool:
        """Return whether adjacent terrain may receive visual-only ruin debris.

        Args:
            primary: Primary visual context.

        Returns:
            True when debris may be painted without implying a blocker.
        """
        return primary in {"clearing", "ruin_floor", "blocked_structure"}

    def _paint_water_details(
        self,
        *,
        canvas: _ArtCanvas,
        rows: list[list[dict[str, Any]]],
        scale: int,
    ) -> dict[str, int]:
        """Paint water as cohesive puddle regions with soft muddy banks.

        Args:
            canvas: RGB canvas.
            rows: Context rows.
            scale: Preview pixels per tile.

        Returns:
            Water painter counters.
        """
        water_mask = self._mask_for(rows, self.WATER_CONTEXTS)
        water_tiles = 0
        bank_tiles = 0
        reeds = 0
        dark_patches = 0
        highlights = 0
        height = len(rows)
        width = len(rows[0]) if rows else 0

        region_body_stats = self._paint_water_region_bodies(
            canvas=canvas,
            water_mask=water_mask,
            scale=scale,
        )

        for y in range(height):
            for x in range(width):
                primary = self._primary(rows[y][x])
                if water_mask[y][x]:
                    water_tiles += 1
                    connections = self._mask_connections(water_mask, x=x, y=y)
                    neighbor_count = sum(connections.values())
                    self._draw_water_tile_body(
                        canvas=canvas,
                        x=x,
                        y=y,
                        scale=scale,
                        connections=connections,
                        neighbor_count=neighbor_count,
                    )
                    if self._touches_outside(water_mask, x=x, y=y):
                        dark_patches += self._draw_water_edge_noise(canvas=canvas, x=x, y=y, scale=scale)
                        reeds += self._draw_water_reeds(canvas=canvas, x=x, y=y, scale=scale, inside_water=True)
                    else:
                        highlights += self._draw_water_inner_highlight(canvas=canvas, x=x, y=y, scale=scale)
                    continue

                if self._touches_mask(water_mask, x=x, y=y) and self._allows_water_bank(primary):
                    bank_tiles += 1
                    self._draw_water_bank(canvas=canvas, x=x, y=y, scale=scale)
                    reeds += self._draw_water_reeds(canvas=canvas, x=x, y=y, scale=scale, inside_water=False)

        region_wash_stats = self._paint_water_region_washes(
            canvas=canvas,
            water_mask=water_mask,
            scale=scale,
        )
        return {
            "water_details": water_tiles,
            "water_tiles": water_tiles,
            "water_bank_tiles": bank_tiles,
            "water_reeds": reeds,
            "water_dark_patches": dark_patches,
            "water_highlights": highlights,
            "water_region_bodies": region_body_stats["water_region_bodies"],
            "water_regions_filled": region_body_stats["water_regions_filled"],
            "water_region_washes": region_wash_stats["water_region_washes"],
            "water_regions_painted": region_wash_stats["water_regions_painted"],
        }

    def _paint_water_region_bodies(
        self,
        *,
        canvas: _ArtCanvas,
        water_mask: list[list[bool]],
        scale: int,
    ) -> dict[str, int]:
        """Paint calm continuous bodies for connected water regions.

        Args:
            canvas: RGB canvas.
            water_mask: True for water cells.
            scale: Preview pixels per tile.

        Returns:
            Water body counters.
        """
        bodies = 0
        regions_filled = 0
        for region_index, cells in enumerate(self._connected_mask_regions(water_mask)):
            if not cells:
                continue
            regions_filled += 1
            for cell_index, (x, y) in enumerate(cells):
                connections = self._mask_connections(water_mask, x=x, y=y)
                phase = self._stable_mod("water-body-phase", x + region_index, y + cell_index, modulo=4)
                radius_x = max(4, scale * (8 + phase) // 16)
                radius_y = max(4, scale * (7 + phase // 2) // 16)
                alpha = 0.24 if sum(connections.values()) > 0 else 0.18
                canvas.blend_ellipse(
                    x * scale + scale // 2,
                    y * scale + scale // 2,
                    radius_x,
                    radius_y,
                    self.BASE_COLORS["water_shallow"],
                    alpha=alpha,
                )
                if connections["E"]:
                    canvas.blend_rect(
                        x * scale + scale // 2,
                        y * scale + scale // 4,
                        scale,
                        max(2, scale // 2),
                        self.BASE_COLORS["water_shallow"],
                        alpha=0.18,
                    )
                if connections["S"]:
                    canvas.blend_rect(
                        x * scale + scale // 4,
                        y * scale + scale // 2,
                        max(2, scale // 2),
                        scale,
                        self.BASE_COLORS["water_shallow"],
                        alpha=0.18,
                    )
                if self._stable_mod("water-body-deep", x, y, modulo=5) == 0:
                    canvas.blend_ellipse(
                        x * scale + scale // 2,
                        y * scale + scale // 2,
                        max(3, radius_x * 2 // 3),
                        max(3, radius_y * 2 // 3),
                        self.BASE_COLORS["water_deep"],
                        alpha=0.16,
                    )
                bodies += 1
        return {"water_region_bodies": bodies, "water_regions_filled": regions_filled}

    def _draw_water_tile_body(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        connections: dict[str, bool],
        neighbor_count: int,
    ) -> None:
        """Draw a quiet puddle body for one logical water tile.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            connections: Cardinal water connections.
            neighbor_count: Number of cardinal water neighbors.
        """
        left = x * scale
        top = y * scale
        center = scale // 2
        shallow = self._shift_color(
            self.BASE_COLORS["water_shallow"],
            self._stable_mod("water-shallow", x, y, modulo=5) - 2,
        )
        deep = self._shift_color(
            self.BASE_COLORS["water_deep"],
            self._stable_mod("water-deep", x, y, modulo=5) - 2,
        )
        outer_radius = max(4, scale // 2)
        inner_radius_x = max(3, scale * (4 if neighbor_count > 0 else 3) // 12)
        inner_radius_y = max(3, scale * (3 if neighbor_count > 0 else 2) // 12)
        body_alpha = 0.54 if neighbor_count > 0 else 0.44
        canvas.blend_ellipse(left + center, top + center, outer_radius, outer_radius, shallow, alpha=body_alpha)
        if connections["N"]:
            canvas.blend_rect(left + center - outer_radius, top, outer_radius * 2, center + 1, shallow, alpha=0.46)
        if connections["S"]:
            canvas.blend_rect(left + center - outer_radius, top + center - 1, outer_radius * 2, center + 1, shallow, alpha=0.46)
        if connections["W"]:
            canvas.blend_rect(left, top + center - outer_radius, center + 1, outer_radius * 2, shallow, alpha=0.46)
        if connections["E"]:
            canvas.blend_rect(left + center - 1, top + center - outer_radius, center + 1, outer_radius * 2, shallow, alpha=0.46)
        if neighbor_count >= 2 or self._stable_mod("water-small-deep", x, y, modulo=4) == 0:
            canvas.blend_ellipse(left + center, top + center, inner_radius_x, inner_radius_y, deep, alpha=0.26)

    def _draw_water_bank(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> None:
        """Draw a visible soft muddy transition patch on land adjacent to water.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
        """
        offset_x = self._stable_mod("water-bank-x", x, y, modulo=max(1, scale // 2)) - scale // 4
        offset_y = self._stable_mod("water-bank-y", y, x, modulo=max(1, scale // 2)) - scale // 4
        radius_x = max(4, scale * (4 + self._stable_mod("water-bank-rx", x, y, modulo=3)) // 5)
        radius_y = max(3, scale * (3 + self._stable_mod("water-bank-ry", y, x, modulo=3)) // 5)
        canvas.blend_ellipse(
            x * scale + scale // 2 + offset_x,
            y * scale + scale // 2 + offset_y,
            radius_x,
            radius_y,
            self.BASE_COLORS["wet_mud"],
            alpha=0.22,
        )
        canvas.blend_ellipse(
            x * scale + scale // 2 - offset_x // 2,
            y * scale + scale // 2 - offset_y // 2,
            max(2, radius_x // 2),
            max(2, radius_y // 2),
            self.BASE_COLORS["water_bank"],
            alpha=0.18,
        )

    def _draw_water_edge_noise(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> int:
        """Draw rare muddy variation on a water edge tile.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.

        Returns:
            Number of patches drawn.
        """
        if self._stable_mod("water-edge-noise", x, y, modulo=5) != 0:
            return 0
        width = max(3, scale // 2)
        height = max(2, scale // 3)
        offset_x = self._stable_mod("water-edge-noise-x", x, y, modulo=max(1, scale - width))
        offset_y = self._stable_mod("water-edge-noise-y", y, x, modulo=max(1, scale - height))
        canvas.blend_ellipse(
            x * scale + offset_x + width // 2,
            y * scale + offset_y + height // 2,
            max(1, width // 2),
            max(1, height // 2),
            self.BASE_COLORS["wet_mud"],
            alpha=0.12,
        )
        return 1

    def _draw_water_inner_highlight(self, *, canvas: _ArtCanvas, x: int, y: int, scale: int) -> int:
        """Draw very rare subtle highlights inside larger water blobs.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.

        Returns:
            Number of highlights drawn.
        """
        if self._stable_mod("water-highlight-skip", x, y, modulo=9) != 0:
            return 0
        width = max(2, scale // 3)
        y_offset = self._stable_mod("water-highlight-y", x, y, modulo=max(1, scale // 3))
        canvas.blend_rect(
            x * scale + scale // 3,
            y * scale + scale // 3 + y_offset,
            width,
            max(1, scale // 12),
            self.BASE_COLORS["water_highlight"],
            alpha=0.12,
        )
        return 1

    def _draw_water_reeds(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        inside_water: bool,
    ) -> int:
        """Draw sparse readable reed clusters near water edges.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            inside_water: Whether the reed cluster is placed inside water.

        Returns:
            Number of reed clusters drawn.
        """
        modulo = 17 if inside_water else 4
        if self._stable_mod("water-reeds-skip", x, y, modulo=modulo) != 0:
            return 0
        cluster_x = x * scale + self._stable_mod("water-reeds-x", x, y, modulo=max(1, scale - 6)) + 3
        cluster_y = y * scale + self._stable_mod("water-reeds-y", y, x, modulo=max(1, scale - 5)) + 4
        canvas.blend_ellipse(
            cluster_x,
            cluster_y + max(1, scale // 5),
            max(2, scale // 4),
            max(1, scale // 7),
            self.BASE_COLORS["wet_mud"],
            alpha=0.22,
        )
        stem_count = 5 if not inside_water else 3
        for reed_index in range(stem_count):
            dx = (reed_index - stem_count // 2) * 2
            height = max(4, scale // 2 + self._stable_mod(f"water-reed-h-{reed_index}", x, y, modulo=5))
            stem_x = cluster_x + dx
            stem_y = cluster_y - height // 2
            canvas.blend_rect(stem_x, stem_y, 1, height, self.BASE_COLORS["reed_dark"], alpha=0.58)
            canvas.blend_rect(stem_x + 1, stem_y + max(1, height // 4), 1, max(2, height * 2 // 3), self.BASE_COLORS["reeds"], alpha=0.42)
            if reed_index % 2 == 0:
                canvas.blend_rect(stem_x - 1, stem_y, 3, 1, self.BASE_COLORS["reed_tip"], alpha=0.44)
        return 1

    def _paint_water_region_washes(
        self,
        *,
        canvas: _ArtCanvas,
        water_mask: list[list[bool]],
        scale: int,
    ) -> dict[str, int]:
        """Paint calm final washes across connected water regions.

        Args:
            canvas: RGB canvas.
            water_mask: True for water cells.
            scale: Preview pixels per tile.

        Returns:
            Water-region wash counters.
        """
        washes = 0
        regions_painted = 0
        for region_index, cells in enumerate(self._connected_mask_regions(water_mask)):
            if not cells:
                continue
            regions_painted += 1
            budget = max(1, min(4, len(cells) // 10 + 1))
            phase = self._stable_mod("water-region-phase", region_index, len(cells), modulo=max(1, len(cells)))
            for wash_index in range(budget):
                x, y = cells[(phase + wash_index * 11 + wash_index * wash_index) % len(cells)]
                radius_x = max(5, scale * (3 + self._stable_mod("water-wash-rx", x, y, modulo=3)) // 2)
                radius_y = max(4, scale * (2 + self._stable_mod("water-wash-ry", y, x, modulo=3)) // 2)
                canvas.blend_ellipse(
                    x * scale + scale // 2,
                    y * scale + scale // 2,
                    radius_x,
                    radius_y,
                    self.BASE_COLORS["water"],
                    alpha=0.08,
                )
                washes += 1
        return {"water_region_washes": washes, "water_regions_painted": regions_painted}

    def _allows_water_bank(self, primary: str) -> bool:
        """Return whether a terrain context may receive a muddy water bank.

        Args:
            primary: Primary terrain context.

        Returns:
            True when the context can receive visual-only water-edge treatment.
        """
        return primary not in self.FOREST_CONTEXTS and primary not in self.RUIN_CONTEXTS and primary not in {"ruin_wall", "blocked_structure"}

    def _paint_visual_objects(
        self,
        *,
        canvas: _ArtCanvas,
        dressed_visual_objects: dict[str, Any],
        scale: int,
        tile_size_px: int,
    ) -> dict[str, Any]:
        """Paint normalized runtime objects as muted silhouettes.

        Args:
            canvas: RGB canvas.
            dressed_visual_objects: Visual object artifact after scene dressing.
            scale: Preview pixels per tile.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Object rendering stats.
        """
        rendered = 0
        skipped = 0
        by_family: Counter[str] = Counter()
        for item in self._object_items(dressed_visual_objects):
            if not isinstance(item, dict):
                skipped += 1
                continue
            if self._bool_value(item.get("visual_only"), default=False):
                continue
            position = self._object_tile_position(item, tile_size_px=tile_size_px)
            if position is None:
                skipped += 1
                continue
            tile_x, tile_y = position
            family = self._object_family(item)
            by_family[family] += 1
            color = self.BASE_COLORS["large_object"] if self._large_family(family) else self.BASE_COLORS["object_muted"]
            self._draw_soft_object(canvas=canvas, tile_x=tile_x, tile_y=tile_y, scale=scale, color=color)
            rendered += 1
        return {
            "rendered": rendered,
            "skipped_without_position": skipped,
            "counts_by_family": dict(sorted(by_family.items())),
        }

    def _paint_scene_dressing(
        self,
        *,
        canvas: _ArtCanvas,
        scene_dressing: dict[str, Any],
        scale: int,
        tile_size_px: int,
    ) -> dict[str, Any]:
        """Paint generated scene dressing as low-contrast details.

        Args:
            canvas: RGB canvas.
            scene_dressing: Scene dressing artifact.
            scale: Preview pixels per tile.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Dressing rendering stats.
        """
        objects = scene_dressing.get("objects")
        if not isinstance(objects, list):
            return {"rendered": 0, "skipped_without_position": 0, "counts_by_category": {}}
        rendered = 0
        skipped = 0
        by_category: Counter[str] = Counter()
        for item in objects:
            if not isinstance(item, dict):
                skipped += 1
                continue
            position = self._object_tile_position(item, tile_size_px=tile_size_px)
            if position is None:
                skipped += 1
                continue
            tile_x, tile_y = position
            category = self._string_value(item.get("category"), default="medium_props")
            by_category[category] += 1
            color = self._dressing_color(category)
            size = max(1, scale // (3 if category == "small_decals" else 2))
            offset_x = self._stable_mod("dress-x", tile_x, tile_y, modulo=max(1, scale - size))
            offset_y = self._stable_mod("dress-y", tile_x, tile_y, modulo=max(1, scale - size))
            canvas.blend_rect(tile_x * scale + offset_x, tile_y * scale + offset_y, size, size, color, alpha=0.34)
            rendered += 1
        return {
            "rendered": rendered,
            "skipped_without_position": skipped,
            "counts_by_category": dict(sorted(by_category.items())),
        }

    def _should_draw_forest_tile_stamp(self, *, x: int, y: int, depth: int) -> bool:
        """Return whether a small local forest detail should be drawn.

        Args:
            x: Tile X coordinate.
            y: Tile Y coordinate.
            depth: Forest depth estimate.

        Returns:
            True when the tile should receive a small local crown hint.
        """
        if depth >= 3:
            return self._stable_mod("forest-local-deep", x, y, modulo=3) == 0
        if depth == 2:
            return self._stable_mod("forest-local-mid", x, y, modulo=4) == 0
        return self._stable_mod("forest-local-edge", x, y, modulo=6) == 0

    def _paint_forest_region_blobs(
        self,
        *,
        canvas: _ArtCanvas,
        forest_mask: list[list[bool]],
        depth_map: list[list[int]],
        scale: int,
    ) -> dict[str, int]:
        """Paint larger deterministic canopy blobs per connected forest region.

        Args:
            canvas: RGB canvas.
            forest_mask: True for forest cells.
            depth_map: Forest depth estimate per tile.
            scale: Preview pixels per tile.

        Returns:
            Region-level blob counters.
        """
        blobs = 0
        regions_painted = 0
        for region_index, cells in enumerate(self._connected_mask_regions(forest_mask)):
            if not cells:
                continue
            regions_painted += 1
            blob_budget = self._forest_blob_budget(len(cells))
            phase = self._stable_mod("forest-region-phase", region_index, len(cells), modulo=max(1, len(cells)))
            for blob_index in range(blob_budget):
                cell_index = (phase + blob_index * 17 + blob_index * blob_index * 7) % len(cells)
                x, y = cells[cell_index]
                depth = depth_map[y][x]
                self._draw_forest_region_blob(
                    canvas=canvas,
                    x=x,
                    y=y,
                    scale=scale,
                    depth=depth,
                    region_index=region_index,
                    blob_index=blob_index,
                )
                blobs += 1
        return {"region_blobs": blobs, "regions_painted": regions_painted}

    def _forest_blob_budget(self, cell_count: int) -> int:
        """Return a bounded number of painter blobs for a forest region.

        Args:
            cell_count: Number of tiles in the connected forest region.

        Returns:
            Blob count for region painting.
        """
        if cell_count <= 0:
            return 0
        if cell_count < 8:
            return 1
        return max(2, min(80, cell_count // 12))

    def _draw_forest_region_blob(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        depth: int,
        region_index: int,
        blob_index: int,
    ) -> None:
        """Draw a larger canopy blob spanning beyond one logical tile.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            depth: Forest depth estimate.
            region_index: Connected forest region index.
            blob_index: Blob index inside the region.
        """
        seed_x = self._stable_mod("forest-blob-x", x + region_index, y + blob_index, modulo=max(1, scale))
        seed_y = self._stable_mod("forest-blob-y", x + blob_index, y + region_index, modulo=max(1, scale))
        center_x = x * scale + seed_x
        center_y = y * scale + seed_y
        radius_x = max(3, scale * (2 + self._stable_mod("forest-blob-rx", x, y, modulo=3)) // 2)
        radius_y = max(3, scale * (1 + self._stable_mod("forest-blob-ry", y, x, modulo=3)) // 2)
        color = self.BASE_COLORS["forest_mid"] if depth >= 2 else self.BASE_COLORS["forest_crown"]
        if self._stable_mod("forest-blob-tone", x, y, modulo=5) == 0:
            color = self.BASE_COLORS["forest_deep"]
        canvas.blend_ellipse(center_x, center_y, radius_x, radius_y, color, alpha=0.20)
        if self._stable_mod("forest-blob-highlight", x, y, modulo=4) == 0:
            canvas.blend_ellipse(
                center_x - max(1, radius_x // 4),
                center_y - max(1, radius_y // 5),
                max(2, radius_x // 2),
                max(2, radius_y // 2),
                self.BASE_COLORS["forest_crown"],
                alpha=0.14,
            )

    def _connected_mask_regions(self, mask: list[list[bool]]) -> list[list[Point]]:
        """Return connected true regions from a boolean mask.

        Args:
            mask: Boolean mask.

        Returns:
            List of connected regions with tile coordinates.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        visited = [[False for _x in range(width)] for _y in range(height)]
        regions: list[list[Point]] = []
        for y in range(height):
            for x in range(width):
                if visited[y][x] or not mask[y][x]:
                    continue
                cells: list[Point] = []
                queue: deque[Point] = deque([(x, y)])
                visited[y][x] = True
                while queue:
                    cx, cy = queue.popleft()
                    cells.append((cx, cy))
                    for nx, ny in self._cardinal_neighbors(cx, cy, width=width, height=height):
                        if visited[ny][nx] or not mask[ny][nx]:
                            continue
                        visited[ny][nx] = True
                        queue.append((nx, ny))
                regions.append(cells)
        return regions

    def _draw_forest_stamp(
        self,
        *,
        canvas: _ArtCanvas,
        x: int,
        y: int,
        scale: int,
        depth: int,
        index: int,
    ) -> None:
        """Draw one deterministic tree-crown-like stamp inside a forest tile.

        Args:
            canvas: RGB canvas.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            scale: Preview pixels per tile.
            depth: Forest depth estimate.
            index: Stamp index inside the tile.
        """
        seed = self._stable_mod(f"forest-stamp-{index}", x, y, modulo=10_000)
        max_offset = max(1, scale // 2)
        center_x = x * scale + scale // 4 + seed % max_offset
        center_y = y * scale + scale // 4 + (seed // 17) % max_offset
        radius = max(2, scale // (3 if depth <= 1 else 2))
        color = self.BASE_COLORS["forest_crown"] if depth <= 1 else self.BASE_COLORS["forest_mid"]
        alpha = 0.32 if depth <= 1 else 0.24
        canvas.blend_ellipse(center_x, center_y, radius, max(2, radius * 2 // 3), color, alpha=alpha)

    def _draw_soft_object(
        self,
        *,
        canvas: _ArtCanvas,
        tile_x: int,
        tile_y: int,
        scale: int,
        color: Color,
    ) -> None:
        """Draw a muted object marker that is less debug-like than a square dot.

        Args:
            canvas: RGB canvas.
            tile_x: Tile X coordinate.
            tile_y: Tile Y coordinate.
            scale: Preview pixels per tile.
            color: Object color.
        """
        width = max(2, scale * 3 // 5)
        height = max(2, scale // 3)
        x = tile_x * scale + (scale - width) // 2
        y = tile_y * scale + (scale - height) // 2
        canvas.blend_rect(x, y, width, height, color, alpha=0.45)
        if scale >= 8:
            canvas.blend_rect(x + width // 4, y - 1, max(1, width // 2), 1, color, alpha=0.35)

    def _base_color(self, *, primary: str, x: int, y: int) -> Color:
        """Return a deterministic base color for a primary context.

        Args:
            primary: Visual primary context.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            RGB color.
        """
        jitter = self._stable_mod("base-jitter", x, y, modulo=13) - 6
        if primary in self.FOREST_CONTEXTS:
            return self._shift_color(self.BASE_COLORS["forest_mid"], jitter)
        if primary in self.ROAD_CONTEXTS:
            return self._shift_color(self.BASE_COLORS["road"], jitter)
        if primary == "ruin_wall":
            return self._shift_color(self.BASE_COLORS["ruin_wall"], jitter)
        if primary == "ruin_floor":
            return self._shift_color(self.BASE_COLORS["ruin_floor"], jitter)
        if primary in self.WATER_CONTEXTS:
            return self._shift_color(self.BASE_COLORS["water_bank"], jitter)
        if primary == "blocked_structure":
            return self._shift_color(self.BASE_COLORS["blocked_structure"], jitter)
        if primary == "clearing":
            return self._shift_color(self.BASE_COLORS["clearing"], jitter)
        return self.BASE_COLORS["unknown"]

    def _forest_mass_color(self, *, x: int, y: int, depth: int) -> Color:
        """Return painter-style forest mass color without explicit outlines.

        Args:
            x: Tile X coordinate.
            y: Tile Y coordinate.
            depth: Distance from non-forest cells.

        Returns:
            RGB color.
        """
        noise = self._stable_mod("forest-mass", x, y, modulo=17) - 8
        if depth >= 3:
            return self._shift_color(self.BASE_COLORS["forest_deep"], noise)
        if depth == 2:
            return self._shift_color(self.BASE_COLORS["forest_mid"], noise)
        return self._shift_color(self.BASE_COLORS["forest_light"], noise)

    def _forest_depth_map(self, forest_mask: list[list[bool]]) -> list[list[int]]:
        """Build a small Manhattan distance-to-outside map for forest tiles.

        Args:
            forest_mask: True for forest cells.

        Returns:
            Depth per tile. Non-forest cells have depth 0.
        """
        height = len(forest_mask)
        width = len(forest_mask[0]) if forest_mask else 0
        depths = [[0 for _x in range(width)] for _y in range(height)]
        queue: deque[Point] = deque()
        for y in range(height):
            for x in range(width):
                if not forest_mask[y][x]:
                    continue
                if self._touches_outside(forest_mask, x=x, y=y):
                    depths[y][x] = 1
                    queue.append((x, y))
        while queue:
            x, y = queue.popleft()
            next_depth = min(depths[y][x] + 1, 4)
            for nx, ny in self._cardinal_neighbors(x, y, width=width, height=height):
                if not forest_mask[ny][nx] or depths[ny][nx] != 0:
                    continue
                depths[ny][nx] = next_depth
                queue.append((nx, ny))
        return depths

    def _mask_for(
        self,
        rows: list[list[dict[str, Any]]],
        contexts: frozenset[str],
    ) -> list[list[bool]]:
        """Build a boolean mask for primary contexts.

        Args:
            rows: Context rows.
            contexts: Primary context names to include.

        Returns:
            Boolean mask.
        """
        return [[self._primary(cell) in contexts for cell in row] for row in rows]

    def _touches_mask(self, mask: list[list[bool]], *, x: int, y: int) -> bool:
        """Return whether a cell touches true values in a mask.

        Args:
            mask: Boolean mask.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            True when any 8-neighbor is true.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        if y < 0 or y >= height or x < 0 or x >= width or mask[y][x]:
            return False
        for ny in range(max(0, y - 1), min(height, y + 2)):
            for nx in range(max(0, x - 1), min(width, x + 2)):
                if mask[ny][nx]:
                    return True
        return False

    def _touches_outside(self, mask: list[list[bool]], *, x: int, y: int) -> bool:
        """Return whether a forest cell touches non-forest or map outside.

        Args:
            mask: Forest mask.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            True when at least one cardinal neighbor is outside forest.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height or not mask[ny][nx]:
                return True
        return False

    def _cardinal_neighbors(self, x: int, y: int, *, width: int, height: int) -> list[Point]:
        """Return in-bounds cardinal neighbors.

        Args:
            x: Tile X coordinate.
            y: Tile Y coordinate.
            width: Map width in tiles.
            height: Map height in tiles.

        Returns:
            Neighbor coordinates.
        """
        result: list[Point] = []
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if 0 <= nx < width and 0 <= ny < height:
                result.append((nx, ny))
        return result

    def _build_report(
        self,
        *,
        dimensions: dict[str, int],
        scale: int,
        terrain_stats: dict[str, int],
        forest_stats: dict[str, int],
        road_stats: dict[str, int],
        ruin_stats: dict[str, int],
        water_stats: dict[str, int],
        object_stats: dict[str, Any],
        dressing_stats: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the pilot art preview report.

        Args:
            dimensions: Source tile dimensions.
            scale: Preview pixels per tile.
            terrain_stats: Tile counts by primary context.
            forest_stats: Forest painter counters.
            road_stats: Road detail counters.
            ruin_stats: Ruin detail counters.
            water_stats: Water detail counters.
            object_stats: Object rendering stats.
            dressing_stats: Dressing rendering stats.

        Returns:
            Preview report dictionary.
        """
        preview_width = max(1, dimensions["width_tiles"] * scale)
        preview_height = max(1, dimensions["height_tiles"] * scale)
        rendered_objects = self._int_value(object_stats.get("rendered"), default=0)
        rendered_dressing = self._int_value(dressing_stats.get("rendered"), default=0)
        forest_stamps = self._int_value(forest_stats.get("forest_stamps"), default=0)
        status = "ok" if preview_width > 0 and preview_height > 0 else "warning"
        return {
            "schema_version": "pilot-art-preview-report-v1",
            "status": status,
            "dimensions": {
                "width_tiles": dimensions["width_tiles"],
                "height_tiles": dimensions["height_tiles"],
                "tile_size_px": dimensions["tile_size_px"],
                "preview_scale_px_per_tile": scale,
                "preview_width_px": preview_width,
                "preview_height_px": preview_height,
            },
            "rendered": {
                "terrain_tiles": sum(terrain_stats.values()),
                "forest_stamps": forest_stamps,
                "forest_region_blobs": forest_stats.get("forest_region_blobs", 0),
                "forest_regions_painted": forest_stats.get("forest_regions_painted", 0),
                "forest_shadow_tiles": forest_stats.get("soft_shadow_tiles", 0),
                "road_details": road_stats.get("road_details", 0),
                "road_external_shoulder_tiles": road_stats.get("road_external_shoulder_tiles", 0),
                "road_junction_tiles": road_stats.get("road_junction_tiles", 0),
                "road_dirt_noise": road_stats.get("road_dirt_noise", 0),
                "road_grass_intrusions": road_stats.get("road_grass_intrusions", 0),
                "ruin_details": ruin_stats.get("ruin_details", 0),
                "ruin_floor_tiles": ruin_stats.get("ruin_floor_tiles", 0),
                "ruin_wall_tiles": ruin_stats.get("ruin_wall_tiles", 0),
                "ruin_floor_cracks": ruin_stats.get("ruin_floor_cracks", 0),
                "ruin_rubble": ruin_stats.get("ruin_rubble", 0),
                "ruin_moss": ruin_stats.get("ruin_moss", 0),
                "ruin_dirt": ruin_stats.get("ruin_dirt", 0),
                "ruin_wall_shadows": ruin_stats.get("ruin_wall_shadows", 0),
                "ruin_broken_hints": ruin_stats.get("ruin_broken_hints", 0),
                "ruin_debris_clusters": ruin_stats.get("ruin_debris_clusters", 0),
                "water_details": water_stats.get("water_details", 0),
                "water_region_bodies": water_stats.get("water_region_bodies", 0),
                "water_regions_filled": water_stats.get("water_regions_filled", 0),
                "water_bank_tiles": water_stats.get("water_bank_tiles", 0),
                "water_reeds": water_stats.get("water_reeds", 0),
                "water_dark_patches": water_stats.get("water_dark_patches", 0),
                "water_highlights": water_stats.get("water_highlights", 0),
                "water_region_washes": water_stats.get("water_region_washes", 0),
                "water_regions_painted": water_stats.get("water_regions_painted", 0),
                "normalized_objects": rendered_objects,
                "dressing_objects": rendered_dressing,
                "skipped_objects_without_position": (
                    self._int_value(object_stats.get("skipped_without_position"), default=0)
                    + self._int_value(dressing_stats.get("skipped_without_position"), default=0)
                ),
            },
            "terrain_counts_by_primary": terrain_stats,
            "object_counts_by_family": self._dict_value(object_stats, "counts_by_family"),
            "dressing_counts_by_category": self._dict_value(dressing_stats, "counts_by_category"),
            "contract": {
                "changes_gameplay": False,
                "changes_collision": False,
                "moves_markers": False,
            },
            "checks": [
                {
                    "code": "pilot_art_preview_built",
                    "status": "passed" if preview_width > 0 and preview_height > 0 else "warning",
                    "message": "Pilot art preview image was generated deterministically.",
                },
                {
                    "code": "forest_region_painter_used",
                    "status": "passed" if forest_stamps > 0 else "warning",
                    "message": "Forest was painted as connected mass with internal structure hints.",
                },
            ],
        }

    def _build_legend(self, *, dimensions: dict[str, int], scale: int) -> dict[str, Any]:
        """Build the pilot preview legend artifact.

        Args:
            dimensions: Source dimensions.
            scale: Preview pixels per tile.

        Returns:
            Legend dictionary.
        """
        return {
            "schema_version": "pilot-art-preview-legend-v1",
            "purpose": "Non-debug pilot art preview for prepared map visual direction checks.",
            "dimensions": dimensions | {"preview_scale_px_per_tile": scale},
            "colors_rgb": {key: list(value) for key, value in sorted(self.BASE_COLORS.items())},
            "rendering_policy": {
                "forest": "Paint connected forest masks as region-scale canopy masses with deterministic brush blobs; do not draw explicit edge outlines.",
                "roads": "Paint old-road masks as soft path regions with faded shoulders, dirt noise, junction wear, and grass intrusion hints while preserving logical road cells.",
                "water": "Paint water masks as puddle-like blobs with muddy banks, sparse reeds, darker edge patches, and subtle highlights without changing walkability.",
                "ruins": "Draw ruin floors and walls as readable gray structures with crack hints.",
                "dressing": "Draw scene dressing as subdued details, not debug markers.",
                "gameplay_changes": False,
            },
        }

    def _dimensions(self, visual_context: dict[str, Any]) -> dict[str, int]:
        """Extract safe preview dimensions from visual context.

        Args:
            visual_context: Visual context artifact.

        Returns:
            Width, height, and tile size dictionary.
        """
        raw_dimensions = self._dict_value(visual_context, "dimensions")
        return {
            "width_tiles": max(1, self._int_value(raw_dimensions.get("width_tiles"), default=1)),
            "height_tiles": max(1, self._int_value(raw_dimensions.get("height_tiles"), default=1)),
            "tile_size_px": max(1, self._int_value(raw_dimensions.get("tile_size_px"), default=self.DEFAULT_TILE_SIZE_PX)),
        }

    def _preview_scale(self, *, width_tiles: int, height_tiles: int, tile_size_px: int) -> int:
        """Return a bounded preview pixel scale per tile.

        Args:
            width_tiles: Map width in tiles.
            height_tiles: Map height in tiles.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Preview scale in pixels per tile.
        """
        if width_tiles <= 0 or height_tiles <= 0:
            return 1
        scale = max(1, tile_size_px)
        max_side_tiles = max(width_tiles, height_tiles)
        while max_side_tiles * scale > self.MAX_PREVIEW_SIZE_PX and scale > 1:
            scale //= 2
        return max(1, scale)

    def _context_rows(self, visual_context: dict[str, Any]) -> list[list[dict[str, Any]]]:
        """Return validated visual context rows.

        Args:
            visual_context: Visual context artifact.

        Returns:
            Rows containing dictionaries only.
        """
        rows = visual_context.get("rows")
        if not isinstance(rows, list):
            return []
        result: list[list[dict[str, Any]]] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            result.append([cell if isinstance(cell, dict) else {} for cell in row])
        return result

    def _object_items(self, visual_objects: dict[str, Any]) -> list[Any]:
        """Return visual object collection items.

        Args:
            visual_objects: Visual object artifact.

        Returns:
            Visual object entries as a list.
        """
        for key in self.COLLECTION_KEYS:
            value = visual_objects.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return list(value.values())
        return []

    def _object_tile_position(self, item: dict[str, Any], *, tile_size_px: int) -> Point | None:
        """Return tile position for visual object-like dictionaries.

        Args:
            item: Object entry.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Tile position or None.
        """
        for key in ("tile", "position", "grid_position"):
            position = item.get(key)
            if isinstance(position, dict):
                x = position.get("x")
                y = position.get("y")
                if x is not None and y is not None:
                    return self._int_value(x, default=0), self._int_value(y, default=0)
        if "x" in item and "y" in item:
            return self._int_value(item.get("x"), default=0), self._int_value(item.get("y"), default=0)
        pixel_x = item.get("pixel_x", item.get("px"))
        pixel_y = item.get("pixel_y", item.get("py"))
        if pixel_x is not None and pixel_y is not None:
            return (
                self._int_value(pixel_x, default=0) // max(1, tile_size_px),
                self._int_value(pixel_y, default=0) // max(1, tile_size_px),
            )
        return None

    def _object_family(self, item: dict[str, Any]) -> str:
        """Return a compact object family label.

        Args:
            item: Object entry.

        Returns:
            Object family string.
        """
        for key in ("resolved_family", "asset_family", "family", "type", "sprite_id", "asset_id"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value.removeprefix("object.")
        return "unknown"

    def _large_family(self, family: str) -> bool:
        """Return whether a family should read as a larger silhouette.

        Args:
            family: Object family name.

        Returns:
            True for large-looking object families.
        """
        return any(
            token in family
            for token in (
                "checkpoint",
                "radio_mast",
                "tent",
                "car_wreck",
                "cart",
                "generator",
                "trench",
                "berm",
                "log",
            )
        )

    def _dressing_color(self, category: str) -> Color:
        """Return muted dressing color by category.

        Args:
            category: Dressing category.

        Returns:
            RGB color.
        """
        if category == "small_decals":
            return self.BASE_COLORS["dressing_small"]
        if category == "large_props":
            return self.BASE_COLORS["dressing_large"]
        return self.BASE_COLORS["dressing_medium"]

    def _primary(self, cell: dict[str, Any]) -> str:
        """Return cell primary context.

        Args:
            cell: Context cell.

        Returns:
            Primary context string.
        """
        return self._string_value(cell.get("primary"), default="unknown")

    def _stable_mod(self, salt: str, x: int, y: int, *, modulo: int) -> int:
        """Return a stable coordinate hash modulo value.

        Args:
            salt: Salt string.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            modulo: Positive modulo value.

        Returns:
            Stable integer in ``[0, modulo)``.
        """
        if modulo <= 1:
            return 0
        value = 1469598103934665603
        for byte in f"{salt}:{x}:{y}".encode("utf-8"):
            value ^= byte
            value *= 1099511628211
            value &= 0xFFFFFFFFFFFFFFFF
        return value % modulo

    def _shift_color(self, color: Color, delta: int) -> Color:
        """Shift RGB color channels by a small delta.

        Args:
            color: Source RGB color.
            delta: Signed delta.

        Returns:
            Shifted RGB color.
        """
        return tuple(max(0, min(255, channel + delta)) for channel in color)

    def _dict_value(self, data: Any, key: str) -> dict[str, Any]:
        """Return a dictionary child or an empty dictionary.

        Args:
            data: Parent value.
            key: Child key.

        Returns:
            Child dictionary or empty dictionary.
        """
        if not isinstance(data, dict):
            return {}
        value = data.get(key)
        return value if isinstance(value, dict) else {}

    def _string_value(self, value: Any, *, default: str) -> str:
        """Return a string value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            String value or fallback.
        """
        return value if isinstance(value, str) and value else default

    def _int_value(self, value: Any, *, default: int) -> int:
        """Return an integer value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Integer value or fallback.
        """
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return default

    def _bool_value(self, value: Any, *, default: bool) -> bool:
        """Return a boolean value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Boolean value or fallback.
        """
        return value if isinstance(value, bool) else default


class _ArtCanvas:
    """Small RGB canvas with painter-style primitives for PNG output."""

    def __init__(self, *, width: int, height: int, background: Color) -> None:
        """Initialize the canvas.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.
            background: Initial fill color.
        """
        self.width = max(1, width)
        self.height = max(1, height)
        self._pixels = bytearray(self.width * self.height * 3)
        self.fill_rect(0, 0, self.width, self.height, background)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: Color) -> None:
        """Fill a rectangle.

        Args:
            x: Left pixel coordinate.
            y: Top pixel coordinate.
            width: Rectangle width.
            height: Rectangle height.
            color: RGB color.
        """
        left = max(0, x)
        top = max(0, y)
        right = min(self.width, x + max(0, width))
        bottom = min(self.height, y + max(0, height))
        if right <= left or bottom <= top:
            return
        r, g, b = color
        row_fragment = bytes((r, g, b)) * (right - left)
        for py in range(top, bottom):
            offset = (py * self.width + left) * 3
            self._pixels[offset:offset + len(row_fragment)] = row_fragment

    def blend_rect(self, x: int, y: int, width: int, height: int, color: Color, *, alpha: float) -> None:
        """Alpha-blend a rectangle over the canvas.

        Args:
            x: Left pixel coordinate.
            y: Top pixel coordinate.
            width: Rectangle width.
            height: Rectangle height.
            color: RGB color.
            alpha: Blend factor in ``[0, 1]``.
        """
        left = max(0, x)
        top = max(0, y)
        right = min(self.width, x + max(0, width))
        bottom = min(self.height, y + max(0, height))
        if right <= left or bottom <= top:
            return
        alpha = max(0.0, min(1.0, alpha))
        inv_alpha = 1.0 - alpha
        for py in range(top, bottom):
            for px in range(left, right):
                self._blend_pixel(px, py, color, alpha=alpha, inv_alpha=inv_alpha)

    def blend_ellipse(
        self,
        center_x: int,
        center_y: int,
        radius_x: int,
        radius_y: int,
        color: Color,
        *,
        alpha: float,
    ) -> None:
        """Alpha-blend a filled ellipse.

        Args:
            center_x: Center X pixel coordinate.
            center_y: Center Y pixel coordinate.
            radius_x: Horizontal radius.
            radius_y: Vertical radius.
            color: RGB color.
            alpha: Blend factor in ``[0, 1]``.
        """
        radius_x = max(1, radius_x)
        radius_y = max(1, radius_y)
        alpha = max(0.0, min(1.0, alpha))
        inv_alpha = 1.0 - alpha
        left = max(0, center_x - radius_x)
        right = min(self.width - 1, center_x + radius_x)
        top = max(0, center_y - radius_y)
        bottom = min(self.height - 1, center_y + radius_y)
        rx2 = radius_x * radius_x
        ry2 = radius_y * radius_y
        threshold = rx2 * ry2
        for py in range(top, bottom + 1):
            dy = py - center_y
            for px in range(left, right + 1):
                dx = px - center_x
                if dx * dx * ry2 + dy * dy * rx2 <= threshold:
                    self._blend_pixel(px, py, color, alpha=alpha, inv_alpha=inv_alpha)

    def to_png_bytes(self) -> bytes:
        """Encode the canvas as PNG bytes.

        Returns:
            PNG-encoded image data.
        """
        rows = bytearray()
        row_stride = self.width * 3
        for row_index in range(self.height):
            rows.append(0)
            start = row_index * row_stride
            rows.extend(self._pixels[start:start + row_stride])
        return b"".join(
            [
                b"\x89PNG\r\n\x1a\n",
                self._png_chunk(
                    b"IHDR",
                    struct.pack(
                        ">IIBBBBB",
                        self.width,
                        self.height,
                        8,
                        2,
                        0,
                        0,
                        0,
                    ),
                ),
                self._png_chunk(b"IDAT", zlib.compress(bytes(rows), level=6)),
                self._png_chunk(b"IEND", b""),
            ],
        )

    def _blend_pixel(
        self,
        x: int,
        y: int,
        color: Color,
        *,
        alpha: float,
        inv_alpha: float,
    ) -> None:
        """Blend one pixel.

        Args:
            x: Pixel X coordinate.
            y: Pixel Y coordinate.
            color: RGB color.
            alpha: Blend factor.
            inv_alpha: Inverted blend factor.
        """
        offset = (y * self.width + x) * 3
        r, g, b = color
        self._pixels[offset] = int(self._pixels[offset] * inv_alpha + r * alpha)
        self._pixels[offset + 1] = int(self._pixels[offset + 1] * inv_alpha + g * alpha)
        self._pixels[offset + 2] = int(self._pixels[offset + 2] * inv_alpha + b * alpha)

    def _png_chunk(self, chunk_type: bytes, data: bytes) -> bytes:
        """Build one PNG chunk.

        Args:
            chunk_type: Four-byte PNG chunk type.
            data: Chunk payload.

        Returns:
            PNG chunk bytes.
        """
        checksum = zlib.crc32(chunk_type)
        checksum = zlib.crc32(data, checksum) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
