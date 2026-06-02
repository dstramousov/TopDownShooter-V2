"""Visual micro-scene layout builder for prepared maps."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VisualMicroSceneLayoutResult:
    """Visual micro-scene layout build output.

    Attributes:
        layouts: Runtime-readable micro-scene layout artifact.
        scene_objects: Flattened micro-scene object artifact.
        layout_report: Compact layout build report.
        layout_summary: Human-readable layout summary.
    """

    layouts: dict[str, Any]
    scene_objects: dict[str, Any]
    layout_report: dict[str, Any]
    layout_summary: str


class VisualMicroSceneLayoutBuilder:
    """Build semantic micro-scene layouts from exported micro-scenes."""

    def build(self, *, micro_scenes: dict[str, Any]) -> VisualMicroSceneLayoutResult:
        """Build micro-scene layouts and flattened scene objects.

        Args:
            micro_scenes: Visual micro-scene artifact.

        Returns:
            Visual micro-scene layout build result.
        """
        scenes = self._scene_items(micro_scenes)
        layouts: list[dict[str, Any]] = []
        scene_objects: list[dict[str, Any]] = []

        for index, scene in enumerate(scenes):
            layout, objects = self._build_layout(index=index, scene=scene)
            layouts.append(layout)
            scene_objects.extend(objects)

        layouts_artifact = self._build_layout_artifact(
            micro_scenes=micro_scenes,
            layouts=layouts,
            scene_objects=scene_objects,
        )
        scene_objects_artifact = self._build_scene_objects_artifact(
            micro_scenes=micro_scenes,
            scene_objects=scene_objects,
        )
        report = self._build_report(
            layouts_artifact=layouts_artifact,
            scene_objects_artifact=scene_objects_artifact,
        )
        return VisualMicroSceneLayoutResult(
            layouts=layouts_artifact,
            scene_objects=scene_objects_artifact,
            layout_report=report,
            layout_summary=self.format_summary(report),
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format a layout report as readable text.

        Args:
            report: Visual micro-scene layout report.

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
                "Visual micro-scene layouts",
                f"- status: {report.get('status', 'unknown')}",
                f"- layouts: {counts.get('layouts', 'unknown')}",
                f"- scene objects: {counts.get('scene_objects', 'unknown')}",
                f"- slots: {counts.get('slots', 'unknown')}",
                f"- required slots filled: {counts.get('required_slots_filled', 'unknown')}",
                f"- visual roles: {top_roles}",
            ],
        )

    def _build_layout(
        self,
        *,
        index: int,
        scene: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Build one layout and its flattened objects.

        Args:
            index: Stable scene order index.
            scene: Source micro-scene entry.

        Returns:
            Tuple containing the layout and flattened scene objects.
        """
        scene_id = self._string_value(scene.get("id"), default=f"scene_{index:03d}")
        visual_role = self._string_value(scene.get("visual_role"), default="unknown")
        bounds = self._dict_value(scene.get("bounds"))
        center = self._dict_value(scene.get("center"))
        slot_specs = self._slot_specs_for_role(visual_role=visual_role)
        linked_items = self._linked_items(scene)
        scene_objects: list[dict[str, Any]] = []
        slots: list[dict[str, Any]] = []

        for slot_index, slot_spec in enumerate(slot_specs):
            assigned = self._assign_slot_items(
                scene_id=scene_id,
                slot_index=slot_index,
                slot_spec=slot_spec,
                linked_items=linked_items,
                bounds=bounds,
                center=center,
            )
            slots.append(
                {
                    "id": f"{scene_id}_slot_{slot_index:02d}",
                    "role": slot_spec["role"],
                    "required": slot_spec["required"],
                    "accepted_categories": slot_spec["categories"],
                    "objects": [item["id"] for item in assigned],
                    "status": "filled" if assigned else "empty",
                },
            )
            scene_objects.extend(assigned)

        return (
            {
                "id": f"{scene_id}_layout",
                "scene_id": scene_id,
                "scene_type": self._string_value(scene.get("type"), default="unknown"),
                "preset_id": self._string_value(scene.get("preset_id"), default="unknown"),
                "preset_family": self._string_value(
                    scene.get("preset_family"),
                    default="unknown",
                ),
                "visual_role": visual_role,
                "priority": self._int_value(scene.get("priority"), default=0),
                "bounds": bounds,
                "center": center,
                "slots": slots,
                "object_count": len(scene_objects),
                "constraints": self._contract(),
            },
            scene_objects,
        )

    def _slot_specs_for_role(self, *, visual_role: str) -> list[dict[str, Any]]:
        """Return semantic slot specs for a visual role.

        Args:
            visual_role: Micro-scene visual role.

        Returns:
            Slot specification dictionaries.
        """
        common = [
            {
                "role": "anchor",
                "required": True,
                "categories": ["anchor"],
            },
        ]
        by_role: dict[str, list[dict[str, Any]]] = {
            "landmark_ruins": [
                {"role": "ruin_structure", "required": True, "categories": ["ruin", "wall", "floor", "rubble"]},
                {"role": "rubble_cluster", "required": False, "categories": ["rubble", "stone", "debris"]},
                {"role": "moss_patch", "required": False, "categories": ["moss", "grass", "dirt"]},
                {"role": "floor_detail", "required": False, "categories": ["crack", "floor", "detail"]},
                {"role": "runtime_prop", "required": False, "categories": ["runtime", "object"]},
            ],
            "environment_wetland": [
                {"role": "water_body", "required": True, "categories": ["water", "wet", "mud"]},
                {"role": "wet_bank", "required": False, "categories": ["bank", "mud", "dirt"]},
                {"role": "reed_cluster", "required": False, "categories": ["reed", "reeds", "grass"]},
                {"role": "mud_detail", "required": False, "categories": ["mud", "wet", "detail"]},
            ],
            "navigation_roadside": [
                {"role": "road_surface", "required": True, "categories": ["road", "path", "dirt"]},
                {"role": "roadside_detail", "required": False, "categories": ["roadside", "debris", "stone"]},
                {"role": "road_wear", "required": False, "categories": ["wear", "road", "grass"]},
                {"role": "small_debris", "required": False, "categories": ["debris", "stone", "scrap"]},
            ],
            "tactical_ambush": [
                {"role": "concealment", "required": True, "categories": ["bush", "grass", "concealment"]},
                {"role": "cover_prop", "required": False, "categories": ["runtime", "cover", "log", "stone"]},
                {"role": "trampled_ground", "required": False, "categories": ["wear", "dirt", "grass"]},
            ],
            "environment_clearing": [
                {"role": "ground_detail", "required": True, "categories": ["grass", "dirt", "detail"]},
                {"role": "small_debris", "required": False, "categories": ["stone", "leaf", "debris"]},
                {"role": "runtime_prop", "required": False, "categories": ["runtime", "object"]},
            ],
        }
        return common + by_role.get(visual_role, by_role["environment_clearing"])

    def _assign_slot_items(
        self,
        *,
        scene_id: str,
        slot_index: int,
        slot_spec: dict[str, Any],
        linked_items: list[dict[str, Any]],
        bounds: dict[str, Any],
        center: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Assign linked items to a semantic slot.

        Args:
            scene_id: Source scene id.
            slot_index: Slot order index.
            slot_spec: Slot specification.
            linked_items: Candidate linked items.
            bounds: Scene bounds.
            center: Scene center.

        Returns:
            Flattened scene object entries assigned to the slot.
        """
        slot_role = self._string_value(slot_spec.get("role"), default="detail")
        if slot_role == "anchor":
            return [
                self._make_scene_object(
                    scene_id=scene_id,
                    slot_index=slot_index,
                    source={
                        "id": f"{scene_id}_anchor",
                        "source": "layout_anchor",
                        "family": "anchor",
                        "kind": "anchor",
                        "tile": center or self._center_from_bounds(bounds),
                        "visual_only": True,
                    },
                    semantic_role="anchor",
                ),
            ]

        categories = [str(item) for item in self._list_value(slot_spec.get("categories"))]
        matches: list[dict[str, Any]] = []
        for linked_item in linked_items:
            if self._matches_categories(linked_item, categories):
                matches.append(
                    self._make_scene_object(
                        scene_id=scene_id,
                        slot_index=slot_index,
                        source=linked_item,
                        semantic_role=slot_role,
                    ),
                )
            if len(matches) >= 3:
                break
        return matches

    def _make_scene_object(
        self,
        *,
        scene_id: str,
        slot_index: int,
        source: dict[str, Any],
        semantic_role: str,
    ) -> dict[str, Any]:
        """Build one flattened scene object.

        Args:
            scene_id: Parent scene id.
            slot_index: Parent slot index.
            source: Linked source item.
            semantic_role: Semantic role assigned by the layout.

        Returns:
            Flattened scene object dictionary.
        """
        source_id = self._string_value(source.get("id"), default="unknown")
        return {
            "id": f"{scene_id}_obj_{slot_index:02d}_{source_id}",
            "scene_id": scene_id,
            "slot_id": f"{scene_id}_slot_{slot_index:02d}",
            "semantic_role": semantic_role,
            "source_id": source_id,
            "source": self._string_value(source.get("source"), default="unknown"),
            "family": self._string_value(source.get("family"), default="unknown"),
            "kind": self._string_value(source.get("kind"), default="unknown"),
            "layer": self._string_value(source.get("layer"), default="unknown"),
            "tile": self._dict_value(source.get("tile")),
            "visual_only": self._bool_value(source.get("visual_only"), default=True),
            "constraints": self._contract(),
        }

    def _linked_items(self, scene: dict[str, Any]) -> list[dict[str, Any]]:
        """Return all linkable items for a scene.

        Args:
            scene: Source micro-scene entry.

        Returns:
            Linked item dictionaries.
        """
        items: list[dict[str, Any]] = []
        dressing = self._dict_value(scene.get("dressing"))
        for item in self._list_value(dressing.get("objects")):
            if isinstance(item, dict):
                items.append({**item, "source": "scene_dressing"})
        links = self._dict_value(scene.get("links"))
        for key in ("runtime_objects", "art_layers", "art_objects"):
            for item in self._list_value(links.get(key)):
                if isinstance(item, dict):
                    items.append({**item, "source": key[:-1] if key.endswith("s") else key})
        return items

    def _matches_categories(self, item: dict[str, Any], categories: list[str]) -> bool:
        """Return whether an item belongs to any category.

        Args:
            item: Candidate item.
            categories: Accepted category tokens.

        Returns:
            True when the item matches a category token.
        """
        if not categories:
            return True
        values = [
            self._string_value(item.get("family"), default=""),
            self._string_value(item.get("kind"), default=""),
            self._string_value(item.get("category"), default=""),
            self._string_value(item.get("source"), default=""),
            self._string_value(item.get("layer"), default=""),
        ]
        haystack = " ".join(values).lower()
        return any(category.lower() in haystack for category in categories)

    def _build_layout_artifact(
        self,
        *,
        micro_scenes: dict[str, Any],
        layouts: list[dict[str, Any]],
        scene_objects: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build layout artifact.

        Args:
            micro_scenes: Source micro-scene artifact.
            layouts: Built layout entries.
            scene_objects: Flattened scene objects.

        Returns:
            Layout artifact dictionary.
        """
        role_counts = Counter(str(layout.get("visual_role", "unknown")) for layout in layouts)
        return {
            "schema_version": "visual-micro-scene-layouts-v1",
            "purpose": "Semantic object layouts for visual micro-scenes.",
            "contract": self._contract(),
            "dimensions": self._dict_value(micro_scenes.get("dimensions")),
            "coordinate_system": self._dict_value(micro_scenes.get("coordinate_system")),
            "source_artifact": "visual_micro_scenes.json",
            "layouts": layouts,
            "summary": {
                "layouts": len(layouts),
                "scene_objects": len(scene_objects),
                "slots": sum(len(self._list_value(layout.get("slots"))) for layout in layouts),
                "required_slots_filled": self._required_slots_filled(layouts),
                "visual_role_counts": dict(sorted(role_counts.items())),
            },
        }

    def _build_scene_objects_artifact(
        self,
        *,
        micro_scenes: dict[str, Any],
        scene_objects: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build flattened scene object artifact.

        Args:
            micro_scenes: Source micro-scene artifact.
            scene_objects: Flattened scene objects.

        Returns:
            Scene object artifact dictionary.
        """
        role_counts = Counter(str(item.get("semantic_role", "unknown")) for item in scene_objects)
        return {
            "schema_version": "visual-micro-scene-objects-v1",
            "purpose": "Flattened semantic objects assigned to visual micro-scene layouts.",
            "contract": self._contract(),
            "dimensions": self._dict_value(micro_scenes.get("dimensions")),
            "coordinate_system": self._dict_value(micro_scenes.get("coordinate_system")),
            "source_artifact": "visual_micro_scene_layouts.json",
            "objects": scene_objects,
            "summary": {
                "objects": len(scene_objects),
                "semantic_role_counts": dict(sorted(role_counts.items())),
            },
        }

    def _build_report(
        self,
        *,
        layouts_artifact: dict[str, Any],
        scene_objects_artifact: dict[str, Any],
    ) -> dict[str, Any]:
        """Build layout report.

        Args:
            layouts_artifact: Layout artifact.
            scene_objects_artifact: Scene object artifact.

        Returns:
            Layout report dictionary.
        """
        summary = self._dict_value(layouts_artifact.get("summary"))
        return {
            "schema_version": "visual-micro-scene-layout-report-v1",
            "status": "ok",
            "contract": self._contract(),
            "dimensions": self._dict_value(layouts_artifact.get("dimensions")),
            "counts": {
                "layouts": self._int_value(summary.get("layouts"), default=0),
                "scene_objects": self._int_value(summary.get("scene_objects"), default=0),
                "slots": self._int_value(summary.get("slots"), default=0),
                "required_slots_filled": self._int_value(
                    summary.get("required_slots_filled"),
                    default=0,
                ),
                "flattened_objects": len(
                    self._list_value(scene_objects_artifact.get("objects")),
                ),
            },
            "visual_role_counts": self._dict_value(summary.get("visual_role_counts")),
        }

    def _required_slots_filled(self, layouts: list[dict[str, Any]]) -> int:
        """Count filled required slots.

        Args:
            layouts: Layout entries.

        Returns:
            Number of filled required slots.
        """
        count = 0
        for layout in layouts:
            for slot in self._list_value(layout.get("slots")):
                if not isinstance(slot, dict):
                    continue
                if bool(slot.get("required")) and slot.get("status") == "filled":
                    count += 1
        return count

    def _center_from_bounds(self, bounds: dict[str, Any]) -> dict[str, int]:
        """Return an approximate center tile for bounds.

        Args:
            bounds: Bounds dictionary.

        Returns:
            Center tile dictionary.
        """
        x = self._int_value(bounds.get("x"), default=self._int_value(bounds.get("min_x"), default=0))
        y = self._int_value(bounds.get("y"), default=self._int_value(bounds.get("min_y"), default=0))
        width = max(1, self._int_value(bounds.get("w"), default=1))
        height = max(1, self._int_value(bounds.get("h"), default=1))
        if "max_x" in bounds and "min_x" in bounds:
            width = max(1, self._int_value(bounds.get("max_x"), default=x) - x + 1)
        if "max_y" in bounds and "min_y" in bounds:
            height = max(1, self._int_value(bounds.get("max_y"), default=y) - y + 1)
        return {"x": x + width // 2, "y": y + height // 2}

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
        """Return micro-scene entries.

        Args:
            artifact: Micro-scene artifact.

        Returns:
            Scene dictionaries.
        """
        result: list[dict[str, Any]] = []
        for item in self._list_value(artifact.get("scenes")):
            if isinstance(item, dict):
                result.append(item)
        return result

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
