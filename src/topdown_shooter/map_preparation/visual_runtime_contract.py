"""Prepared visual runtime contract validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PreparedVisualRuntimeContractResult:
    """Prepared visual runtime contract validation result.

    Attributes:
        contract_report: Machine-readable validation report.
        contract_summary: Human-readable validation summary.
    """

    contract_report: dict[str, Any]
    contract_summary: str


class PreparedVisualRuntimeContractValidator:
    """Validate prepared visual artifacts before runtime consumption.

    The validator defines the minimum data contract that future game renderers
    may rely on. It validates structure and cross-links only; it does not mutate
    map data and never changes gameplay semantics.
    """

    REQUIRED_LAYER_SCHEMAS = {
        "visual_art_layers": "visual-art-layers-v1",
        "visual_art_objects": "visual-art-objects-v1",
        "visual_art_chunks": "visual-art-chunks-v1",
        "visual_micro_scenes": "visual-micro-scenes-v1",
        "visual_micro_scene_layouts": "visual-micro-scene-layouts-v1",
        "visual_micro_scene_objects": "visual-micro-scene-objects-v1",
    }
    REQUIRED_CONTRACT_FLAGS = (
        "changes_gameplay",
        "changes_collision",
        "moves_markers",
    )

    def validate(
        self,
        *,
        expected_dimensions: dict[str, Any],
        visual_art_layers: dict[str, Any],
        visual_art_objects: dict[str, Any],
        visual_art_chunks: dict[str, Any],
        visual_micro_scenes: dict[str, Any],
        visual_micro_scene_layouts: dict[str, Any],
        visual_micro_scene_objects: dict[str, Any],
    ) -> PreparedVisualRuntimeContractResult:
        """Validate prepared visual runtime artifacts.

        Args:
            expected_dimensions: Runtime map dimensions expected by the game.
            visual_art_layers: Prepared visual terrain/transition layer artifact.
            visual_art_objects: Prepared visual object artifact.
            visual_art_chunks: Prepared chunk index artifact.
            visual_micro_scenes: Runtime-readable visual micro-scene artifact.
            visual_micro_scene_layouts: Micro-scene layout artifact.
            visual_micro_scene_objects: Flattened micro-scene object artifact.

        Returns:
            Validation result containing report and summary artifacts.
        """
        checks: list[dict[str, Any]] = []
        artifacts = {
            "visual_art_layers": visual_art_layers,
            "visual_art_objects": visual_art_objects,
            "visual_art_chunks": visual_art_chunks,
            "visual_micro_scenes": visual_micro_scenes,
            "visual_micro_scene_layouts": visual_micro_scene_layouts,
            "visual_micro_scene_objects": visual_micro_scene_objects,
        }

        checks.extend(self._check_schemas(artifacts))
        checks.extend(self._check_contracts(artifacts))
        checks.extend(
            self._check_dimensions(
                expected_dimensions=expected_dimensions,
                artifacts=artifacts,
            ),
        )
        checks.extend(
            self._check_art_layers(
                expected_dimensions=expected_dimensions,
                visual_art_layers=visual_art_layers,
            ),
        )
        checks.extend(
            self._check_art_objects(
                expected_dimensions=expected_dimensions,
                visual_art_objects=visual_art_objects,
            ),
        )
        checks.extend(
            self._check_chunks(
                expected_dimensions=expected_dimensions,
                visual_art_chunks=visual_art_chunks,
            ),
        )
        checks.extend(
            self._check_micro_scenes(
                expected_dimensions=expected_dimensions,
                visual_micro_scenes=visual_micro_scenes,
            ),
        )
        checks.extend(
            self._check_micro_scene_layouts(
                visual_micro_scenes=visual_micro_scenes,
                visual_micro_scene_layouts=visual_micro_scene_layouts,
                visual_micro_scene_objects=visual_micro_scene_objects,
            ),
        )

        status = self._overall_status(checks)
        report = {
            "schema_version": "prepared-visual-runtime-contract-report-v1",
            "status": status,
            "contract": self._safe_contract(),
            "expected_dimensions": self._normalize_dimensions(expected_dimensions),
            "artifact_schemas": {
                key: self._string_value(value.get("schema_version"), default="missing")
                for key, value in artifacts.items()
            },
            "counts": {
                "art_layer_elements": len(self._list_value(visual_art_layers.get("layers"))),
                "art_objects": len(self._list_value(visual_art_objects.get("objects"))),
                "chunks": len(self._list_value(visual_art_chunks.get("chunks"))),
                "micro_scenes": len(self._list_value(visual_micro_scenes.get("scenes"))),
                "micro_scene_layouts": len(
                    self._list_value(visual_micro_scene_layouts.get("layouts")),
                ),
                "micro_scene_objects": len(
                    self._list_value(visual_micro_scene_objects.get("objects")),
                ),
            },
            "checks": checks,
        }
        return PreparedVisualRuntimeContractResult(
            contract_report=report,
            contract_summary=self.format_summary(report),
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format a prepared visual runtime contract report.

        Args:
            report: Prepared visual runtime contract report.

        Returns:
            Human-readable summary.
        """
        counts = self._dict_value(report.get("counts"))
        failed = self._checks_by_status(report, "failed")
        warnings = self._checks_by_status(report, "warning")
        return "\n".join(
            [
                "Prepared visual runtime contract",
                f"- status: {report.get('status', 'unknown')}",
                f"- art layer elements: {counts.get('art_layer_elements', 'unknown')}",
                f"- art objects: {counts.get('art_objects', 'unknown')}",
                f"- chunks: {counts.get('chunks', 'unknown')}",
                f"- micro-scenes: {counts.get('micro_scenes', 'unknown')}",
                f"- micro-scene layouts: {counts.get('micro_scene_layouts', 'unknown')}",
                f"- micro-scene objects: {counts.get('micro_scene_objects', 'unknown')}",
                f"- failed checks: {len(failed)}",
                f"- warnings: {len(warnings)}",
            ],
        )

    def _check_schemas(self, artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate expected schema versions.

        Args:
            artifacts: Artifact dictionary by logical name.

        Returns:
            Check entries.
        """
        checks: list[dict[str, Any]] = []
        for key, expected_schema in self.REQUIRED_LAYER_SCHEMAS.items():
            artifact = artifacts.get(key, {})
            actual_schema = self._string_value(artifact.get("schema_version"), default="missing")
            checks.append(
                self._check(
                    code=f"{key}_schema",
                    status="passed" if actual_schema == expected_schema else "failed",
                    message=f"{key} must use schema {expected_schema}.",
                    details={"expected": expected_schema, "actual": actual_schema},
                ),
            )
        return checks

    def _check_contracts(self, artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        """Validate gameplay-safety contract flags.

        Args:
            artifacts: Artifact dictionary by logical name.

        Returns:
            Check entries.
        """
        checks: list[dict[str, Any]] = []
        for key, artifact in artifacts.items():
            contract = self._dict_value(artifact.get("contract"))
            invalid = [
                flag
                for flag in self.REQUIRED_CONTRACT_FLAGS
                if contract.get(flag) is not False
            ]
            checks.append(
                self._check(
                    code=f"{key}_safe_contract",
                    status="passed" if not invalid else "failed",
                    message=f"{key} must not change gameplay, collision, or markers.",
                    details={"invalid_flags": invalid},
                ),
            )
        return checks

    def _check_dimensions(
        self,
        *,
        expected_dimensions: dict[str, Any],
        artifacts: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Validate dimensions across artifacts.

        Args:
            expected_dimensions: Runtime dimensions.
            artifacts: Artifact dictionary by logical name.

        Returns:
            Check entries.
        """
        expected = self._normalize_dimensions(expected_dimensions)
        checks: list[dict[str, Any]] = []
        checks.append(
            self._check(
                code="tile_size_16",
                status="passed" if expected.get("tile_size_px") == 16 else "failed",
                message="Prepared visual runtime contract currently requires 16 px tiles.",
                details={"tile_size_px": expected.get("tile_size_px")},
            ),
        )
        for key, artifact in artifacts.items():
            actual = self._normalize_dimensions(self._dict_value(artifact.get("dimensions")))
            checks.append(
                self._check(
                    code=f"{key}_dimensions_match",
                    status="passed" if actual == expected else "failed",
                    message=f"{key} dimensions must match runtime map dimensions.",
                    details={"expected": expected, "actual": actual},
                ),
            )
        return checks

    def _check_art_layers(
        self,
        *,
        expected_dimensions: dict[str, Any],
        visual_art_layers: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate visual art layer element fields.

        Args:
            expected_dimensions: Runtime dimensions.
            visual_art_layers: Visual art layer artifact.

        Returns:
            Check entries.
        """
        dimensions = self._normalize_dimensions(expected_dimensions)
        layers = self._list_value(visual_art_layers.get("layers"))
        required_fields = ("id", "layer", "family", "kind", "tile", "variant")
        invalid = []
        unsafe = []
        out_of_bounds = []
        for index, item in enumerate(layers):
            if not isinstance(item, dict):
                invalid.append(index)
                continue
            missing = [field for field in required_fields if field not in item]
            tile = self._dict_value(item.get("tile"))
            if missing or not self._valid_tile(tile=tile, dimensions=dimensions):
                invalid.append(item.get("id", index))
            if item.get("changes_gameplay") is not False:
                unsafe.append(item.get("id", index))
            if tile and not self._tile_in_bounds(tile=tile, dimensions=dimensions):
                out_of_bounds.append(item.get("id", index))
        return [
            self._check(
                code="visual_art_layers_non_empty",
                status="passed" if layers else "failed",
                message="visual_art_layers must contain renderable elements.",
                details={"count": len(layers)},
            ),
            self._check(
                code="visual_art_layer_fields",
                status="passed" if not invalid else "failed",
                message="Every visual art layer element must include required runtime fields.",
                details={"invalid_count": len(invalid), "examples": invalid[:10]},
            ),
            self._check(
                code="visual_art_layer_safe",
                status="passed" if not unsafe else "failed",
                message="Visual art layer elements must not change gameplay.",
                details={"unsafe_count": len(unsafe), "examples": unsafe[:10]},
            ),
            self._check(
                code="visual_art_layer_bounds",
                status="passed" if not out_of_bounds else "failed",
                message="Visual art layer elements must stay inside map bounds.",
                details={"out_of_bounds_count": len(out_of_bounds), "examples": out_of_bounds[:10]},
            ),
        ]

    def _check_art_objects(
        self,
        *,
        expected_dimensions: dict[str, Any],
        visual_art_objects: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate visual art object fields.

        Args:
            expected_dimensions: Runtime dimensions.
            visual_art_objects: Visual art object artifact.

        Returns:
            Check entries.
        """
        dimensions = self._normalize_dimensions(expected_dimensions)
        objects = self._list_value(visual_art_objects.get("objects"))
        required_fields = ("id", "layer", "family", "kind", "tile", "variant")
        invalid = []
        unsafe = []
        out_of_bounds = []
        for index, item in enumerate(objects):
            if not isinstance(item, dict):
                invalid.append(index)
                continue
            missing = [field for field in required_fields if field not in item]
            tile = self._dict_value(item.get("tile"))
            if missing or not self._valid_tile(tile=tile, dimensions=dimensions):
                invalid.append(item.get("id", index))
            if item.get("changes_gameplay") is not False:
                unsafe.append(item.get("id", index))
            if tile and not self._tile_in_bounds(tile=tile, dimensions=dimensions):
                out_of_bounds.append(item.get("id", index))
        return [
            self._check(
                code="visual_art_objects_non_empty",
                status="passed",
                message="visual_art_objects may be empty on tiny or object-free maps.",
                details={"count": len(objects)},
            ),
            self._check(
                code="visual_art_object_fields",
                status="passed" if not invalid else "failed",
                message="Every visual art object must include required runtime fields.",
                details={"invalid_count": len(invalid), "examples": invalid[:10]},
            ),
            self._check(
                code="visual_art_object_safe",
                status="passed" if not unsafe else "failed",
                message="Visual art objects must not change gameplay.",
                details={"unsafe_count": len(unsafe), "examples": unsafe[:10]},
            ),
            self._check(
                code="visual_art_object_bounds",
                status="passed" if not out_of_bounds else "failed",
                message="Visual art objects must stay inside map bounds.",
                details={"out_of_bounds_count": len(out_of_bounds), "examples": out_of_bounds[:10]},
            ),
        ]

    def _check_chunks(
        self,
        *,
        expected_dimensions: dict[str, Any],
        visual_art_chunks: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate visual chunk coverage.

        Args:
            expected_dimensions: Runtime dimensions.
            visual_art_chunks: Visual art chunk artifact.

        Returns:
            Check entries.
        """
        dimensions = self._normalize_dimensions(expected_dimensions)
        chunks = self._list_value(visual_art_chunks.get("chunks"))
        chunk_size = self._int_value(visual_art_chunks.get("chunk_size_tiles"), default=32)
        expected_x = self._ceil_div(self._int_value(dimensions.get("width_tiles"), default=0), chunk_size)
        expected_y = self._ceil_div(self._int_value(dimensions.get("height_tiles"), default=0), chunk_size)
        expected_chunks = expected_x * expected_y
        invalid = []
        covered: set[tuple[int, int]] = set()
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                invalid.append(index)
                continue
            x = chunk.get("x")
            y = chunk.get("y")
            bounds = self._dict_value(chunk.get("bounds_tiles"))
            if not isinstance(x, int) or not isinstance(y, int) or not bounds:
                invalid.append(chunk.get("id", index))
                continue
            covered.add((x, y))
        expected_positions = {
            (x, y)
            for y in range(expected_y)
            for x in range(expected_x)
        }
        missing_positions = sorted(expected_positions - covered)
        return [
            self._check(
                code="visual_art_chunks_count",
                status="passed" if len(chunks) == expected_chunks else "failed",
                message="visual_art_chunks must cover the whole map with expected chunk count.",
                details={"expected": expected_chunks, "actual": len(chunks)},
            ),
            self._check(
                code="visual_art_chunks_fields",
                status="passed" if not invalid else "failed",
                message="Every visual art chunk must include coordinates and bounds.",
                details={"invalid_count": len(invalid), "examples": invalid[:10]},
            ),
            self._check(
                code="visual_art_chunks_coverage",
                status="passed" if not missing_positions else "failed",
                message="visual_art_chunks must cover every expected chunk coordinate.",
                details={"missing": missing_positions[:10], "missing_count": len(missing_positions)},
            ),
        ]

    def _check_micro_scenes(
        self,
        *,
        expected_dimensions: dict[str, Any],
        visual_micro_scenes: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate runtime micro-scene entries.

        Args:
            expected_dimensions: Runtime dimensions.
            visual_micro_scenes: Visual micro-scene artifact.

        Returns:
            Check entries.
        """
        dimensions = self._normalize_dimensions(expected_dimensions)
        scenes = self._list_value(visual_micro_scenes.get("scenes"))
        invalid = []
        unsafe = []
        scene_ids = set()
        for index, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                invalid.append(index)
                continue
            scene_id = self._string_value(scene.get("id"), default="")
            if scene_id:
                scene_ids.add(scene_id)
            bounds = self._dict_value(scene.get("bounds"))
            center = self._dict_value(scene.get("center"))
            constraints = self._dict_value(scene.get("constraints"))
            required_missing = [
                field
                for field in ("id", "type", "preset_id", "preset_family", "visual_role")
                if not scene.get(field)
            ]
            if (
                required_missing
                or not self._valid_bounds(bounds=bounds, dimensions=dimensions)
                or not self._valid_tile(tile=center, dimensions=dimensions)
            ):
                invalid.append(scene.get("id", index))
            if any(constraints.get(flag) is not False for flag in self.REQUIRED_CONTRACT_FLAGS):
                unsafe.append(scene.get("id", index))
        return [
            self._check(
                code="visual_micro_scenes_non_empty",
                status="passed",
                message="visual_micro_scenes may be empty when no scene is accepted.",
                details={"count": len(scenes)},
            ),
            self._check(
                code="visual_micro_scene_fields",
                status="passed" if not invalid else "failed",
                message="Every visual micro-scene must include runtime identity and spatial fields.",
                details={"invalid_count": len(invalid), "examples": invalid[:10]},
            ),
            self._check(
                code="visual_micro_scene_safe",
                status="passed" if not unsafe else "failed",
                message="Visual micro-scenes must not change gameplay.",
                details={"unsafe_count": len(unsafe), "examples": unsafe[:10]},
            ),
            self._check(
                code="visual_micro_scene_unique_ids",
                status="passed" if len(scene_ids) == len(scenes) else "failed",
                message="Visual micro-scene ids must be unique and present.",
                details={"unique_ids": len(scene_ids), "scenes": len(scenes)},
            ),
        ]

    def _check_micro_scene_layouts(
        self,
        *,
        visual_micro_scenes: dict[str, Any],
        visual_micro_scene_layouts: dict[str, Any],
        visual_micro_scene_objects: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Validate layout and scene-object cross-links.

        Args:
            visual_micro_scenes: Visual micro-scene artifact.
            visual_micro_scene_layouts: Visual micro-scene layout artifact.
            visual_micro_scene_objects: Visual micro-scene object artifact.

        Returns:
            Check entries.
        """
        scenes = self._list_value(visual_micro_scenes.get("scenes"))
        layouts = self._list_value(visual_micro_scene_layouts.get("layouts"))
        objects = self._list_value(visual_micro_scene_objects.get("objects"))
        scene_ids = {
            self._string_value(scene.get("id"), default="")
            for scene in scenes
            if isinstance(scene, dict)
        }
        scene_ids.discard("")
        object_ids = {
            self._string_value(item.get("id"), default="")
            for item in objects
            if isinstance(item, dict)
        }
        object_ids.discard("")
        invalid_layouts = []
        invalid_objects = []
        missing_scene_refs = []
        missing_object_refs = []
        unsafe_objects = []

        for index, layout in enumerate(layouts):
            if not isinstance(layout, dict):
                invalid_layouts.append(index)
                continue
            scene_id = self._string_value(layout.get("scene_id"), default="")
            if scene_id not in scene_ids:
                missing_scene_refs.append(layout.get("id", index))
            slots = self._list_value(layout.get("slots"))
            if not layout.get("id") or not slots:
                invalid_layouts.append(layout.get("id", index))
            for slot in slots:
                if not isinstance(slot, dict):
                    continue
                for object_id in self._list_value(slot.get("objects")):
                    if object_id not in object_ids:
                        missing_object_refs.append(object_id)

        for index, item in enumerate(objects):
            if not isinstance(item, dict):
                invalid_objects.append(index)
                continue
            scene_id = self._string_value(item.get("scene_id"), default="")
            if scene_id not in scene_ids:
                missing_scene_refs.append(item.get("id", index))
            role = item.get("role") or item.get("semantic_role")
            category = item.get("category") or item.get("family") or item.get("kind")
            if not item.get("id") or not role or not category:
                invalid_objects.append(item.get("id", index))
            if self._dict_value(item.get("constraints")).get("changes_gameplay") is not False:
                unsafe_objects.append(item.get("id", index))

        return [
            self._check(
                code="visual_micro_scene_layout_count",
                status="passed" if len(layouts) == len(scenes) else "failed",
                message="Each visual micro-scene must have one layout.",
                details={"scenes": len(scenes), "layouts": len(layouts)},
            ),
            self._check(
                code="visual_micro_scene_layout_fields",
                status="passed" if not invalid_layouts else "failed",
                message="Every visual micro-scene layout must include id, scene_id, and slots.",
                details={"invalid_count": len(invalid_layouts), "examples": invalid_layouts[:10]},
            ),
            self._check(
                code="visual_micro_scene_object_fields",
                status="passed" if not invalid_objects else "failed",
                message="Every visual micro-scene object must include id, scene_id, role, and category.",
                details={"invalid_count": len(invalid_objects), "examples": invalid_objects[:10]},
            ),
            self._check(
                code="visual_micro_scene_layout_links",
                status="passed" if not missing_scene_refs and not missing_object_refs else "failed",
                message="Micro-scene layouts and objects must reference existing scenes and objects.",
                details={
                    "missing_scene_refs": missing_scene_refs[:10],
                    "missing_object_refs": missing_object_refs[:10],
                    "missing_scene_ref_count": len(missing_scene_refs),
                    "missing_object_ref_count": len(missing_object_refs),
                },
            ),
            self._check(
                code="visual_micro_scene_object_safe",
                status="passed" if not unsafe_objects else "failed",
                message="Visual micro-scene objects must not change gameplay.",
                details={"unsafe_count": len(unsafe_objects), "examples": unsafe_objects[:10]},
            ),
        ]

    def _check(self, *, code: str, status: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        """Build one check entry.

        Args:
            code: Stable check code.
            status: Check status.
            message: Human-readable message.
            details: Optional details payload.

        Returns:
            Check dictionary.
        """
        entry: dict[str, Any] = {"code": code, "status": status, "message": message}
        if details is not None:
            entry["details"] = details
        return entry

    def _overall_status(self, checks: list[dict[str, Any]]) -> str:
        """Build overall status from check entries.

        Args:
            checks: Check entries.

        Returns:
            Overall status.
        """
        statuses = {str(check.get("status", "failed")) for check in checks}
        if "failed" in statuses:
            return "failed"
        if "warning" in statuses:
            return "warning"
        return "ok"

    def _checks_by_status(self, report: dict[str, Any], status: str) -> list[dict[str, Any]]:
        """Return checks matching a status.

        Args:
            report: Contract report.
            status: Desired status.

        Returns:
            Matching checks.
        """
        checks = self._list_value(report.get("checks"))
        return [check for check in checks if isinstance(check, dict) and check.get("status") == status]

    def _valid_tile(self, *, tile: dict[str, Any], dimensions: dict[str, Any]) -> bool:
        """Return whether a tile has integer coordinates inside map bounds.

        Args:
            tile: Tile dictionary.
            dimensions: Runtime dimensions.

        Returns:
            True when the tile is valid.
        """
        x = tile.get("x")
        y = tile.get("y")
        return isinstance(x, int) and isinstance(y, int) and self._tile_in_bounds(tile=tile, dimensions=dimensions)

    def _tile_in_bounds(self, *, tile: dict[str, Any], dimensions: dict[str, Any]) -> bool:
        """Return whether a tile is inside map bounds.

        Args:
            tile: Tile dictionary.
            dimensions: Runtime dimensions.

        Returns:
            True when inside map bounds.
        """
        x = self._int_value(tile.get("x"), default=-1)
        y = self._int_value(tile.get("y"), default=-1)
        width = self._int_value(dimensions.get("width_tiles"), default=0)
        height = self._int_value(dimensions.get("height_tiles"), default=0)
        return 0 <= x < width and 0 <= y < height

    def _valid_bounds(self, *, bounds: dict[str, Any], dimensions: dict[str, Any]) -> bool:
        """Return whether bounds are non-empty and inside map extents.

        Args:
            bounds: Bounds dictionary.
            dimensions: Runtime dimensions.

        Returns:
            True when bounds are valid.
        """
        width = self._int_value(dimensions.get("width_tiles"), default=0)
        height = self._int_value(dimensions.get("height_tiles"), default=0)
        if {"x", "y", "w", "h"}.issubset(bounds):
            x = self._int_value(bounds.get("x"), default=-1)
            y = self._int_value(bounds.get("y"), default=-1)
            w = self._int_value(bounds.get("w"), default=0)
            h = self._int_value(bounds.get("h"), default=0)
            return x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= width and y + h <= height
        if {"min_x", "min_y", "max_x", "max_y"}.issubset(bounds):
            min_x = self._int_value(bounds.get("min_x"), default=-1)
            min_y = self._int_value(bounds.get("min_y"), default=-1)
            max_x = self._int_value(bounds.get("max_x"), default=-1)
            max_y = self._int_value(bounds.get("max_y"), default=-1)
            return 0 <= min_x <= max_x < width and 0 <= min_y <= max_y < height
        return False

    def _normalize_dimensions(self, value: dict[str, Any]) -> dict[str, int]:
        """Normalize dimensions dictionary.

        Args:
            value: Raw dimensions.

        Returns:
            Normalized dimensions with integer fields.
        """
        return {
            "width_tiles": self._int_value(value.get("width_tiles"), default=0),
            "height_tiles": self._int_value(value.get("height_tiles"), default=0),
            "tile_size_px": self._int_value(value.get("tile_size_px"), default=0),
        }

    def _safe_contract(self) -> dict[str, bool]:
        """Return the required safe runtime contract.

        Returns:
            Safe contract flags.
        """
        return {
            "changes_gameplay": False,
            "changes_collision": False,
            "moves_markers": False,
            "creates_runtime_objects": False,
        }

    def _ceil_div(self, value: int, divisor: int) -> int:
        """Return ceiling division.

        Args:
            value: Dividend.
            divisor: Divisor.

        Returns:
            Ceiling division result.
        """
        if divisor <= 0:
            return 0
        return (value + divisor - 1) // divisor

    def _dict_value(self, value: Any) -> dict[str, Any]:
        """Return a dictionary or an empty dictionary.

        Args:
            value: Raw value.

        Returns:
            Dictionary value.
        """
        return value if isinstance(value, dict) else {}

    def _list_value(self, value: Any) -> list[Any]:
        """Return a list or an empty list.

        Args:
            value: Raw value.

        Returns:
            List value.
        """
        return value if isinstance(value, list) else []

    def _string_value(self, value: Any, *, default: str) -> str:
        """Return a string or fallback.

        Args:
            value: Raw value.
            default: Fallback string.

        Returns:
            String value.
        """
        return value if isinstance(value, str) and value else default

    def _int_value(self, value: Any, *, default: int) -> int:
        """Return an int or fallback.

        Args:
            value: Raw value.
            default: Fallback integer.

        Returns:
            Integer value.
        """
        return value if isinstance(value, int) else default
