"""Visual art layer export for prepared map rendering."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Any


Point = tuple[int, int]


@dataclass(frozen=True, slots=True)
class VisualArtLayerResult:
    """Visual art layer export result.

    Attributes:
        visual_art_layers: Renderable terrain/transition/decal layer artifact.
        visual_art_objects: Renderable runtime and dressing object artifact.
        visual_art_chunks: Chunk index for render streaming and preview tools.
        art_report: Compact export report for preparation tracking.
        art_summary: Human-readable export summary.
    """

    visual_art_layers: dict[str, Any]
    visual_art_objects: dict[str, Any]
    visual_art_chunks: dict[str, Any]
    art_report: dict[str, Any]
    art_summary: str


class VisualArtLayerBuilder:
    """Build deterministic render-layer JSON artifacts from normalizer output.

    The builder mirrors the pilot painter decisions as structured data. It does
    not change gameplay geometry; every element is visual-only unless it wraps an
    existing normalized runtime object.
    """

    COLLECTION_KEYS = ("items", "objects", "visual_objects")
    DEFAULT_TILE_SIZE_PX = 16
    DEFAULT_CHUNK_SIZE_TILES = 32
    FOREST_CONTEXTS = frozenset({"forest_inner", "forest_edge", "forest_outer_corner", "forest_single"})
    ROAD_CONTEXTS = frozenset({"road_straight", "road_turn", "road_junction", "road_dead_end", "road_isolated"})
    WATER_CONTEXTS = frozenset({"water_patch", "water_single"})
    RUIN_CONTEXTS = frozenset({"ruin_floor", "ruin_wall"})

    def build(
        self,
        *,
        visual_context: dict[str, Any],
        scene_dressing: dict[str, Any],
        dressed_visual_objects: dict[str, Any],
    ) -> VisualArtLayerResult:
        """Build prepared render-layer artifacts.

        Args:
            visual_context: Per-tile visual context artifact.
            scene_dressing: Generated scene dressing artifact.
            dressed_visual_objects: Normalized objects with dressing appended.

        Returns:
            Visual art layer result artifacts.
        """
        dimensions = self._dimensions(visual_context)
        rows = self._context_rows(visual_context)
        layers: list[dict[str, Any]] = []
        objects: list[dict[str, Any]] = []

        base_counts = self._add_base_terrain(layers=layers, rows=rows)
        forest_counts = self._add_forest_elements(layers=layers, rows=rows)
        road_counts = self._add_road_elements(layers=layers, rows=rows)
        water_counts = self._add_water_elements(layers=layers, rows=rows)
        ruin_counts = self._add_ruin_elements(layers=layers, rows=rows)
        object_counts = self._add_visual_objects(
            objects=objects,
            dressed_visual_objects=dressed_visual_objects,
            tile_size_px=dimensions["tile_size_px"],
        )
        dressing_counts = self._add_scene_dressing(
            objects=objects,
            scene_dressing=scene_dressing,
            tile_size_px=dimensions["tile_size_px"],
        )
        chunks = self._build_chunks(dimensions=dimensions, layers=layers, objects=objects)
        layer_counts = Counter(str(item.get("layer", "unknown")) for item in layers)
        object_layer_counts = Counter(str(item.get("layer", "unknown")) for item in objects)

        visual_art_layers = {
            "schema_version": "visual-art-layers-v1",
            "purpose": "Renderable visual terrain elements for prepared maps.",
            "contract": self._contract(),
            "dimensions": dimensions,
            "coordinate_system": self._coordinate_system(),
            "generation": {
                "deterministic": True,
                "source_artifacts": [
                    "visual_context.json",
                    "visual_scene_dressing.json",
                    "visual_objects_dressed.json",
                ],
            },
            "layers": layers,
        }
        visual_art_objects = {
            "schema_version": "visual-art-objects-v1",
            "purpose": "Renderable object and decal elements for prepared maps.",
            "contract": self._contract(),
            "dimensions": dimensions,
            "coordinate_system": self._coordinate_system(),
            "objects": objects,
        }
        visual_art_chunks = {
            "schema_version": "visual-art-chunks-v1",
            "purpose": "Chunk index over visual_art_layers and visual_art_objects.",
            "contract": self._contract(),
            "dimensions": dimensions,
            "chunk_size_tiles": self.DEFAULT_CHUNK_SIZE_TILES,
            "chunks": chunks,
        }
        report = self._build_report(
            dimensions=dimensions,
            layers=layers,
            objects=objects,
            chunks=chunks,
            layer_counts=dict(sorted(layer_counts.items())),
            object_layer_counts=dict(sorted(object_layer_counts.items())),
            base_counts=base_counts,
            forest_counts=forest_counts,
            road_counts=road_counts,
            water_counts=water_counts,
            ruin_counts=ruin_counts,
            object_counts=object_counts,
            dressing_counts=dressing_counts,
        )
        return VisualArtLayerResult(
            visual_art_layers=visual_art_layers,
            visual_art_objects=visual_art_objects,
            visual_art_chunks=visual_art_chunks,
            art_report=report,
            art_summary=self.format_summary(report),
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format a visual art layer report as readable text.

        Args:
            report: Visual art layer report dictionary.

        Returns:
            Human-readable summary.
        """
        counts = self._dict_value(report, "counts")
        dimensions = self._dict_value(report, "dimensions")
        return "\n".join(
            [
                "Visual art layers",
                f"- status: {report.get('status', 'unknown')}",
                (
                    "- size: "
                    f"{dimensions.get('width_tiles', 'unknown')}x"
                    f"{dimensions.get('height_tiles', 'unknown')} tiles"
                ),
                f"- art layer elements: {counts.get('layer_elements', 'unknown')}",
                f"- art object elements: {counts.get('object_elements', 'unknown')}",
                f"- chunks: {counts.get('chunks', 'unknown')}",
                f"- forest elements: {counts.get('forest_elements', 'unknown')}",
                f"- road elements: {counts.get('road_elements', 'unknown')}",
                f"- water elements: {counts.get('water_elements', 'unknown')}",
                f"- ruin elements: {counts.get('ruin_elements', 'unknown')}",
                f"- ruin rubble: {counts.get('ruin_rubble', 'unknown')}",
                f"- ruin moss: {counts.get('ruin_moss', 'unknown')}",
                f"- runtime objects: {counts.get('runtime_objects', 'unknown')}",
                f"- dressing objects: {counts.get('dressing_objects', 'unknown')}",
            ],
        )

    def _add_base_terrain(self, *, layers: list[dict[str, Any]], rows: list[list[dict[str, Any]]]) -> dict[str, int]:
        """Add base terrain elements.

        Args:
            layers: Mutable terrain element list.
            rows: Context rows.

        Returns:
            Counts by base family.
        """
        counts: Counter[str] = Counter()
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                primary = self._primary(cell)
                family = self._base_family(primary)
                counts[family] += 1
                layers.append(
                    self._tile_element(
                        element_id=f"base_{x:04d}_{y:04d}",
                        layer="base_ground",
                        family=family,
                        kind=primary,
                        x=x,
                        y=y,
                        variant=self._stable_mod("base", x, y, modulo=8),
                        alpha=1.0,
                    ),
                )
                if primary == "clearing" and self._stable_mod("grass-detail", x, y, modulo=7) == 0:
                    layers.append(
                        self._tile_element(
                            element_id=f"grass_detail_{x:04d}_{y:04d}",
                            layer="surface_decals",
                            family="grass_detail",
                            kind="grass_detail_patch",
                            x=x,
                            y=y,
                            variant=self._stable_mod("grass-detail-var", x, y, modulo=4),
                            alpha=0.20,
                        ),
                    )
        return dict(sorted(counts.items()))

    def _add_forest_elements(self, *, layers: list[dict[str, Any]], rows: list[list[dict[str, Any]]]) -> dict[str, int]:
        """Add painter-style forest mass elements.

        Args:
            layers: Mutable terrain element list.
            rows: Context rows.

        Returns:
            Forest element counters.
        """
        forest_mask = self._mask_for(rows, self.FOREST_CONTEXTS)
        depth_map = self._depth_map(forest_mask)
        forest_tiles = 0
        crown_stamps = 0
        shadows = 0
        for y, row in enumerate(forest_mask):
            for x, is_forest in enumerate(row):
                if is_forest:
                    forest_tiles += 1
                    depth = depth_map[y][x]
                    layers.append(
                        self._tile_element(
                            element_id=f"forest_mass_{x:04d}_{y:04d}",
                            layer="structures_and_blockers",
                            family="forest_region_mass",
                            kind="forest_mass_depth",
                            x=x,
                            y=y,
                            variant=self._stable_mod("forest-mass", x, y, modulo=8),
                            alpha=0.82,
                            extra={"depth": depth},
                        ),
                    )
                    if self._should_draw_forest_stamp(x=x, y=y, depth=depth):
                        crown_stamps += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"forest_crown_{x:04d}_{y:04d}",
                                layer="structures_and_blockers",
                                family="forest_canopy_stamp",
                                kind="forest_crown_hint",
                                x=x,
                                y=y,
                                variant=self._stable_mod("forest-crown", x, y, modulo=6),
                                alpha=0.28,
                                extra={"depth": depth},
                            ),
                        )
                    continue
                if self._touches_mask(forest_mask, x=x, y=y):
                    shadows += 1
                    layers.append(
                        self._tile_element(
                            element_id=f"forest_shadow_{x:04d}_{y:04d}",
                            layer="terrain_transitions",
                            family="forest_soft_shadow",
                            kind="forest_to_ground_shadow",
                            x=x,
                            y=y,
                            variant=self._stable_mod("forest-shadow", x, y, modulo=4),
                            alpha=0.10,
                        ),
                    )
        blob_count = 0
        regions = 0
        for region_index, cells in enumerate(self._connected_mask_regions(forest_mask)):
            if not cells:
                continue
            regions += 1
            budget = max(1, min(10, len(cells) // 18 + 1))
            phase = self._stable_mod("forest-region-phase", region_index, len(cells), modulo=max(1, len(cells)))
            for blob_index in range(budget):
                x, y = cells[(phase + blob_index * 17 + blob_index * blob_index) % len(cells)]
                blob_count += 1
                layers.append(
                    self._tile_element(
                        element_id=f"forest_blob_{region_index:03d}_{blob_index:03d}",
                        layer="structures_and_blockers",
                        family="forest_canopy_blob",
                        kind="region_scale_canopy_blob",
                        x=x,
                        y=y,
                        variant=self._stable_mod("forest-blob", x, y, modulo=8),
                        alpha=0.24,
                        extra={"region_index": region_index, "radius_tiles": 1 + (len(cells) > 24)},
                    ),
                )
        return {
            "forest_tiles": forest_tiles,
            "forest_stamps": crown_stamps,
            "forest_region_blobs": blob_count,
            "forest_regions_painted": regions,
            "forest_soft_shadows": shadows,
        }

    def _add_road_elements(self, *, layers: list[dict[str, Any]], rows: list[list[dict[str, Any]]]) -> dict[str, int]:
        """Add road painter elements.

        Args:
            layers: Mutable terrain element list.
            rows: Context rows.

        Returns:
            Road element counters.
        """
        road_mask = self._mask_for(rows, self.ROAD_CONTEXTS)
        road_tiles = 0
        shoulders = 0
        noise = 0
        intrusions = 0
        for y, row in enumerate(road_mask):
            for x, is_road in enumerate(row):
                if not is_road:
                    if self._touches_mask(road_mask, x=x, y=y) and self._stable_mod("road-ext-shoulder-skip", x, y, modulo=2) != 0:
                        shoulders += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"road_ext_shoulder_{x:04d}_{y:04d}",
                                layer="terrain_transitions",
                                family="road_soft_shoulder",
                                kind="external_dirt_wash",
                                x=x,
                                y=y,
                                variant=self._stable_mod("road-ext", x, y, modulo=4),
                                alpha=0.08,
                            ),
                        )
                    continue
                road_tiles += 1
                connections = self._mask_connections(road_mask, x=x, y=y)
                connection_count = sum(connections.values())
                layers.append(
                    self._tile_element(
                        element_id=f"road_body_{x:04d}_{y:04d}",
                        layer="base_ground",
                        family="road_painted_body",
                        kind="road_junction" if connection_count >= 3 else "road_core",
                        x=x,
                        y=y,
                        variant=self._stable_mod("road-body", x, y, modulo=6),
                        alpha=0.62 if connection_count < 3 else 0.70,
                        extra={"connections": connections},
                    ),
                )
                layers.append(
                    self._tile_element(
                        element_id=f"road_shoulder_{x:04d}_{y:04d}",
                        layer="terrain_transitions",
                        family="road_soft_shoulder",
                        kind="internal_dirt_shoulder",
                        x=x,
                        y=y,
                        variant=self._stable_mod("road-shoulder", x, y, modulo=4),
                        alpha=0.40 if connection_count < 3 else 0.48,
                        extra={"connections": connections},
                    ),
                )
                if self._stable_mod("road-noise-a", x, y, modulo=4) == 0:
                    noise += 1
                    layers.append(
                        self._tile_element(
                            element_id=f"road_noise_{x:04d}_{y:04d}",
                            layer="surface_decals",
                            family="road_dirt_noise",
                            kind="worn_dirt_patch",
                            x=x,
                            y=y,
                            variant=self._stable_mod("road-noise", x, y, modulo=5),
                            alpha=0.12,
                        ),
                    )
                if self._stable_mod("road-grass-skip", x, y, modulo=7) == 0:
                    intrusions += 1
                    layers.append(
                        self._tile_element(
                            element_id=f"road_grass_{x:04d}_{y:04d}",
                            layer="surface_decals",
                            family="road_grass_intrusion",
                            kind="grass_intrusion_patch",
                            x=x,
                            y=y,
                            variant=self._stable_mod("road-grass", x, y, modulo=4),
                            alpha=0.12,
                        ),
                    )
        return {
            "road_tiles": road_tiles,
            "road_external_shoulder_tiles": shoulders,
            "road_dirt_noise": noise,
            "road_grass_intrusions": intrusions,
        }

    def _add_water_elements(self, *, layers: list[dict[str, Any]], rows: list[list[dict[str, Any]]]) -> dict[str, int]:
        """Add water painter elements.

        Args:
            layers: Mutable terrain element list.
            rows: Context rows.

        Returns:
            Water element counters.
        """
        water_mask = self._mask_for(rows, self.WATER_CONTEXTS)
        water_tiles = 0
        bank_tiles = 0
        reeds = 0
        region_bodies = 0
        for region_index, cells in enumerate(self._connected_mask_regions(water_mask)):
            if not cells:
                continue
            budget = max(1, min(4, len(cells) // 10 + 1))
            phase = self._stable_mod("water-region-phase", region_index, len(cells), modulo=max(1, len(cells)))
            for body_index in range(budget):
                x, y = cells[(phase + body_index * 11 + body_index * body_index) % len(cells)]
                region_bodies += 1
                layers.append(
                    self._tile_element(
                        element_id=f"water_region_body_{region_index:03d}_{body_index:03d}",
                        layer="base_ground",
                        family="water_region_body",
                        kind="calm_puddle_body",
                        x=x,
                        y=y,
                        variant=self._stable_mod("water-body", x, y, modulo=5),
                        alpha=0.24,
                        extra={"region_index": region_index},
                    ),
                )
        for y, row in enumerate(water_mask):
            for x, is_water in enumerate(row):
                primary = self._primary(rows[y][x])
                if is_water:
                    water_tiles += 1
                    connections = self._mask_connections(water_mask, x=x, y=y)
                    layers.append(
                        self._tile_element(
                            element_id=f"water_tile_{x:04d}_{y:04d}",
                            layer="base_ground",
                            family="water_puddle_body",
                            kind="water_connected" if sum(connections.values()) else "water_single",
                            x=x,
                            y=y,
                            variant=self._stable_mod("water-tile", x, y, modulo=6),
                            alpha=0.54 if sum(connections.values()) else 0.44,
                            extra={"connections": connections},
                        ),
                    )
                    if self._touches_outside(water_mask, x=x, y=y) and self._stable_mod("water-reeds-skip", x, y, modulo=17) == 0:
                        reeds += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"water_reeds_in_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="reed_cluster",
                                kind="sparse_inner_reeds",
                                x=x,
                                y=y,
                                variant=self._stable_mod("water-reeds", x, y, modulo=4),
                                alpha=0.58,
                            ),
                        )
                    continue
                if self._touches_mask(water_mask, x=x, y=y) and self._allows_water_bank(primary):
                    bank_tiles += 1
                    layers.append(
                        self._tile_element(
                            element_id=f"water_bank_{x:04d}_{y:04d}",
                            layer="terrain_transitions",
                            family="muddy_water_bank",
                            kind="wet_mud_bank",
                            x=x,
                            y=y,
                            variant=self._stable_mod("water-bank", x, y, modulo=5),
                            alpha=0.22,
                        ),
                    )
                    if self._stable_mod("water-reeds-skip", x, y, modulo=4) == 0:
                        reeds += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"water_reeds_bank_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="reed_cluster",
                                kind="bank_reeds",
                                x=x,
                                y=y,
                                variant=self._stable_mod("water-reeds", x, y, modulo=4),
                                alpha=0.58,
                            ),
                        )
        return {
            "water_tiles": water_tiles,
            "water_bank_tiles": bank_tiles,
            "water_reeds": reeds,
            "water_region_bodies": region_bodies,
        }

    def _add_ruin_elements(self, *, layers: list[dict[str, Any]], rows: list[list[dict[str, Any]]]) -> dict[str, int]:
        """Add ruin painter elements for broken stone sites.

        Args:
            layers: Mutable terrain element list.
            rows: Context rows.

        Returns:
            Ruin element counters.
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

        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                primary = self._primary(cell)
                if primary == "ruin_floor":
                    floor_tiles += 1
                    near_wall = self._touches_mask(wall_mask, x=x, y=y)
                    layers.append(
                        self._tile_element(
                            element_id=f"ruin_floor_{x:04d}_{y:04d}",
                            layer="base_ground",
                            family="ruin_floor",
                            kind="broken_stone_floor",
                            x=x,
                            y=y,
                            variant=self._stable_mod("ruin-floor", x, y, modulo=6),
                            alpha=1.0,
                            extra={"near_wall": near_wall},
                        ),
                    )
                    if self._stable_mod("ruin-floor-crack", x, y, modulo=3) == 0:
                        cracks += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"ruin_floor_crack_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="ruin_floor_crack",
                                kind="floor_crack",
                                x=x,
                                y=y,
                                variant=self._stable_mod("ruin-crack-var", x, y, modulo=4),
                                alpha=0.34,
                            ),
                        )
                    if near_wall and self._stable_mod("ruin-floor-moss", x, y, modulo=3) == 0:
                        moss += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"ruin_floor_moss_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="ruin_moss_patch",
                                kind="moss_near_wall",
                                x=x,
                                y=y,
                                variant=self._stable_mod("ruin-moss", x, y, modulo=5),
                                alpha=0.30,
                            ),
                        )
                    if self._stable_mod("ruin-floor-dirt", x, y, modulo=5) == 0:
                        dirt += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"ruin_floor_dirt_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="ruin_dirt_patch",
                                kind="dirty_stone_floor",
                                x=x,
                                y=y,
                                variant=self._stable_mod("ruin-dirt", x, y, modulo=4),
                                alpha=0.22,
                            ),
                        )
                    continue

                if primary == "ruin_wall":
                    wall_tiles += 1
                    connections = self._mask_connections(wall_mask, x=x, y=y)
                    layers.append(
                        self._tile_element(
                            element_id=f"ruin_wall_{x:04d}_{y:04d}",
                            layer="structures_and_blockers",
                            family="ruin_wall_mass",
                            kind="broken_wall_mass",
                            x=x,
                            y=y,
                            variant=self._stable_mod("ruin-wall", x, y, modulo=6),
                            alpha=1.0,
                            extra={"connections": connections},
                        ),
                    )
                    shadow_marks = self._ruin_wall_shadow_count(connections)
                    wall_shadows += shadow_marks
                    if shadow_marks:
                        layers.append(
                            self._tile_element(
                                element_id=f"ruin_wall_shadow_{x:04d}_{y:04d}",
                                layer="terrain_transitions",
                                family="ruin_wall_shadow",
                                kind="wall_base_shadow",
                                x=x,
                                y=y,
                                variant=self._stable_mod("ruin-shadow", x, y, modulo=4),
                                alpha=0.30,
                                extra={"connections": connections, "shadow_marks": shadow_marks},
                            ),
                        )
                    if self._stable_mod("ruin-wall-broken", x, y, modulo=3) == 0:
                        broken_hints += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"ruin_wall_broken_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="ruin_broken_wall_hint",
                                kind="broken_wall_gap",
                                x=x,
                                y=y,
                                variant=self._stable_mod("ruin-break", x, y, modulo=4),
                                alpha=0.28,
                            ),
                        )
                    if self._stable_mod("ruin-wall-rubble", x, y, modulo=2) == 0:
                        rubble += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"ruin_wall_rubble_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="ruin_rubble_cluster",
                                kind="wall_rubble",
                                x=x,
                                y=y,
                                variant=self._stable_mod("ruin-rubble", x, y, modulo=6),
                                alpha=0.42,
                            ),
                        )
                    continue

                if self._touches_mask(ruin_mask, x=x, y=y) and self._allows_ruin_debris(primary):
                    if self._stable_mod("ruin-adjacent-rubble", x, y, modulo=3) == 0:
                        rubble += 1
                        debris_clusters += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"ruin_adjacent_rubble_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="ruin_rubble_cluster",
                                kind="adjacent_stone_debris",
                                x=x,
                                y=y,
                                variant=self._stable_mod("ruin-adj-rubble", x, y, modulo=6),
                                alpha=0.34,
                            ),
                        )
                    if self._stable_mod("ruin-adjacent-moss", x, y, modulo=5) == 0:
                        moss += 1
                        layers.append(
                            self._tile_element(
                                element_id=f"ruin_adjacent_moss_{x:04d}_{y:04d}",
                                layer="surface_decals",
                                family="ruin_moss_patch",
                                kind="adjacent_moss",
                                x=x,
                                y=y,
                                variant=self._stable_mod("ruin-adj-moss", x, y, modulo=5),
                                alpha=0.26,
                            ),
                        )

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

    def _ruin_wall_shadow_count(self, connections: dict[str, bool]) -> int:
        """Return approximate shadow marks for wall gaps.

        Args:
            connections: Cardinal wall connections.

        Returns:
            Count of visual wall-base shadow marks.
        """
        marks = 0
        if not connections.get("S", False):
            marks += 1
        if not connections.get("E", False):
            marks += 1
        return marks

    def _allows_ruin_debris(self, primary: str) -> bool:
        """Return whether adjacent terrain may receive visual-only ruin debris.

        Args:
            primary: Primary visual context.

        Returns:
            True when debris may be placed without implying a blocker.
        """
        return primary in {"clearing", "ruin_floor", "blocked_structure"}

    def _add_visual_objects(
        self,
        *,
        objects: list[dict[str, Any]],
        dressed_visual_objects: dict[str, Any],
        tile_size_px: int,
    ) -> dict[str, Any]:
        """Add normalized runtime objects to visual art objects.

        Args:
            objects: Mutable object element list.
            dressed_visual_objects: Normalized objects with dressing appended.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Object counters.
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
            x, y = position
            family = self._object_family(item)
            by_family[family] += 1
            rendered += 1
            objects.append(
                {
                    "id": str(item.get("id") or f"runtime_object_{rendered:05d}"),
                    "source": "runtime_object",
                    "layer": "runtime_objects",
                    "family": family,
                    "kind": "large_object" if self._large_family(family) else "runtime_object",
                    "tile": {"x": x, "y": y},
                    "position_px": {"x": x * tile_size_px, "y": y * tile_size_px},
                    "variant": self._stable_mod(f"object:{family}", x, y, modulo=8),
                    "visual_only": False,
                    "changes_gameplay": False,
                    "source_object_id": item.get("source_object_id"),
                    "source_object_type": item.get("source_object_type"),
                    "visual_size_px": item.get("visual_size_px"),
                    "footprint_tiles": item.get("footprint_tiles"),
                },
            )
        return {
            "runtime_objects": rendered,
            "skipped_without_position": skipped,
            "counts_by_family": dict(sorted(by_family.items())),
        }

    def _add_scene_dressing(
        self,
        *,
        objects: list[dict[str, Any]],
        scene_dressing: dict[str, Any],
        tile_size_px: int,
    ) -> dict[str, Any]:
        """Add scene dressing objects to visual art objects.

        Args:
            objects: Mutable object element list.
            scene_dressing: Scene dressing artifact.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Dressing counters.
        """
        rendered = 0
        skipped = 0
        by_category: Counter[str] = Counter()
        by_family: Counter[str] = Counter()
        for item in self._dressing_items(scene_dressing):
            if not isinstance(item, dict):
                skipped += 1
                continue
            position = self._object_tile_position(item, tile_size_px=tile_size_px)
            if position is None:
                skipped += 1
                continue
            x, y = position
            category = self._string_value(item.get("category"), default="small_decals")
            family = self._string_value(item.get("family"), default="scene_dressing")
            by_category[category] += 1
            by_family[family] += 1
            rendered += 1
            objects.append(
                {
                    "id": str(item.get("id") or f"scene_dressing_{rendered:05d}"),
                    "source": "scene_dressing",
                    "layer": "surface_decals" if category == "small_decals" else "runtime_objects",
                    "family": family,
                    "kind": category,
                    "tile": {"x": x, "y": y},
                    "position_px": {"x": x * tile_size_px, "y": y * tile_size_px},
                    "variant": self._stable_mod(f"dressing:{family}:{category}", x, y, modulo=8),
                    "visual_only": True,
                    "changes_gameplay": False,
                    "scene_id": item.get("scene_id"),
                    "preset": item.get("preset"),
                },
            )
        return {
            "dressing_objects": rendered,
            "skipped_without_position": skipped,
            "counts_by_category": dict(sorted(by_category.items())),
            "counts_by_family": dict(sorted(by_family.items())),
        }

    def _build_chunks(
        self,
        *,
        dimensions: dict[str, int],
        layers: list[dict[str, Any]],
        objects: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Build chunk index entries for visual elements.

        Args:
            dimensions: Map dimensions.
            layers: Layer elements.
            objects: Object elements.

        Returns:
            Chunk index entries.
        """
        width = dimensions["width_tiles"]
        height = dimensions["height_tiles"]
        chunk_size = self.DEFAULT_CHUNK_SIZE_TILES
        chunks_x = (width + chunk_size - 1) // chunk_size
        chunks_y = (height + chunk_size - 1) // chunk_size
        layer_counts: dict[tuple[int, int], int] = Counter()
        object_counts: dict[tuple[int, int], int] = Counter()
        for item in layers:
            tile = self._dict_value(item, "tile")
            chunk = (self._int_value(tile.get("x"), default=0) // chunk_size, self._int_value(tile.get("y"), default=0) // chunk_size)
            layer_counts[chunk] += 1
        for item in objects:
            tile = self._dict_value(item, "tile")
            chunk = (self._int_value(tile.get("x"), default=0) // chunk_size, self._int_value(tile.get("y"), default=0) // chunk_size)
            object_counts[chunk] += 1

        chunks: list[dict[str, Any]] = []
        for chunk_y in range(chunks_y):
            for chunk_x in range(chunks_x):
                x0 = chunk_x * chunk_size
                y0 = chunk_y * chunk_size
                chunks.append(
                    {
                        "id": f"chunk_{chunk_x:03d}_{chunk_y:03d}",
                        "x": chunk_x,
                        "y": chunk_y,
                        "bounds_tiles": {
                            "x": x0,
                            "y": y0,
                            "w": min(chunk_size, max(0, width - x0)),
                            "h": min(chunk_size, max(0, height - y0)),
                        },
                        "layer_elements": layer_counts[(chunk_x, chunk_y)],
                        "object_elements": object_counts[(chunk_x, chunk_y)],
                    },
                )
        return chunks

    def _build_report(
        self,
        *,
        dimensions: dict[str, int],
        layers: list[dict[str, Any]],
        objects: list[dict[str, Any]],
        chunks: list[dict[str, Any]],
        layer_counts: dict[str, int],
        object_layer_counts: dict[str, int],
        base_counts: dict[str, int],
        forest_counts: dict[str, int],
        road_counts: dict[str, int],
        water_counts: dict[str, int],
        ruin_counts: dict[str, int],
        object_counts: dict[str, Any],
        dressing_counts: dict[str, Any],
    ) -> dict[str, Any]:
        """Build visual art layer export report.

        Args:
            dimensions: Map dimensions.
            layers: Layer elements.
            objects: Object elements.
            chunks: Chunk entries.
            layer_counts: Counts by layer name.
            object_layer_counts: Object counts by layer name.
            base_counts: Base terrain counters.
            forest_counts: Forest counters.
            road_counts: Road counters.
            water_counts: Water counters.
            ruin_counts: Ruin counters.
            object_counts: Runtime object counters.
            dressing_counts: Dressing object counters.

        Returns:
            Report dictionary.
        """
        return {
            "schema_version": "visual-art-layers-report-v1",
            "status": "ok",
            "contract": self._contract(),
            "dimensions": dimensions,
            "counts": {
                "layer_elements": len(layers),
                "object_elements": len(objects),
                "chunks": len(chunks),
                "forest_elements": sum(forest_counts.values()),
                "road_elements": sum(road_counts.values()),
                "water_elements": sum(water_counts.values()),
                "ruin_elements": sum(ruin_counts.values()),
                "ruin_rubble": self._int_value(ruin_counts.get("ruin_rubble"), default=0),
                "ruin_moss": self._int_value(ruin_counts.get("ruin_moss"), default=0),
                "ruin_wall_shadows": self._int_value(ruin_counts.get("ruin_wall_shadows"), default=0),
                "runtime_objects": self._int_value(object_counts.get("runtime_objects"), default=0),
                "dressing_objects": self._int_value(dressing_counts.get("dressing_objects"), default=0),
            },
            "layer_counts": layer_counts,
            "object_layer_counts": object_layer_counts,
            "base_counts": base_counts,
            "forest": forest_counts,
            "road": road_counts,
            "water": water_counts,
            "ruins": ruin_counts,
            "runtime_objects": object_counts,
            "scene_dressing": dressing_counts,
        }

    def _tile_element(
        self,
        *,
        element_id: str,
        layer: str,
        family: str,
        kind: str,
        x: int,
        y: int,
        variant: int,
        alpha: float,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build one tile-anchored render element.

        Args:
            element_id: Stable element id.
            layer: Render layer name.
            family: Asset or procedural family.
            kind: Specific visual kind.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            variant: Deterministic variant index.
            alpha: Suggested render alpha.
            extra: Additional serializable metadata.

        Returns:
            Render element dictionary.
        """
        element: dict[str, Any] = {
            "id": element_id,
            "layer": layer,
            "family": family,
            "kind": kind,
            "tile": {"x": x, "y": y},
            "variant": variant,
            "alpha": round(alpha, 3),
            "visual_only": True,
            "changes_gameplay": False,
        }
        if extra:
            element.update(extra)
        return element

    def _base_family(self, primary: str) -> str:
        """Map primary context to base visual family.

        Args:
            primary: Primary visual context.

        Returns:
            Base family name.
        """
        if primary in self.FOREST_CONTEXTS:
            return "forest_base"
        if primary in self.ROAD_CONTEXTS:
            return "road_base"
        if primary in self.WATER_CONTEXTS:
            return "water_base"
        if primary == "ruin_wall":
            return "ruin_wall"
        if primary == "ruin_floor":
            return "ruin_floor"
        if primary == "blocked_structure":
            return "blocked_structure"
        return "grass_base"

    def _dimensions(self, visual_context: dict[str, Any]) -> dict[str, int]:
        """Read visual context dimensions.

        Args:
            visual_context: Per-tile context artifact.

        Returns:
            Normalized dimensions dictionary.
        """
        raw_dimensions = self._dict_value(visual_context, "dimensions")
        rows = visual_context.get("rows")
        row_count = len(rows) if isinstance(rows, list) else 0
        first_row = rows[0] if row_count and isinstance(rows[0], list) else []
        return {
            "width_tiles": max(1, self._int_value(raw_dimensions.get("width_tiles"), default=len(first_row))),
            "height_tiles": max(1, self._int_value(raw_dimensions.get("height_tiles"), default=row_count)),
            "tile_size_px": max(1, self._int_value(raw_dimensions.get("tile_size_px"), default=self.DEFAULT_TILE_SIZE_PX)),
        }

    def _context_rows(self, visual_context: dict[str, Any]) -> list[list[dict[str, Any]]]:
        """Return normalized context rows.

        Args:
            visual_context: Per-tile context artifact.

        Returns:
            Context row list.
        """
        raw_rows = visual_context.get("rows")
        if not isinstance(raw_rows, list):
            return []
        rows: list[list[dict[str, Any]]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, list):
                continue
            row: list[dict[str, Any]] = []
            for cell in raw_row:
                row.append(cell if isinstance(cell, dict) else {"primary": "unknown"})
            rows.append(row)
        return rows

    def _primary(self, cell: dict[str, Any]) -> str:
        """Return a cell primary context.

        Args:
            cell: Context cell.

        Returns:
            Primary context string.
        """
        return self._string_value(cell.get("primary"), default="unknown")

    def _mask_for(self, rows: list[list[dict[str, Any]]], contexts: frozenset[str]) -> list[list[bool]]:
        """Build a boolean mask for primary contexts.

        Args:
            rows: Context rows.
            contexts: Accepted primary context names.

        Returns:
            Boolean mask.
        """
        return [[self._primary(cell) in contexts for cell in row] for row in rows]

    def _depth_map(self, mask: list[list[bool]]) -> list[list[int]]:
        """Build distance-to-outside depth map for a boolean region mask.

        Args:
            mask: Boolean region mask.

        Returns:
            Depth map.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        depth = [[0 for _ in range(width)] for _ in range(height)]
        queue: deque[Point] = deque()
        for y in range(height):
            for x in range(width):
                if not mask[y][x]:
                    continue
                if self._touches_outside(mask, x=x, y=y):
                    depth[y][x] = 1
                    queue.append((x, y))
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
                if ny < 0 or ny >= height or nx < 0 or nx >= width:
                    continue
                if not mask[ny][nx] or depth[ny][nx] != 0:
                    continue
                depth[ny][nx] = depth[y][x] + 1
                queue.append((nx, ny))
        return depth

    def _connected_mask_regions(self, mask: list[list[bool]]) -> list[list[Point]]:
        """Return 4-connected true-cell regions from a mask.

        Args:
            mask: Boolean mask.

        Returns:
            Connected regions.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        visited: set[Point] = set()
        regions: list[list[Point]] = []
        for y in range(height):
            for x in range(width):
                if not mask[y][x] or (x, y) in visited:
                    continue
                region: list[Point] = []
                queue: deque[Point] = deque([(x, y)])
                visited.add((x, y))
                while queue:
                    cx, cy = queue.popleft()
                    region.append((cx, cy))
                    for nx, ny in ((cx, cy - 1), (cx + 1, cy), (cx, cy + 1), (cx - 1, cy)):
                        if ny < 0 or ny >= height or nx < 0 or nx >= width:
                            continue
                        if not mask[ny][nx] or (nx, ny) in visited:
                            continue
                        visited.add((nx, ny))
                        queue.append((nx, ny))
                regions.append(region)
        return regions

    def _mask_connections(self, mask: list[list[bool]], *, x: int, y: int) -> dict[str, bool]:
        """Return cardinal mask connections for a tile.

        Args:
            mask: Boolean mask.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            Dictionary with N/E/S/W connection flags.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        return {
            "N": y > 0 and mask[y - 1][x],
            "E": x + 1 < width and mask[y][x + 1],
            "S": y + 1 < height and mask[y + 1][x],
            "W": x > 0 and mask[y][x - 1],
        }

    def _touches_mask(self, mask: list[list[bool]], *, x: int, y: int) -> bool:
        """Return whether a non-mask tile touches a true mask tile.

        Args:
            mask: Boolean mask.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            True if any 8-neighbor is true.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if 0 <= nx < width and 0 <= ny < height and mask[ny][nx]:
                    return True
        return False

    def _touches_outside(self, mask: list[list[bool]], *, x: int, y: int) -> bool:
        """Return whether a true mask tile touches outside the mask.

        Args:
            mask: Boolean mask.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            True if any cardinal neighbor is false/out-of-bounds.
        """
        height = len(mask)
        width = len(mask[0]) if mask else 0
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if ny < 0 or ny >= height or nx < 0 or nx >= width or not mask[ny][nx]:
                return True
        return False

    def _allows_water_bank(self, primary: str) -> bool:
        """Return whether a tile can receive visual-only water-bank treatment.

        Args:
            primary: Primary context.

        Returns:
            True when a muddy bank can be drawn on the tile.
        """
        return primary not in self.FOREST_CONTEXTS and primary not in self.RUIN_CONTEXTS and primary not in {"ruin_wall", "blocked_structure"}

    def _should_draw_forest_stamp(self, *, x: int, y: int, depth: int) -> bool:
        """Return whether a forest tile should receive an internal crown stamp.

        Args:
            x: Tile X coordinate.
            y: Tile Y coordinate.
            depth: Forest depth value.

        Returns:
            True when a crown stamp should be exported.
        """
        if depth >= 3:
            return self._stable_mod("forest-stamp-deep", x, y, modulo=5) == 0
        return self._stable_mod("forest-stamp-edge", x, y, modulo=9) == 0

    def _object_items(self, data: dict[str, Any]) -> list[Any]:
        """Extract common visual object collection items.

        Args:
            data: Visual objects artifact.

        Returns:
            Object list.
        """
        for key in self.COLLECTION_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return list(value.values())
        return []

    def _dressing_items(self, scene_dressing: dict[str, Any]) -> list[Any]:
        """Extract dressing object items.

        Args:
            scene_dressing: Scene dressing artifact.

        Returns:
            Dressing object list.
        """
        objects = scene_dressing.get("objects")
        if isinstance(objects, list):
            return objects
        scenes = scene_dressing.get("scenes")
        if isinstance(scenes, list):
            result: list[Any] = []
            for scene in scenes:
                if not isinstance(scene, dict):
                    continue
                scene_objects = scene.get("objects")
                if isinstance(scene_objects, list):
                    result.extend(scene_objects)
            return result
        return []

    def _object_family(self, item: dict[str, Any]) -> str:
        """Extract an object family name.

        Args:
            item: Visual object item.

        Returns:
            Family name.
        """
        for key in ("resolved_asset_family", "asset_family", "family", "visual_family", "type"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value.removeprefix("object.")
        return "object"

    def _object_tile_position(self, item: dict[str, Any], *, tile_size_px: int) -> tuple[int, int] | None:
        """Extract an object tile coordinate.

        Args:
            item: Visual object item.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Tile coordinate, or None when not available.
        """
        for key in ("tile", "position", "anchor_tile"):
            raw = item.get(key)
            if isinstance(raw, dict):
                x = raw.get("x")
                y = raw.get("y")
                if isinstance(x, int) and isinstance(y, int):
                    return x, y
        x = item.get("x")
        y = item.get("y")
        if isinstance(x, int) and isinstance(y, int):
            return x, y
        position_px = item.get("position_px")
        if isinstance(position_px, dict):
            px = position_px.get("x")
            py = position_px.get("y")
            if isinstance(px, int) and isinstance(py, int):
                return px // tile_size_px, py // tile_size_px
        return None

    def _large_family(self, family: str) -> bool:
        """Return whether a family should be treated as a large object.

        Args:
            family: Object family.

        Returns:
            True for large visual object families.
        """
        return family in {
            "abandoned_cart",
            "big_dead_tree",
            "broken_generator",
            "broken_radio_mast",
            "car_wreck",
            "earth_berm",
            "fallen_log",
            "field_tent",
            "old_checkpoint",
            "trench",
        }

    def _coordinate_system(self) -> dict[str, str]:
        """Return shared visual coordinate system metadata.

        Returns:
            Coordinate system dictionary.
        """
        return {
            "origin": "top_left",
            "x_axis": "right",
            "y_axis": "down",
            "tile_anchor_px": "top_left",
        }

    def _contract(self) -> dict[str, bool]:
        """Return gameplay safety contract for generated visual art layers.

        Returns:
            Contract flags.
        """
        return {
            "changes_gameplay": False,
            "changes_collision": False,
            "moves_markers": False,
            "creates_runtime_objects": False,
        }

    def _stable_mod(self, salt: str, x: int, y: int, *, modulo: int) -> int:
        """Return a deterministic small integer for coordinates.

        Args:
            salt: Hash salt.
            x: First coordinate/value.
            y: Second coordinate/value.
            modulo: Modulo divisor.

        Returns:
            Deterministic integer in [0, modulo).
        """
        if modulo <= 0:
            return 0
        value = 1469598103934665603
        for part in (salt, str(x), str(y)):
            for byte in part.encode("utf-8"):
                value ^= byte
                value *= 1099511628211
                value &= 0xFFFFFFFFFFFFFFFF
        return value % modulo

    def _dict_value(self, value: Any, key: str | None = None) -> dict[str, Any]:
        """Return a dictionary value.

        Args:
            value: Raw value or parent dictionary.
            key: Optional key to read from parent.

        Returns:
            Dictionary value or an empty dictionary.
        """
        if key is not None:
            value = value.get(key) if isinstance(value, dict) else None
        return value if isinstance(value, dict) else {}

    def _string_value(self, value: Any, *, default: str) -> str:
        """Return a string value.

        Args:
            value: Raw value.
            default: Fallback string.

        Returns:
            String value.
        """
        return value if isinstance(value, str) and value else default

    def _int_value(self, value: Any, *, default: int) -> int:
        """Return an integer value.

        Args:
            value: Raw value.
            default: Fallback integer.

        Returns:
            Integer value.
        """
        return value if isinstance(value, int) else default

    def _bool_value(self, value: Any, *, default: bool) -> bool:
        """Return a boolean value.

        Args:
            value: Raw value.
            default: Fallback boolean.

        Returns:
            Boolean value.
        """
        return value if isinstance(value, bool) else default
