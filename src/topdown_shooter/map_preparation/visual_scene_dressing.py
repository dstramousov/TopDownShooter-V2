"""Visual scene dressing generation for prepared map baking."""

from __future__ import annotations

import hashlib
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VisualSceneDressingResult:
    """Visual scene dressing generation output.

    Attributes:
        scene_dressing: Per-scene generated dressing artifact.
        dressed_visual_objects: Normalized visual objects with visual-only dressing appended.
        dressing_report: Compact dressing report for preparation and quality tracking.
        dressing_summary: Human-readable dressing summary.
    """

    scene_dressing: dict[str, Any]
    dressed_visual_objects: dict[str, Any]
    dressing_report: dict[str, Any]
    dressing_summary: str


class VisualSceneDressingGenerator:
    """Generate deterministic visual-only dressing objects for assigned scenes."""

    COLLECTION_KEYS = ("items", "objects", "visual_objects")
    DEFAULT_TILE_SIZE_PX = 16
    DRESSING_RULES: dict[str, dict[str, list[str]]] = {
        "forest_clearing_light": {
            "large_props": [],
            "medium_props": [
                "small_stones",
                "fallen_branch",
                "grass_clump",
                "bush_patch",
            ],
            "small_decals": [
                "grass_wear",
                "leaf_noise",
                "small_stones",
            ],
        },
        "road_junction_forest_ruins": {
            "large_props": [],
            "medium_props": [
                "roadside_stones",
                "broken_plank",
                "scrap_pile_small",
            ],
            "small_decals": [
                "road_wear",
                "grass_intrusion",
                "roadside_stones",
            ],
        },
        "small_ruin_site": {
            "large_props": ["rubble_large"],
            "medium_props": [
                "rubble_small",
                "stone_debris",
                "moss_patch",
                "broken_plank",
            ],
            "small_decals": [
                "rubble",
                "moss",
                "cracks",
                "wall_shadow",
            ],
        },
        "water_lowland_mud": {
            "large_props": [],
            "medium_props": [
                "reeds_patch",
                "wet_grass_clump",
                "mud_stones",
            ],
            "small_decals": [
                "mud",
                "wet_grass",
                "reeds",
                "small_stones",
            ],
        },
    }

    def generate(
        self,
        *,
        scene_presets: dict[str, Any],
        visual_context: dict[str, Any],
        normalized_visual_objects: dict[str, Any],
    ) -> VisualSceneDressingResult:
        """Generate visual-only scene dressing objects.

        Args:
            scene_presets: Scene preset artifact from ``VisualScenePresetAssigner``.
            visual_context: Per-tile visual context artifact from ``VisualContextAnalyzer``.
            normalized_visual_objects: Normalized visual objects artifact.

        Returns:
            Dressing result with generated objects, combined visual objects, and reports.
        """
        scenes = self._scene_items(scene_presets)
        context_rows = self._context_rows(visual_context)
        tile_size_px = self._tile_size_px(visual_context)
        generated_scenes: list[dict[str, Any]] = []
        all_dressing_objects: list[dict[str, Any]] = []

        for scene in scenes:
            generated_scene = self._generate_scene(
                scene=scene,
                context_rows=context_rows,
                tile_size_px=tile_size_px,
            )
            generated_scenes.append(generated_scene)
            all_dressing_objects.extend(generated_scene["objects"])

        scene_dressing = self._build_scene_dressing_artifact(
            scene_presets=scene_presets,
            generated_scenes=generated_scenes,
            dressing_objects=all_dressing_objects,
        )
        dressed_visual_objects = self._build_dressed_visual_objects(
            normalized_visual_objects=normalized_visual_objects,
            dressing_objects=all_dressing_objects,
        )
        report = self._build_report(scene_dressing)
        return VisualSceneDressingResult(
            scene_dressing=scene_dressing,
            dressed_visual_objects=dressed_visual_objects,
            dressing_report=report,
            dressing_summary=self.format_summary(report),
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format visual scene dressing as readable text.

        Args:
            report: Dressing report dictionary.

        Returns:
            Human-readable summary.
        """
        coverage = self._dict_value(report, "dressing_coverage")
        family_counts = self._dict_value(coverage, "object_counts_by_family")
        top_families = ", ".join(
            f"{family}:{count}"
            for family, count in list(family_counts.items())[:8]
        )
        if not top_families:
            top_families = "none"
        return "\n".join(
            [
                "Visual scene dressing",
                f"- status: {report.get('status', 'unknown')}",
                f"- assigned scenes: {coverage.get('assigned_scenes', 'unknown')}",
                f"- dressed scenes: {coverage.get('dressed_scenes', 'unknown')}",
                f"- generated objects: {coverage.get('generated_objects', 'unknown')}",
                f"- scenes without dressing: {coverage.get('scenes_without_dressing', 'unknown')}",
                f"- top families: {top_families}",
            ],
        )

    def _generate_scene(
        self,
        *,
        scene: dict[str, Any],
        context_rows: list[list[dict[str, Any]]],
        tile_size_px: int,
    ) -> dict[str, Any]:
        """Generate deterministic dressing for one assigned scene.

        Args:
            scene: Scene preset assignment entry.
            context_rows: Per-tile context rows.
            tile_size_px: Tile size in pixels.

        Returns:
            Generated scene dressing entry.
        """
        scene_id = self._string_value(scene.get("id"), default="scene_unknown")
        preset_id = self._string_value(scene.get("preset_id"), default="generic_scene")
        assignment_status = self._string_value(
            scene.get("assignment_status"),
            default="missing_preset",
        )
        if assignment_status != "assigned":
            return self._empty_scene(scene, reason="missing_preset")

        budget = self._dict_value(scene, "dressing_budget")
        rules = self.DRESSING_RULES.get(preset_id, {})
        occupied_tiles: set[tuple[int, int]] = set()
        objects: list[dict[str, Any]] = []
        placement_failures: list[dict[str, Any]] = []

        for category in ("large_props", "medium_props", "small_decals"):
            requested_count = self._int_value(budget.get(category), default=0)
            if requested_count <= 0:
                continue
            families = self._string_list(rules.get(category))
            if not families:
                placement_failures.append(
                    {
                        "category": category,
                        "reason": "missing_dressing_rule",
                        "requested_count": requested_count,
                    },
                )
                continue
            candidates = self._candidate_tiles_for_scene(
                scene=scene,
                preset_id=preset_id,
                category=category,
                context_rows=context_rows,
                occupied_tiles=occupied_tiles,
            )
            if not candidates:
                placement_failures.append(
                    {
                        "category": category,
                        "reason": "no_valid_tiles",
                        "requested_count": requested_count,
                    },
                )
                continue
            ordered_candidates = self._stable_ordered_tiles(
                candidates,
                salt=f"{scene_id}:{preset_id}:{category}",
            )
            generated_count = min(requested_count, len(ordered_candidates))
            if generated_count < requested_count:
                placement_failures.append(
                    {
                        "category": category,
                        "reason": "not_enough_valid_tiles",
                        "requested_count": requested_count,
                        "generated_count": generated_count,
                    },
                )
            for local_index, tile in enumerate(ordered_candidates[:generated_count]):
                family = families[
                    self._stable_int(f"{scene_id}:{category}:{local_index}") % len(families)
                ]
                occupied_tiles.add(tile)
                objects.append(
                    self._build_dressing_object(
                        scene=scene,
                        category=category,
                        family=family,
                        tile=tile,
                        local_index=local_index,
                        tile_size_px=tile_size_px,
                    ),
                )

        status = "dressed" if objects else "empty"
        return {
            "id": scene_id,
            "scene_type": self._string_value(scene.get("scene_type"), default="unknown"),
            "preset_id": preset_id,
            "preset_family": self._string_value(scene.get("preset_family"), default="unknown"),
            "bounds": self._dict_value(scene, "bounds"),
            "center": self._dict_value(scene, "center"),
            "status": status,
            "requested_budget": budget,
            "generated_objects": len(objects),
            "objects": objects,
            "placement_failures": placement_failures,
        }

    def _empty_scene(self, scene: dict[str, Any], *, reason: str) -> dict[str, Any]:
        """Return an empty dressing scene entry.

        Args:
            scene: Source scene assignment.
            reason: Reason why dressing was not generated.

        Returns:
            Empty scene dressing entry.
        """
        return {
            "id": self._string_value(scene.get("id"), default="scene_unknown"),
            "scene_type": self._string_value(scene.get("scene_type"), default="unknown"),
            "preset_id": self._string_value(scene.get("preset_id"), default="generic_scene"),
            "preset_family": self._string_value(scene.get("preset_family"), default="unknown"),
            "bounds": self._dict_value(scene, "bounds"),
            "center": self._dict_value(scene, "center"),
            "status": "empty",
            "requested_budget": self._dict_value(scene, "dressing_budget"),
            "generated_objects": 0,
            "objects": [],
            "placement_failures": [{"category": "scene", "reason": reason}],
        }

    def _candidate_tiles_for_scene(
        self,
        *,
        scene: dict[str, Any],
        preset_id: str,
        category: str,
        context_rows: list[list[dict[str, Any]]],
        occupied_tiles: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Return valid candidate tiles for a scene dressing category.

        Args:
            scene: Scene preset assignment.
            preset_id: Preset id.
            category: Dressing category.
            context_rows: Per-tile context rows.
            occupied_tiles: Already used tiles in the scene.

        Returns:
            Valid tile coordinates.
        """
        bounds = self._dict_value(scene, "bounds")
        min_x, min_y, max_x, max_y = self._bounds_tuple(bounds, context_rows)
        candidates: list[tuple[int, int]] = []
        for y in range(min_y, max_y + 1):
            if y < 0 or y >= len(context_rows):
                continue
            row = context_rows[y]
            for x in range(min_x, max_x + 1):
                if x < 0 or x >= len(row) or (x, y) in occupied_tiles:
                    continue
                cell = row[x]
                if self._is_tile_allowed(
                    preset_id=preset_id,
                    category=category,
                    cell=cell,
                ):
                    candidates.append((x, y))
        if candidates:
            return candidates
        return self._fallback_candidate_tiles(
            bounds=bounds,
            context_rows=context_rows,
            occupied_tiles=occupied_tiles,
        )

    def _fallback_candidate_tiles(
        self,
        *,
        bounds: dict[str, Any],
        context_rows: list[list[dict[str, Any]]],
        occupied_tiles: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Return conservative fallback tiles when preset-specific placement is empty.

        Args:
            bounds: Scene bounds.
            context_rows: Per-tile context rows.
            occupied_tiles: Already used tiles in the scene.

        Returns:
            Fallback tile coordinates.
        """
        min_x, min_y, max_x, max_y = self._bounds_tuple(bounds, context_rows)
        candidates: list[tuple[int, int]] = []
        for y in range(min_y, max_y + 1):
            if y < 0 or y >= len(context_rows):
                continue
            row = context_rows[y]
            for x in range(min_x, max_x + 1):
                if x < 0 or x >= len(row) or (x, y) in occupied_tiles:
                    continue
                cell = row[x]
                primary = self._string_value(cell.get("primary"), default="unknown")
                flags = set(self._string_list(cell.get("flags")))
                if primary.startswith("forest") or primary in {"ruin_wall", "blocked_structure"}:
                    continue
                if flags & {"marker_start", "marker_goal"}:
                    continue
                candidates.append((x, y))
        return candidates

    def _is_tile_allowed(self, *, preset_id: str, category: str, cell: dict[str, Any]) -> bool:
        """Return whether a tile can receive a dressing object.

        Args:
            preset_id: Scene preset id.
            category: Dressing category.
            cell: Visual context cell.

        Returns:
            ``True`` when placement is safe and compatible.
        """
        primary = self._string_value(cell.get("primary"), default="unknown")
        flags = set(self._string_list(cell.get("flags")))
        if flags & {"marker_start", "marker_goal"}:
            return False
        if primary in {"ruin_wall", "blocked_structure"}:
            return category == "small_decals" and preset_id == "small_ruin_site"
        if primary.startswith("forest"):
            return False

        if preset_id == "forest_clearing_light":
            return primary == "clearing"
        if preset_id == "road_junction_forest_ruins":
            return primary.startswith("road") or (primary == "clearing" and "near_road" in flags)
        if preset_id == "small_ruin_site":
            return primary in {"ruin_floor", "clearing", "ruin_wall"} or "near_ruin" in flags
        if preset_id == "water_lowland_mud":
            return primary.startswith("water") or (primary == "clearing" and "near_water" in flags)
        return primary == "clearing"

    def _build_dressing_object(
        self,
        *,
        scene: dict[str, Any],
        category: str,
        family: str,
        tile: tuple[int, int],
        local_index: int,
        tile_size_px: int,
    ) -> dict[str, Any]:
        """Build a visual-only dressing object.

        Args:
            scene: Source scene assignment.
            category: Dressing category.
            family: Dressing family name.
            tile: Tile coordinate.
            local_index: Local object index for this category.
            tile_size_px: Tile size in pixels.

        Returns:
            Dressing object dictionary.
        """
        scene_id = self._string_value(scene.get("id"), default="scene_unknown")
        preset_id = self._string_value(scene.get("preset_id"), default="generic_scene")
        x, y = tile
        object_id = f"dressing_{scene_id}_{category}_{local_index:02d}_{x:03d}_{y:03d}"
        sprite_namespace = "decal" if category == "small_decals" else "dressing"
        draw_layer = "surface_decals" if category == "small_decals" else "scene_dressing"
        return {
            "id": object_id,
            "type": "visual_dressing",
            "source_object_type": "visual_decoration",
            "source_scene_id": scene_id,
            "source_preset_id": preset_id,
            "scene_type": self._string_value(scene.get("scene_type"), default="unknown"),
            "category": category,
            "asset_family": family,
            "family": family,
            "sprite_id": f"{sprite_namespace}.{family}",
            "draw_layer": draw_layer,
            "position": {"x": x, "y": y},
            "visual_bounds": {
                "x": x * tile_size_px,
                "y": y * tile_size_px,
                "width": tile_size_px,
                "height": tile_size_px,
            },
            "footprint": {"width": 1, "height": 1},
            "anchor": "tile_top_left",
            "visual_only": True,
            "changes_gameplay": False,
            "changes_collision": False,
            "collision_profile": "none",
            "placement_policy": "deterministic_scene_dressing_v1",
            "tags": [
                "visual_only",
                "scene_dressing",
                category,
                family,
            ],
        }

    def _build_scene_dressing_artifact(
        self,
        *,
        scene_presets: dict[str, Any],
        generated_scenes: list[dict[str, Any]],
        dressing_objects: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the scene dressing artifact.

        Args:
            scene_presets: Source scene presets artifact.
            generated_scenes: Generated scene entries.
            dressing_objects: Flat generated object list.

        Returns:
            Scene dressing artifact.
        """
        preset_counts = Counter(str(scene["preset_id"]) for scene in generated_scenes)
        status_counts = Counter(str(scene["status"]) for scene in generated_scenes)
        category_counts = Counter(str(item["category"]) for item in dressing_objects)
        family_counts = Counter(str(item["asset_family"]) for item in dressing_objects)
        return {
            "schema_version": "visual-scene-dressing-v1",
            "source_schema_version": self._string_value(
                scene_presets.get("schema_version"),
                default="unknown",
            ),
            "profile": scene_presets.get("profile", "unknown"),
            "normalized_profile": scene_presets.get("normalized_profile", "unknown"),
            "dressing_rules_version": "forest-ruins-scene-dressing-v1",
            "scenes": generated_scenes,
            "objects": dressing_objects,
            "summary": {
                "total_scenes": len(generated_scenes),
                "dressed_scenes": status_counts["dressed"],
                "empty_scenes": status_counts["empty"],
                "generated_objects": len(dressing_objects),
                "scene_counts_by_status": dict(sorted(status_counts.items())),
                "scene_counts_by_preset": dict(sorted(preset_counts.items())),
                "object_counts_by_category": dict(sorted(category_counts.items())),
                "object_counts_by_family": dict(sorted(family_counts.items())),
            },
            "contract": {
                "changes_gameplay": False,
                "changes_collision": False,
                "moves_markers": False,
            },
        }

    def _build_dressed_visual_objects(
        self,
        *,
        normalized_visual_objects: dict[str, Any],
        dressing_objects: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Append scene dressing objects to normalized visual objects.

        Args:
            normalized_visual_objects: Normalized source visual object artifact.
            dressing_objects: Generated visual-only dressing objects.

        Returns:
            Dressed visual object artifact.
        """
        source = deepcopy(normalized_visual_objects) if isinstance(normalized_visual_objects, dict) else {}
        collection_key = self._collection_key(source) or "items"
        collection = source.get(collection_key)
        if isinstance(collection, dict):
            updated_collection: dict[str, Any] = dict(collection)
            for item in dressing_objects:
                updated_collection[str(item["id"])] = item
            source[collection_key] = updated_collection
            base_count = len(collection)
        elif isinstance(collection, list):
            base_items = [deepcopy(item) for item in collection]
            base_count = len(base_items)
            source[collection_key] = base_items + [deepcopy(item) for item in dressing_objects]
        else:
            base_count = 0
            source[collection_key] = [deepcopy(item) for item in dressing_objects]

        source["schema_version"] = "visual-objects-dressed-v1"
        source["scene_dressing"] = {
            "source_schema_version": self._string_value(
                normalized_visual_objects.get("schema_version")
                if isinstance(normalized_visual_objects, dict)
                else None,
                default="unknown",
            ),
            "base_objects": base_count,
            "dressing_objects": len(dressing_objects),
            "total_objects": base_count + len(dressing_objects),
            "contract": {
                "changes_gameplay": False,
                "changes_collision": False,
                "moves_markers": False,
            },
        }
        if isinstance(source.get("summary"), dict):
            source["summary"] = dict(source["summary"])
            source["summary"]["scene_dressing"] = dict(source["scene_dressing"])
        return source

    def _build_report(self, scene_dressing: dict[str, Any]) -> dict[str, Any]:
        """Build compact scene dressing report.

        Args:
            scene_dressing: Full scene dressing artifact.

        Returns:
            Report dictionary.
        """
        summary = self._dict_value(scene_dressing, "summary")
        total_scenes = self._int_value(summary.get("total_scenes"), default=0)
        dressed_scenes = self._int_value(summary.get("dressed_scenes"), default=0)
        empty_scenes = self._int_value(summary.get("empty_scenes"), default=0)
        generated_objects = self._int_value(summary.get("generated_objects"), default=0)
        if total_scenes == 0:
            status = "warning"
        elif empty_scenes > 0 or generated_objects == 0:
            status = "warning"
        else:
            status = "ok"
        checks = [
            self._check(
                "scene_dressing_generated",
                "passed" if generated_objects > 0 or total_scenes == 0 else "warning",
                "Assigned scenes should produce deterministic visual-only dressing objects.",
            ),
            self._check(
                "scene_dressing_contract",
                "passed",
                "Generated dressing must not change gameplay, collision, or marker positions.",
            ),
        ]
        return {
            "schema_version": "visual-scene-dressing-report-v1",
            "status": status,
            "profile": scene_dressing.get("profile", "unknown"),
            "normalized_profile": scene_dressing.get("normalized_profile", "unknown"),
            "dressing_coverage": {
                "assigned_scenes": total_scenes,
                "dressed_scenes": dressed_scenes,
                "scenes_without_dressing": empty_scenes,
                "dressed_ratio_percent": self._ratio_percent(dressed_scenes, total_scenes),
                "generated_objects": generated_objects,
                "object_counts_by_category": self._dict_value(
                    summary,
                    "object_counts_by_category",
                ),
                "object_counts_by_family": self._dict_value(
                    summary,
                    "object_counts_by_family",
                ),
                "scene_counts_by_preset": self._dict_value(
                    summary,
                    "scene_counts_by_preset",
                ),
                "scene_counts_by_status": self._dict_value(
                    summary,
                    "scene_counts_by_status",
                ),
            },
            "contract": self._dict_value(scene_dressing, "contract"),
            "checks": checks,
        }

    def _scene_items(self, scene_presets: dict[str, Any]) -> list[dict[str, Any]]:
        """Return scene assignment entries.

        Args:
            scene_presets: Scene preset artifact.

        Returns:
            Scene dictionaries.
        """
        scenes = scene_presets.get("scenes")
        if not isinstance(scenes, list):
            return []
        return [scene for scene in scenes if isinstance(scene, dict)]

    def _context_rows(self, visual_context: dict[str, Any]) -> list[list[dict[str, Any]]]:
        """Return normalized visual context rows.

        Args:
            visual_context: Visual context artifact.

        Returns:
            Rows containing context cell dictionaries.
        """
        rows = visual_context.get("rows")
        if not isinstance(rows, list):
            return []
        normalized_rows: list[list[dict[str, Any]]] = []
        for row in rows:
            if not isinstance(row, list):
                normalized_rows.append([])
                continue
            normalized_rows.append([cell if isinstance(cell, dict) else {} for cell in row])
        return normalized_rows

    def _tile_size_px(self, visual_context: dict[str, Any]) -> int:
        """Return tile size in pixels from visual context dimensions.

        Args:
            visual_context: Visual context artifact.

        Returns:
            Tile size in pixels.
        """
        dimensions = self._dict_value(visual_context, "dimensions")
        return self._int_value(dimensions.get("tile_size_px"), default=self.DEFAULT_TILE_SIZE_PX)

    def _collection_key(self, data: dict[str, Any]) -> str | None:
        """Return the first visual-object collection key found.

        Args:
            data: Visual object artifact.

        Returns:
            Collection key or ``None``.
        """
        for key in self.COLLECTION_KEYS:
            if isinstance(data.get(key), (list, dict)):
                return key
        return None

    def _bounds_tuple(
        self,
        bounds: dict[str, Any],
        context_rows: list[list[dict[str, Any]]],
    ) -> tuple[int, int, int, int]:
        """Return bounded inclusive coordinates.

        Args:
            bounds: Raw bounds dictionary.
            context_rows: Per-tile context rows.

        Returns:
            ``min_x, min_y, max_x, max_y`` tuple.
        """
        height = len(context_rows)
        width = max((len(row) for row in context_rows), default=0)
        min_x = max(0, self._int_value(bounds.get("min_x"), default=0))
        min_y = max(0, self._int_value(bounds.get("min_y"), default=0))
        max_x = self._int_value(bounds.get("max_x"), default=min_x)
        max_y = self._int_value(bounds.get("max_y"), default=min_y)
        if width > 0:
            max_x = min(width - 1, max_x)
        if height > 0:
            max_y = min(height - 1, max_y)
        if max_x < min_x:
            max_x = min_x
        if max_y < min_y:
            max_y = min_y
        return min_x, min_y, max_x, max_y

    def _stable_ordered_tiles(
        self,
        tiles: list[tuple[int, int]],
        *,
        salt: str,
    ) -> list[tuple[int, int]]:
        """Return tiles ordered by deterministic hash.

        Args:
            tiles: Tile coordinates.
            salt: Stable ordering salt.

        Returns:
            Deterministically ordered tiles.
        """
        return sorted(tiles, key=lambda tile: (self._stable_int(f"{salt}:{tile[0]}:{tile[1]}"), tile))

    def _stable_int(self, value: str) -> int:
        """Return a deterministic integer hash.

        Args:
            value: Hash input value.

        Returns:
            Integer hash value.
        """
        digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, byteorder="big", signed=False)

    def _check(self, code: str, status: str, message: str) -> dict[str, str]:
        """Build a dressing check entry.

        Args:
            code: Stable check code.
            status: Check status.
            message: Human-readable check message.

        Returns:
            Check dictionary.
        """
        return {"code": code, "status": status, "message": message}

    def _dict_value(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        """Return a nested dictionary value.

        Args:
            data: Source dictionary.
            key: Key to read.

        Returns:
            Nested dictionary or empty dictionary.
        """
        value = data.get(key)
        return value if isinstance(value, dict) else {}

    def _int_value(self, value: Any, *, default: int) -> int:
        """Return an integer from raw JSON-like data.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Integer value or fallback.
        """
        return value if isinstance(value, int) and not isinstance(value, bool) else default

    def _ratio_percent(self, numerator: int, denominator: int) -> float:
        """Return a rounded percentage value.

        Args:
            numerator: Ratio numerator.
            denominator: Ratio denominator.

        Returns:
            Percentage rounded to two decimals.
        """
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100.0, 2)

    def _string_list(self, value: Any) -> list[str]:
        """Return a list of non-empty strings.

        Args:
            value: Raw JSON-like value.

        Returns:
            String list.
        """
        if not isinstance(value, list):
            return []
        strings: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                strings.append(item.strip())
        return strings

    def _string_value(self, value: Any, *, default: str) -> str:
        """Return a stripped string from raw JSON-like data.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            String value or fallback.
        """
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default
