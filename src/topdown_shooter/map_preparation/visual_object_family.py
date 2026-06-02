"""Visual object family resolution for prepared map baking."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VisualObjectFamilyResult:
    """Visual object family resolver output.

    Attributes:
        family_index: Per-object family resolution artifact.
        family_report: Compact report for visual quality tracking.
        family_summary: Human-readable resolver summary.
    """

    family_index: dict[str, Any]
    family_report: dict[str, Any]
    family_summary: str


class VisualObjectFamilyResolver:
    """Resolve visual object families and diagnose generic sprite usage."""

    KNOWN_SOURCE_TYPE_FAMILIES = {
        "abandoned_backpack": "abandoned_backpack",
        "abandoned_cart": "abandoned_cart",
        "ammo_cache": "ammo_cache",
        "ancient_beacon": "ancient_beacon",
        "big_dead_tree": "big_dead_tree",
        "broken_generator": "broken_generator",
        "broken_radio_mast": "broken_radio_mast",
        "buried_bunker_2x2": "buried_bunker",
        "buried_bunker_2x3": "buried_bunker",
        "bush_thicket": "bush_thicket",
        "cable_spool": "cable_spool",
        "car_wreck": "car_wreck",
        "dead_campfire": "dead_campfire",
        "earth_berm": "earth_berm",
        "fallen_log": "fallen_log",
        "field_tent": "field_tent",
        "hill": "hill",
        "medkit_cache": "medkit_cache",
        "old_checkpoint": "old_checkpoint",
        "old_grave_marker": "old_grave_marker",
        "old_well": "old_well",
        "pit": "pit",
        "ruin_platform": "ruin_platform",
        "rusted_barrel": "rusted_barrel",
        "scrap_pile": "scrap_pile",
        "stone_chunk": "stone_chunk",
        "stone_ramp": "stone_ramp",
        "stone_stairs": "stone_stairs",
        "trench": "trench",
        "warning_sign": "warning_sign",
        "watchtower": "watchtower",
        "wooden_bridge": "wooden_bridge",
    }

    COLLECTION_KEYS = ("objects", "visual_objects", "items")
    SPRITE_FIELDS = ("sprite_id", "asset_id", "asset_family", "family", "type")

    def resolve(self, visual_objects: dict[str, Any] | None) -> VisualObjectFamilyResult:
        """Resolve visual object families from a visual object export.

        Args:
            visual_objects: Optional ``visual_objects.json`` dictionary.

        Returns:
            Family resolution result with JSON-serializable artifacts.
        """
        items = self._extract_collection_items(visual_objects)
        resolved_items = [self._resolve_item(item) for item in items]
        family_index = self._build_family_index(resolved_items)
        report = self._build_report(family_index)
        summary = self.format_summary(report)
        return VisualObjectFamilyResult(
            family_index=family_index,
            family_report=report,
            family_summary=summary,
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format object family resolution as readable text.

        Args:
            report: Family resolver report.

        Returns:
            Human-readable summary.
        """
        generic = self._dict_value(report, "generic_objects")
        coverage = self._dict_value(report, "family_coverage")
        unresolved_by_type = self._dict_value(generic, "unresolved_by_source_type")
        top_unresolved = ", ".join(
            f"{source_type}:{count}"
            for source_type, count in list(unresolved_by_type.items())[:8]
        )
        if not top_unresolved:
            top_unresolved = "none"
        return "\n".join(
            [
                "Visual object families",
                f"- status: {report.get('status', 'unknown')}",
                f"- visual objects: {coverage.get('total_visual_objects', 'unknown')}",
                (
                    "- generic objects: "
                    f"{generic.get('generic_objects', 'unknown')}"
                ),
                (
                    "- resolved generic candidates: "
                    f"{generic.get('resolved_generic_objects', 'unknown')}"
                ),
                (
                    "- unresolved generic objects: "
                    f"{generic.get('unresolved_generic_objects', 'unknown')}"
                ),
                f"- unresolved by source type: {top_unresolved}",
            ],
        )

    def _build_family_index(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Build per-object family resolution artifact.

        Args:
            items: Raw visual object dictionaries.

        Returns:
            Family index artifact.
        """
        family_counts = Counter(str(item["resolved_family"]) for item in items)
        status_counts = Counter(str(item["resolution_status"]) for item in items)
        generic_by_type = Counter(
            str(item["source_object_type"] or "unknown")
            for item in items
            if item["is_generic"]
        )
        unresolved_by_type = Counter(
            str(item["source_object_type"] or "unknown")
            for item in items
            if item["resolution_status"] == "generic_unresolved"
        )
        return {
            "schema_version": "visual-object-families-v1",
            "known_source_type_families": dict(sorted(self.KNOWN_SOURCE_TYPE_FAMILIES.items())),
            "items": items,
            "summary": {
                "total_visual_objects": len(items),
                "generic_objects": status_counts["generic_resolved"]
                + status_counts["generic_unresolved"],
                "resolved_generic_objects": status_counts["generic_resolved"],
                "unresolved_generic_objects": status_counts["generic_unresolved"],
                "non_generic_objects": status_counts["non_generic"],
                "family_counts": dict(sorted(family_counts.items())),
                "generic_by_source_type": dict(sorted(generic_by_type.items())),
                "unresolved_by_source_type": dict(sorted(unresolved_by_type.items())),
                "resolution_counts": dict(sorted(status_counts.items())),
            },
        }

    def _resolve_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Resolve family metadata for one visual object.

        Args:
            item: Raw visual object dictionary.

        Returns:
            Compact resolved object entry.
        """
        object_id = self._string_value(item.get("id"), default="unknown")
        source_object_id = self._string_value(item.get("source_object_id"), default="")
        source_object_type = self._string_value(item.get("source_object_type"), default="")
        current_sprite = self._current_sprite(item)
        is_generic = self._is_generic_item(item)
        mapped_family = self.KNOWN_SOURCE_TYPE_FAMILIES.get(source_object_type)

        if is_generic and mapped_family:
            resolution_status = "generic_resolved"
            resolved_family = mapped_family
            recommended_sprite_id = f"object.{mapped_family}"
        elif is_generic:
            resolution_status = "generic_unresolved"
            resolved_family = source_object_type or "unknown"
            recommended_sprite_id = "object.generic"
        else:
            resolution_status = "non_generic"
            resolved_family = self._derive_non_generic_family(item)
            recommended_sprite_id = current_sprite

        return {
            "id": object_id,
            "source_object_id": source_object_id or None,
            "source_object_type": source_object_type or None,
            "current_sprite_id": current_sprite,
            "is_generic": is_generic,
            "resolution_status": resolution_status,
            "resolved_family": resolved_family,
            "recommended_sprite_id": recommended_sprite_id,
            "draw_layer": self._string_value(item.get("draw_layer"), default=""),
            "position": self._dict_value(item, "position"),
            "visual_bounds": self._dict_value(item, "visual_bounds"),
        }

    def _build_report(self, family_index: dict[str, Any]) -> dict[str, Any]:
        """Build compact family resolver report.

        Args:
            family_index: Full family index artifact.

        Returns:
            Compact report dictionary.
        """
        summary = self._dict_value(family_index, "summary")
        generic_objects = self._int_value(summary.get("generic_objects"), default=0)
        resolved_generic = self._int_value(
            summary.get("resolved_generic_objects"),
            default=0,
        )
        unresolved_generic = self._int_value(
            summary.get("unresolved_generic_objects"),
            default=0,
        )
        if unresolved_generic > 0:
            status = "needs_work"
        elif generic_objects > 0:
            status = "warning"
        else:
            status = "ok"

        checks = [
            self._check(
                "visual_object_family_index",
                "passed",
                "Visual object family index was built from visual_objects.json.",
            ),
            self._check(
                "generic_family_resolution",
                status,
                "Generic visual objects should map to concrete source-type families.",
            ),
        ]
        return {
            "schema_version": "visual-object-family-report-v1",
            "status": status,
            "family_coverage": {
                "total_visual_objects": self._int_value(
                    summary.get("total_visual_objects"),
                    default=0,
                ),
                "known_source_type_families": len(self.KNOWN_SOURCE_TYPE_FAMILIES),
                "family_counts": self._dict_value(summary, "family_counts"),
            },
            "generic_objects": {
                "generic_objects": generic_objects,
                "resolved_generic_objects": resolved_generic,
                "unresolved_generic_objects": unresolved_generic,
                "generic_by_source_type": self._dict_value(summary, "generic_by_source_type"),
                "unresolved_by_source_type": self._dict_value(
                    summary,
                    "unresolved_by_source_type",
                ),
            },
            "checks": checks,
        }

    def _extract_collection_items(self, data: dict[str, Any] | None) -> list[dict[str, Any]]:
        """Extract visual object dictionaries from common collection shapes.

        Args:
            data: Optional visual objects dictionary.

        Returns:
            Visual object dictionaries.
        """
        if data is None:
            return []
        for key in self.COLLECTION_KEYS:
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                return [item for item in value.values() if isinstance(item, dict)]
        return []

    def _current_sprite(self, item: dict[str, Any]) -> str:
        """Return the current sprite or asset family label.

        Args:
            item: Visual object dictionary.

        Returns:
            Current sprite label, or an empty string.
        """
        for key in self.SPRITE_FIELDS:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _is_generic_item(self, item: dict[str, Any]) -> bool:
        """Return whether a visual object uses a generic family marker.

        Args:
            item: Visual object dictionary.

        Returns:
            ``True`` when the object still points at a generic visual family.
        """
        searchable = " ".join(
            self._string_value(item.get(key), default="")
            for key in (*self.SPRITE_FIELDS, "visual_id")
        ).lower()
        return "generic" in searchable

    def _derive_non_generic_family(self, item: dict[str, Any]) -> str:
        """Derive a family label for a non-generic visual object.

        Args:
            item: Visual object dictionary.

        Returns:
            Derived family label.
        """
        source_object_type = self._string_value(item.get("source_object_type"), default="")
        if source_object_type and source_object_type != "visual_decoration":
            return self.KNOWN_SOURCE_TYPE_FAMILIES.get(source_object_type, source_object_type)
        current_sprite = self._current_sprite(item)
        if not current_sprite:
            return "unknown"
        parts = current_sprite.split(".")
        if len(parts) >= 2:
            return ".".join(parts[:2])
        return current_sprite

    def _check(self, code: str, status: str, message: str) -> dict[str, str]:
        """Build a family resolver check entry.

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

    def _string_value(self, value: Any, *, default: str) -> str:
        """Return a stripped string from raw JSON-like data.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            String value or fallback.
        """
        if isinstance(value, str):
            return value.strip()
        return default
