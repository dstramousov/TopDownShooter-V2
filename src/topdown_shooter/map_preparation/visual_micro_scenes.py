"""Visual micro-scene export for prepared maps."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VisualMicroSceneResult:
    """Visual micro-scene export output.

    Attributes:
        micro_scenes: Generated visual micro-scene artifact.
        micro_scene_report: Compact export report.
        micro_scene_summary: Human-readable export summary.
    """

    micro_scenes: dict[str, Any]
    micro_scene_report: dict[str, Any]
    micro_scene_summary: str


class VisualMicroSceneExporter:
    """Export prepared visual scene entities for runtime consumption."""

    def export(
        self,
        *,
        scene_presets: dict[str, Any],
        scene_dressing: dict[str, Any],
        visual_art_layers: dict[str, Any],
        visual_art_objects: dict[str, Any],
    ) -> VisualMicroSceneResult:
        """Build visual micro-scenes from prepared scene artifacts.

        Args:
            scene_presets: Assigned scene preset artifact.
            scene_dressing: Scene dressing artifact.
            visual_art_layers: Prepared terrain render elements.
            visual_art_objects: Prepared object render elements.

        Returns:
            Visual micro-scene export result.
        """
        preset_scenes = self._scene_items(scene_presets)
        dressing_by_scene = self._dressing_by_scene(scene_dressing)
        art_layers = self._list_value(visual_art_layers.get("layers"))
        art_objects = self._list_value(visual_art_objects.get("objects"))
        scenes: list[dict[str, Any]] = []

        for index, scene in enumerate(preset_scenes):
            micro_scene = self._build_micro_scene(
                index=index,
                scene=scene,
                dressing_scene=dressing_by_scene.get(
                    self._string_value(scene.get("id"), default=f"scene_{index:03d}"),
                    {},
                ),
                art_layers=art_layers,
                art_objects=art_objects,
            )
            scenes.append(micro_scene)

        micro_scenes = self._build_artifact(
            scene_presets=scene_presets,
            visual_art_layers=visual_art_layers,
            visual_art_objects=visual_art_objects,
            scenes=scenes,
        )
        report = self._build_report(micro_scenes)
        return VisualMicroSceneResult(
            micro_scenes=micro_scenes,
            micro_scene_report=report,
            micro_scene_summary=self.format_summary(report),
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format micro-scene export report as readable text.

        Args:
            report: Micro-scene export report.

        Returns:
            Human-readable summary.
        """
        counts = self._dict_value(report.get("counts"))
        role_counts = self._dict_value(report.get("visual_role_counts"))
        top_roles = ", ".join(
            f"{role}:{count}" for role, count in list(role_counts.items())[:8]
        )
        if not top_roles:
            top_roles = "none"
        return "\n".join(
            [
                "Visual micro-scenes",
                f"- status: {report.get('status', 'unknown')}",
                f"- scenes: {counts.get('scenes', 'unknown')}",
                f"- linked dressing objects: {counts.get('linked_dressing_objects', 'unknown')}",
                f"- linked runtime objects: {counts.get('linked_runtime_objects', 'unknown')}",
                f"- linked art layers: {counts.get('linked_art_layers', 'unknown')}",
                f"- linked art objects: {counts.get('linked_art_objects', 'unknown')}",
                f"- visual roles: {top_roles}",
            ],
        )

    def _build_micro_scene(
        self,
        *,
        index: int,
        scene: dict[str, Any],
        dressing_scene: dict[str, Any],
        art_layers: list[Any],
        art_objects: list[Any],
    ) -> dict[str, Any]:
        """Build one micro-scene entry.

        Args:
            index: Stable scene order index.
            scene: Source assigned scene entry.
            dressing_scene: Matching scene dressing entry, if present.
            art_layers: Prepared art layer elements.
            art_objects: Prepared art object elements.

        Returns:
            Micro-scene dictionary.
        """
        scene_id = self._string_value(scene.get("id"), default=f"scene_{index:03d}")
        bounds = self._dict_value(scene.get("bounds"))
        center = self._dict_value(scene.get("center"))
        dressing_objects = self._dressing_objects(dressing_scene)
        linked_runtime_objects = self._runtime_objects_in_bounds(
            art_objects=art_objects,
            bounds=bounds,
        )
        linked_art_layers = self._art_layers_in_bounds(
            art_layers=art_layers,
            bounds=bounds,
        )
        linked_art_objects = self._art_objects_in_bounds(
            art_objects=art_objects,
            bounds=bounds,
        )
        preset_family = self._string_value(scene.get("preset_family"), default="unknown")
        scene_type = self._string_value(scene.get("scene_type"), default="unknown")
        return {
            "id": scene_id,
            "index": index,
            "type": scene_type,
            "preset_id": self._string_value(scene.get("preset_id"), default="generic_scene"),
            "preset_family": preset_family,
            "assignment_status": self._string_value(
                scene.get("assignment_status"),
                default="unknown",
            ),
            "status": "ready" if self._string_value(scene.get("assignment_status"), default="") == "assigned" else "incomplete",
            "visual_role": self._visual_role(scene_type=scene_type, preset_family=preset_family),
            "priority": self._priority(scene_type=scene_type, preset_family=preset_family),
            "bounds": bounds,
            "center": center,
            "area_tiles": self._area(bounds),
            "dressing": {
                "status": self._string_value(dressing_scene.get("status"), default="missing"),
                "object_count": len(dressing_objects),
                "objects": dressing_objects,
            },
            "links": {
                "runtime_objects": linked_runtime_objects,
                "art_layers": linked_art_layers,
                "art_objects": linked_art_objects,
            },
            "constraints": {
                "changes_gameplay": False,
                "changes_collision": False,
                "moves_markers": False,
                "visual_only": True,
                "must_not_cover_critical_objects": True,
            },
            "source": {
                "scene_preset_artifact": "visual_scene_presets.json",
                "scene_dressing_artifact": "visual_scene_dressing.json",
                "visual_art_layers_artifact": "visual_art_layers.json",
                "visual_art_objects_artifact": "visual_art_objects.json",
            },
        }

    def _build_artifact(
        self,
        *,
        scene_presets: dict[str, Any],
        visual_art_layers: dict[str, Any],
        visual_art_objects: dict[str, Any],
        scenes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the micro-scene artifact.

        Args:
            scene_presets: Source scene preset artifact.
            visual_art_layers: Prepared visual art layers.
            visual_art_objects: Prepared visual art objects.
            scenes: Built micro-scene entries.

        Returns:
            Micro-scene artifact dictionary.
        """
        role_counts = Counter(str(scene.get("visual_role", "unknown")) for scene in scenes)
        family_counts = Counter(str(scene.get("preset_family", "unknown")) for scene in scenes)
        return {
            "schema_version": "visual-micro-scenes-v1",
            "purpose": "Runtime-readable visual micro-scene entities for prepared maps.",
            "contract": self._contract(),
            "dimensions": self._dict_value(visual_art_layers.get("dimensions")),
            "coordinate_system": self._dict_value(visual_art_layers.get("coordinate_system")),
            "generation": {
                "deterministic": True,
                "source_artifacts": [
                    "visual_scene_presets.json",
                    "visual_scene_dressing.json",
                    "visual_art_layers.json",
                    "visual_art_objects.json",
                ],
                "source_schema_versions": {
                    "visual_scene_presets": scene_presets.get("schema_version"),
                    "visual_art_layers": visual_art_layers.get("schema_version"),
                    "visual_art_objects": visual_art_objects.get("schema_version"),
                },
            },
            "scenes": scenes,
            "summary": {
                "scenes": len(scenes),
                "linked_dressing_objects": sum(
                    self._int_value(scene.get("dressing", {}).get("object_count"), default=0)
                    for scene in scenes
                    if isinstance(scene.get("dressing"), dict)
                ),
                "linked_runtime_objects": sum(
                    len(self._list_value(self._dict_value(scene.get("links")).get("runtime_objects")))
                    for scene in scenes
                ),
                "linked_art_layers": sum(
                    len(self._list_value(self._dict_value(scene.get("links")).get("art_layers")))
                    for scene in scenes
                ),
                "linked_art_objects": sum(
                    len(self._list_value(self._dict_value(scene.get("links")).get("art_objects")))
                    for scene in scenes
                ),
                "visual_role_counts": dict(sorted(role_counts.items())),
                "preset_family_counts": dict(sorted(family_counts.items())),
            },
        }

    def _build_report(self, micro_scenes: dict[str, Any]) -> dict[str, Any]:
        """Build micro-scene export report.

        Args:
            micro_scenes: Micro-scene artifact.

        Returns:
            Report dictionary.
        """
        summary = self._dict_value(micro_scenes.get("summary"))
        return {
            "schema_version": "visual-micro-scenes-report-v1",
            "status": "ok",
            "contract": self._contract(),
            "dimensions": self._dict_value(micro_scenes.get("dimensions")),
            "counts": {
                "scenes": self._int_value(summary.get("scenes"), default=0),
                "linked_dressing_objects": self._int_value(
                    summary.get("linked_dressing_objects"),
                    default=0,
                ),
                "linked_runtime_objects": self._int_value(
                    summary.get("linked_runtime_objects"),
                    default=0,
                ),
                "linked_art_layers": self._int_value(summary.get("linked_art_layers"), default=0),
                "linked_art_objects": self._int_value(summary.get("linked_art_objects"), default=0),
            },
            "visual_role_counts": self._dict_value(summary.get("visual_role_counts")),
            "preset_family_counts": self._dict_value(summary.get("preset_family_counts")),
        }

    def _dressing_by_scene(self, scene_dressing: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Index scene dressing entries by scene id.

        Args:
            scene_dressing: Scene dressing artifact.

        Returns:
            Mapping from scene id to dressing scene entry.
        """
        result: dict[str, dict[str, Any]] = {}
        for scene in self._scene_items(scene_dressing):
            scene_id = self._string_value(scene.get("id"), default="")
            if scene_id:
                result[scene_id] = scene
        return result

    def _dressing_objects(self, dressing_scene: dict[str, Any]) -> list[dict[str, Any]]:
        """Return compact linked dressing object records.

        Args:
            dressing_scene: Scene dressing entry.

        Returns:
            Compact dressing object dictionaries.
        """
        objects: list[dict[str, Any]] = []
        for item in self._list_value(dressing_scene.get("objects")):
            if not isinstance(item, dict):
                continue
            position = self._dict_value(item.get("position"))
            objects.append(
                {
                    "id": self._string_value(item.get("id"), default="unknown"),
                    "family": self._string_value(item.get("family"), default="unknown"),
                    "category": self._string_value(item.get("category"), default="unknown"),
                    "tile": {
                        "x": self._int_value(position.get("x"), default=0),
                        "y": self._int_value(position.get("y"), default=0),
                    },
                    "layer": self._string_value(item.get("draw_layer"), default="unknown"),
                    "visual_only": self._bool_value(item.get("visual_only"), default=True),
                },
            )
        return objects

    def _runtime_objects_in_bounds(
        self,
        *,
        art_objects: list[Any],
        bounds: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return runtime object links inside scene bounds.

        Args:
            art_objects: Prepared art object elements.
            bounds: Scene bounds.

        Returns:
            Compact runtime object links.
        """
        links: list[dict[str, Any]] = []
        for item in art_objects:
            if not isinstance(item, dict) or item.get("source") != "runtime_object":
                continue
            if not self._tile_in_bounds(self._dict_value(item.get("tile")), bounds):
                continue
            links.append(self._object_link(item))
        return links

    def _art_objects_in_bounds(
        self,
        *,
        art_objects: list[Any],
        bounds: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return visual art object links inside scene bounds.

        Args:
            art_objects: Prepared art object elements.
            bounds: Scene bounds.

        Returns:
            Compact object links.
        """
        links: list[dict[str, Any]] = []
        for item in art_objects:
            if not isinstance(item, dict):
                continue
            if not self._tile_in_bounds(self._dict_value(item.get("tile")), bounds):
                continue
            links.append(self._object_link(item))
        return links

    def _art_layers_in_bounds(
        self,
        *,
        art_layers: list[Any],
        bounds: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return compact art layer references inside scene bounds.

        Args:
            art_layers: Prepared art layer elements.
            bounds: Scene bounds.

        Returns:
            Compact terrain layer references.
        """
        links: list[dict[str, Any]] = []
        for item in art_layers:
            if not isinstance(item, dict):
                continue
            if not self._tile_in_bounds(self._dict_value(item.get("tile")), bounds):
                continue
            links.append(
                {
                    "id": self._string_value(item.get("id"), default="unknown"),
                    "family": self._string_value(item.get("family"), default="unknown"),
                    "kind": self._string_value(item.get("kind"), default="unknown"),
                    "layer": self._string_value(item.get("layer"), default="unknown"),
                    "tile": self._dict_value(item.get("tile")),
                },
            )
        return links

    def _object_link(self, item: dict[str, Any]) -> dict[str, Any]:
        """Build a compact object link.

        Args:
            item: Visual art object element.

        Returns:
            Object link dictionary.
        """
        return {
            "id": self._string_value(item.get("id"), default="unknown"),
            "source": self._string_value(item.get("source"), default="unknown"),
            "family": self._string_value(item.get("family"), default="unknown"),
            "kind": self._string_value(item.get("kind"), default="unknown"),
            "layer": self._string_value(item.get("layer"), default="unknown"),
            "tile": self._dict_value(item.get("tile")),
            "visual_only": self._bool_value(item.get("visual_only"), default=True),
        }

    def _tile_in_bounds(self, tile: dict[str, Any], bounds: dict[str, Any]) -> bool:
        """Return whether a tile is inside scene bounds.

        Args:
            tile: Tile coordinate dictionary.
            bounds: Scene bounds dictionary.

        Returns:
            True when tile is inside bounds.
        """
        x = self._int_value(tile.get("x"), default=-1)
        y = self._int_value(tile.get("y"), default=-1)
        min_x, min_y, max_x, max_y = self._bounds_tuple(bounds)
        return min_x <= x <= max_x and min_y <= y <= max_y

    def _bounds_tuple(self, bounds: dict[str, Any]) -> tuple[int, int, int, int]:
        """Return inclusive scene bounds.

        Args:
            bounds: Scene bounds dictionary.

        Returns:
            Tuple of min x, min y, max x, max y.
        """
        x = self._int_value(bounds.get("x"), default=0)
        y = self._int_value(bounds.get("y"), default=0)
        if "w" in bounds or "h" in bounds:
            w = max(1, self._int_value(bounds.get("w"), default=1))
            h = max(1, self._int_value(bounds.get("h"), default=1))
            return x, y, x + w - 1, y + h - 1
        min_x = self._int_value(bounds.get("min_x"), default=x)
        min_y = self._int_value(bounds.get("min_y"), default=y)
        max_x = self._int_value(bounds.get("max_x"), default=min_x)
        max_y = self._int_value(bounds.get("max_y"), default=min_y)
        return min_x, min_y, max_x, max_y

    def _area(self, bounds: dict[str, Any]) -> int:
        """Return scene area in tiles.

        Args:
            bounds: Scene bounds dictionary.

        Returns:
            Tile area.
        """
        min_x, min_y, max_x, max_y = self._bounds_tuple(bounds)
        return max(0, max_x - min_x + 1) * max(0, max_y - min_y + 1)

    def _visual_role(self, *, scene_type: str, preset_family: str) -> str:
        """Return a coarse runtime visual role for a scene.

        Args:
            scene_type: Scene type label.
            preset_family: Preset family label.

        Returns:
            Visual role label.
        """
        if preset_family == "ruins" or "ruin" in scene_type:
            return "landmark_ruins"
        if preset_family == "wetland" or "water" in scene_type:
            return "environment_wetland"
        if preset_family == "roadside" or "road" in scene_type:
            return "navigation_roadside"
        if "ambush" in scene_type:
            return "tactical_ambush"
        return "environment_clearing"

    def _priority(self, *, scene_type: str, preset_family: str) -> int:
        """Return scene visual priority.

        Args:
            scene_type: Scene type label.
            preset_family: Preset family label.

        Returns:
            Priority number, larger means more important.
        """
        if preset_family == "ruins" or "ruin" in scene_type:
            return 90
        if preset_family == "roadside" or "road" in scene_type:
            return 70
        if preset_family == "wetland" or "water" in scene_type:
            return 60
        return 50

    def _contract(self) -> dict[str, bool]:
        """Return visual-only contract flags.

        Returns:
            Contract dictionary.
        """
        return {
            "changes_gameplay": False,
            "changes_collision": False,
            "moves_markers": False,
        }

    def _scene_items(self, artifact: dict[str, Any]) -> list[dict[str, Any]]:
        """Return scene entries from an artifact.

        Args:
            artifact: Artifact dictionary.

        Returns:
            Scene entry list.
        """
        for key in ("scenes", "items"):
            raw = artifact.get(key)
            if isinstance(raw, list):
                return [item for item in raw if isinstance(item, dict)]
        return []

    def _dict_value(self, value: Any) -> dict[str, Any]:
        """Return a dictionary value or an empty dictionary.

        Args:
            value: Raw value.

        Returns:
            Dictionary value.
        """
        return value if isinstance(value, dict) else {}

    def _list_value(self, value: Any) -> list[Any]:
        """Return a list value or an empty list.

        Args:
            value: Raw value.

        Returns:
            List value.
        """
        return value if isinstance(value, list) else []

    def _string_value(self, value: Any, *, default: str) -> str:
        """Return a normalized string value.

        Args:
            value: Raw value.
            default: Fallback string.

        Returns:
            String value.
        """
        return value if isinstance(value, str) and value else default

    def _int_value(self, value: Any, *, default: int) -> int:
        """Return a normalized integer value.

        Args:
            value: Raw value.
            default: Fallback integer.

        Returns:
            Integer value.
        """
        return value if isinstance(value, int) else default

    def _bool_value(self, value: Any, *, default: bool) -> bool:
        """Return a normalized boolean value.

        Args:
            value: Raw value.
            default: Fallback boolean.

        Returns:
            Boolean value.
        """
        return value if isinstance(value, bool) else default
