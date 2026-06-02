"""Visual object normalization for prepared map baking."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VisualObjectNormalizationResult:
    """Visual object normalization output.

    Attributes:
        normalized_visual_objects: Visual objects artifact with resolved generic sprites.
        normalization_report: Compact report for preparation and quality tracking.
        normalization_summary: Human-readable normalization summary.
    """

    normalized_visual_objects: dict[str, Any]
    normalization_report: dict[str, Any]
    normalization_summary: str


class VisualObjectNormalizer:
    """Apply resolved visual families to generic visual objects."""

    COLLECTION_KEYS = ("objects", "visual_objects", "items")
    GENERIC_SEARCH_FIELDS = (
        "type",
        "sprite_id",
        "asset_id",
        "asset_family",
        "visual_id",
        "family",
    )
    SPRITE_LIKE_FIELDS = ("sprite_id", "asset_id", "visual_id")
    FAMILY_LIKE_FIELDS = ("asset_family", "family", "type")

    def normalize(
        self,
        visual_objects: dict[str, Any] | None,
        family_index: dict[str, Any],
    ) -> VisualObjectNormalizationResult:
        """Normalize generic visual objects using resolved family metadata.

        Args:
            visual_objects: Optional source ``visual_objects.json`` dictionary.
            family_index: Family resolver artifact from ``VisualObjectFamilyResolver``.

        Returns:
            Normalization result with JSON-serializable artifacts.
        """
        source = deepcopy(visual_objects) if isinstance(visual_objects, dict) else {}
        resolution_by_id = self._resolution_by_id(family_index)
        collection_key = self._collection_key(source)
        if collection_key is None:
            normalized = self._empty_normalized_artifact(source)
            report = self._build_report(
                total_objects=0,
                source_generic_objects=0,
                replaced_generic_objects=0,
                remaining_generic_objects=0,
                unresolved_generic_objects=0,
                skipped_objects=0,
                unresolved_by_source_type={},
            )
            return VisualObjectNormalizationResult(
                normalized_visual_objects=normalized,
                normalization_report=report,
                normalization_summary=self.format_summary(report),
            )

        collection = source[collection_key]
        normalized_items: list[dict[str, Any]] = []
        source_generic_objects = 0
        replaced_generic_objects = 0
        remaining_generic_objects = 0
        unresolved_generic_objects = 0
        skipped_objects = 0
        unresolved_by_source_type: dict[str, int] = {}

        if isinstance(collection, list):
            for raw_item in collection:
                item, stats = self._normalize_raw_item(raw_item, resolution_by_id)
                normalized_items.append(item)
                source_generic_objects += stats["source_generic"]
                replaced_generic_objects += stats["replaced"]
                remaining_generic_objects += stats["remaining_generic"]
                unresolved_generic_objects += stats["unresolved"]
                skipped_objects += stats["skipped"]
                self._merge_count(
                    unresolved_by_source_type,
                    stats["unresolved_source_type"],
                )
            source[collection_key] = normalized_items
        elif isinstance(collection, dict):
            normalized_dict: dict[str, Any] = {}
            for key, raw_item in collection.items():
                item, stats = self._normalize_raw_item(raw_item, resolution_by_id)
                normalized_dict[str(key)] = item
                source_generic_objects += stats["source_generic"]
                replaced_generic_objects += stats["replaced"]
                remaining_generic_objects += stats["remaining_generic"]
                unresolved_generic_objects += stats["unresolved"]
                skipped_objects += stats["skipped"]
                self._merge_count(
                    unresolved_by_source_type,
                    stats["unresolved_source_type"],
                )
            source[collection_key] = normalized_dict

        total_objects = self._collection_size(source.get(collection_key))
        source["schema_version"] = "visual-objects-normalized-v1"
        source["normalization"] = {
            "source_schema_version": self._string_value(
                visual_objects.get("schema_version") if isinstance(visual_objects, dict) else None,
                default="unknown",
            ),
            "source_collection_key": collection_key,
            "source_generic_objects": source_generic_objects,
            "replaced_generic_objects": replaced_generic_objects,
            "remaining_generic_objects": remaining_generic_objects,
            "unresolved_generic_objects": unresolved_generic_objects,
        }
        if isinstance(source.get("summary"), dict):
            source["summary"] = dict(source["summary"])
            source["summary"]["normalization"] = dict(source["normalization"])

        report = self._build_report(
            total_objects=total_objects,
            source_generic_objects=source_generic_objects,
            replaced_generic_objects=replaced_generic_objects,
            remaining_generic_objects=remaining_generic_objects,
            unresolved_generic_objects=unresolved_generic_objects,
            skipped_objects=skipped_objects,
            unresolved_by_source_type=unresolved_by_source_type,
        )
        return VisualObjectNormalizationResult(
            normalized_visual_objects=source,
            normalization_report=report,
            normalization_summary=self.format_summary(report),
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format visual object normalization as readable text.

        Args:
            report: Normalization report dictionary.

        Returns:
            Human-readable summary.
        """
        counts = self._dict_value(report, "counts")
        unresolved = self._dict_value(report, "unresolved_by_source_type")
        top_unresolved = ", ".join(
            f"{source_type}:{count}"
            for source_type, count in list(unresolved.items())[:8]
        )
        if not top_unresolved:
            top_unresolved = "none"
        return "\n".join(
            [
                "Visual object normalization",
                f"- status: {report.get('status', 'unknown')}",
                f"- visual objects: {counts.get('total_objects', 'unknown')}",
                (
                    "- source generic objects: "
                    f"{counts.get('source_generic_objects', 'unknown')}"
                ),
                (
                    "- replaced generic objects: "
                    f"{counts.get('replaced_generic_objects', 'unknown')}"
                ),
                (
                    "- remaining generic objects: "
                    f"{counts.get('remaining_generic_objects', 'unknown')}"
                ),
                f"- unresolved by source type: {top_unresolved}",
            ],
        )

    def _normalize_raw_item(
        self,
        raw_item: Any,
        resolution_by_id: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Normalize one raw visual object item.

        Args:
            raw_item: Raw JSON-like item.
            resolution_by_id: Resolver entries keyed by visual object id.

        Returns:
            Normalized item and small stats dictionary.
        """
        if not isinstance(raw_item, dict):
            return {}, self._stats(skipped=1)

        item = deepcopy(raw_item)
        object_id = self._string_value(item.get("id"), default="")
        resolution = resolution_by_id.get(object_id, {})
        was_generic = self._is_generic_item(item)
        if not was_generic:
            item.setdefault("normalization_status", "not_generic")
            return item, self._stats()

        resolution_status = self._string_value(
            resolution.get("resolution_status"),
            default="",
        )
        if resolution_status != "generic_resolved":
            source_type = self._string_value(
                item.get("source_object_type"),
                default="unknown",
            )
            item["normalization_status"] = "generic_unresolved"
            return item, self._stats(
                source_generic=1,
                remaining_generic=1,
                unresolved=1,
                unresolved_source_type=source_type,
            )

        resolved_family = self._string_value(
            resolution.get("resolved_family"),
            default="unknown",
        )
        recommended_sprite_id = self._string_value(
            resolution.get("recommended_sprite_id"),
            default=f"object.{resolved_family}",
        )
        original_sprite = self._current_sprite(item)
        self._replace_generic_fields(
            item=item,
            resolved_family=resolved_family,
            recommended_sprite_id=recommended_sprite_id,
        )
        item["normalization_status"] = "generic_replaced"
        item["normalized_family"] = resolved_family
        item["normalized_sprite_id"] = recommended_sprite_id
        if original_sprite:
            item["source_sprite_id_before_normalization"] = original_sprite
        self._append_source_tag(item, "normalized_visual_family")

        remaining_generic = 1 if self._is_generic_item(item) else 0
        unresolved = 1 if remaining_generic else 0
        source_type = self._string_value(
            item.get("source_object_type"),
            default="unknown",
        ) if remaining_generic else ""
        return item, self._stats(
            source_generic=1,
            replaced=1,
            remaining_generic=remaining_generic,
            unresolved=unresolved,
            unresolved_source_type=source_type,
        )

    def _replace_generic_fields(
        self,
        *,
        item: dict[str, Any],
        resolved_family: str,
        recommended_sprite_id: str,
    ) -> None:
        """Replace generic sprite/family fields in-place.

        Args:
            item: Visual object item to update.
            resolved_family: Concrete visual family.
            recommended_sprite_id: Concrete sprite id recommendation.
        """
        has_sprite_field = False
        for key in self.SPRITE_LIKE_FIELDS:
            value = item.get(key)
            if isinstance(value, str) and "generic" in value.lower():
                item[key] = recommended_sprite_id
                has_sprite_field = True
        for key in self.FAMILY_LIKE_FIELDS:
            value = item.get(key)
            if isinstance(value, str) and "generic" in value.lower():
                item[key] = resolved_family
        if not has_sprite_field and "sprite_id" not in item:
            item["sprite_id"] = recommended_sprite_id
        if "asset_family" in item and not isinstance(item.get("asset_family"), str):
            item["asset_family"] = resolved_family

    def _build_report(
        self,
        *,
        total_objects: int,
        source_generic_objects: int,
        replaced_generic_objects: int,
        remaining_generic_objects: int,
        unresolved_generic_objects: int,
        skipped_objects: int,
        unresolved_by_source_type: dict[str, int],
    ) -> dict[str, Any]:
        """Build compact normalization report.

        Args:
            total_objects: Total normalized visual object count.
            source_generic_objects: Generic objects before normalization.
            replaced_generic_objects: Generic objects replaced with concrete families.
            remaining_generic_objects: Generic objects still present after normalization.
            unresolved_generic_objects: Generic objects not resolved by family index.
            skipped_objects: Non-dictionary items skipped.
            unresolved_by_source_type: Unresolved generic counts by source type.

        Returns:
            Compact report dictionary.
        """
        if remaining_generic_objects > 0:
            status = "needs_work"
        elif source_generic_objects > 0:
            status = "ok"
        else:
            status = "ok"
        return {
            "schema_version": "visual-object-normalization-report-v1",
            "status": status,
            "counts": {
                "total_objects": total_objects,
                "source_generic_objects": source_generic_objects,
                "replaced_generic_objects": replaced_generic_objects,
                "remaining_generic_objects": remaining_generic_objects,
                "unresolved_generic_objects": unresolved_generic_objects,
                "skipped_objects": skipped_objects,
            },
            "unresolved_by_source_type": dict(sorted(unresolved_by_source_type.items())),
            "checks": [
                self._check(
                    "visual_object_normalization",
                    status,
                    "Generic visual objects should be replaced by resolved visual families.",
                ),
            ],
        }

    def _empty_normalized_artifact(self, source: dict[str, Any]) -> dict[str, Any]:
        """Build an empty normalized visual object artifact.

        Args:
            source: Source visual object dictionary, possibly empty.

        Returns:
            Empty normalized artifact preserving source metadata where possible.
        """
        return {
            "schema_version": "visual-objects-normalized-v1",
            "source_schema_version": self._string_value(
                source.get("schema_version"),
                default="unknown",
            ),
            "items": [],
            "normalization": {
                "source_generic_objects": 0,
                "replaced_generic_objects": 0,
                "remaining_generic_objects": 0,
                "unresolved_generic_objects": 0,
            },
        }

    def _resolution_by_id(self, family_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Build family resolver lookup by visual object id.

        Args:
            family_index: Full family resolver artifact.

        Returns:
            Resolver item dictionary keyed by id.
        """
        items = family_index.get("items", [])
        if not isinstance(items, list):
            return {}
        lookup: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            object_id = self._string_value(item.get("id"), default="")
            if object_id:
                lookup[object_id] = item
        return lookup

    def _collection_key(self, data: dict[str, Any]) -> str | None:
        """Return first supported collection key in a visual object artifact.

        Args:
            data: Visual object artifact.

        Returns:
            Collection key or ``None``.
        """
        for key in self.COLLECTION_KEYS:
            value = data.get(key)
            if isinstance(value, (list, dict)):
                return key
        return None

    def _collection_size(self, collection: Any) -> int:
        """Return item count for supported collection shapes.

        Args:
            collection: Raw collection value.

        Returns:
            Number of items in the collection.
        """
        if isinstance(collection, (list, dict)):
            return len(collection)
        return 0

    def _current_sprite(self, item: dict[str, Any]) -> str:
        """Return current sprite-like label.

        Args:
            item: Visual object dictionary.

        Returns:
            Current sprite label, or an empty string.
        """
        for key in self.GENERIC_SEARCH_FIELDS:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _is_generic_item(self, item: dict[str, Any]) -> bool:
        """Return whether a visual object still uses a generic marker.

        Args:
            item: Visual object dictionary.

        Returns:
            ``True`` when a generic marker is present in render-facing fields.
        """
        searchable = " ".join(
            self._string_value(item.get(key), default="")
            for key in self.GENERIC_SEARCH_FIELDS
        ).lower()
        return "generic" in searchable

    def _append_source_tag(self, item: dict[str, Any], tag: str) -> None:
        """Append a source tag without duplicating it.

        Args:
            item: Visual object item.
            tag: Tag to append.
        """
        tags = item.get("source_tags")
        if not isinstance(tags, list):
            item["source_tags"] = [tag]
            return
        if tag not in tags:
            tags.append(tag)

    def _stats(
        self,
        *,
        source_generic: int = 0,
        replaced: int = 0,
        remaining_generic: int = 0,
        unresolved: int = 0,
        skipped: int = 0,
        unresolved_source_type: str = "",
    ) -> dict[str, Any]:
        """Build per-item normalization stats.

        Args:
            source_generic: Whether the source item was generic.
            replaced: Whether a generic item was replaced.
            remaining_generic: Whether generic marker remains after normalization.
            unresolved: Whether a generic item was unresolved.
            skipped: Whether the item was skipped as malformed.
            unresolved_source_type: Source type of unresolved generic item.

        Returns:
            Small stats dictionary.
        """
        return {
            "source_generic": source_generic,
            "replaced": replaced,
            "remaining_generic": remaining_generic,
            "unresolved": unresolved,
            "skipped": skipped,
            "unresolved_source_type": unresolved_source_type,
        }

    def _merge_count(self, target: dict[str, int], key: str) -> None:
        """Increment a counter key if it is not empty.

        Args:
            target: Mutable counter dictionary.
            key: Counter key.
        """
        if not key:
            return
        target[key] = target.get(key, 0) + 1

    def _check(self, code: str, status: str, message: str) -> dict[str, str]:
        """Build a normalization check entry.

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
