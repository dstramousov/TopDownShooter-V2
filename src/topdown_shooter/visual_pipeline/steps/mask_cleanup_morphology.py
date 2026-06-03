"""Visual-only mask cleanup and morphology step."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.visual_pipeline.artifacts import PipelineArtifact
from topdown_shooter.visual_pipeline.context import VisualPipelineContext
from topdown_shooter.visual_pipeline.debug.mask_renderer import SemanticMaskDebugRenderer
from topdown_shooter.visual_pipeline.masks import SemanticMask, SemanticMaskSet
from topdown_shooter.visual_pipeline.morphology import BinaryMorphology
from topdown_shooter.visual_pipeline.reports import PipelineStepReport

_VISUAL_MASKS_DIR = "visual_map/visual_masks"
_DEBUG_DIR = "visual_map/debug"
_VISUAL_MASKS_FILE = "visual_masks.json"
_COMBINED_DEBUG_FILE = "02_mask_cleanup_morphology.png"
_VISUAL_MASK_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("forest_visual_mask", "Visual forest blocker mask copied from semantic truth."),
    ("forest_core_mask", "Eroded internal forest area for later dense forest rendering."),
    ("forest_edge_mask", "Forest source cells outside the eroded core."),
    ("forest_shadow_band_mask", "Walkable open cells adjacent to forest for visual-only shadows."),
    ("road_visual_mask", "Road mask preserved for connectivity-sensitive road rendering."),
    ("ruin_visual_mask", "Ruin mask preserved for floor and wall normalization."),
    ("collision_lock_mask", "Gameplay collision mask copied unchanged as a visual lock."),
    ("open_area_visual_mask", "Walkable open-area mask copied unchanged for later placement rules."),
)
_VISUAL_MASK_COLORS = {
    "open_area_visual_mask": (74, 114, 54),
    "forest_shadow_band_mask": (31, 54, 36),
    "forest_edge_mask": (33, 98, 52),
    "forest_core_mask": (12, 49, 26),
    "forest_visual_mask": (20, 73, 38),
    "road_visual_mask": (158, 128, 78),
    "ruin_visual_mask": (116, 116, 111),
    "collision_lock_mask": (150, 34, 34),
}
_VISUAL_MASK_PRIORITY = (
    "open_area_visual_mask",
    "forest_shadow_band_mask",
    "road_visual_mask",
    "ruin_visual_mask",
    "forest_visual_mask",
    "forest_edge_mask",
    "forest_core_mask",
    "collision_lock_mask",
)


class MaskCleanupMorphologyStep:
    """Build visual-only derived masks from semantic source masks."""

    step_id = "02_mask_cleanup_morphology"

    def __init__(
        self,
        *,
        morphology: BinaryMorphology | None = None,
        debug_renderer: SemanticMaskDebugRenderer | None = None,
    ) -> None:
        """Initialize the mask cleanup step.

        Args:
            morphology: Optional morphology helper override for tests.
            debug_renderer: Optional debug renderer override for tests.
        """
        self._morphology = morphology or BinaryMorphology()
        self._debug_renderer = debug_renderer or SemanticMaskDebugRenderer()

    def run(self, context: VisualPipelineContext) -> VisualPipelineContext:
        """Build visual masks, write debug artifacts, and update the context.

        Args:
            context: Current visual pipeline context.

        Returns:
            Updated visual pipeline context.

        Raises:
            InvalidMapPackageError: If semantic masks are missing or artifacts cannot be written.
        """
        semantic_masks = self._get_semantic_masks(context)
        visual_masks = self._build_visual_masks(semantic_masks)
        self._validate_dimensions(visual_masks, semantic_masks)
        context.memory["visual_masks"] = visual_masks

        visual_dir = context.output_dir / _VISUAL_MASKS_DIR
        debug_dir = context.output_dir / _DEBUG_DIR
        visual_json_path = visual_dir / _VISUAL_MASKS_FILE
        combined_debug_path = debug_dir / _COMBINED_DEBUG_FILE
        mask_paths = self._build_mask_paths(visual_dir)

        try:
            self._write_json(visual_json_path, self._to_json_payload(visual_masks))
            for mask_id, path in mask_paths.items():
                self._debug_renderer.render_individual_mask(visual_masks.require(mask_id), path)
            self._debug_renderer.render_combined_preview_with_palette(
                visual_masks,
                combined_debug_path,
                palette=_VISUAL_MASK_COLORS,
                priority=_VISUAL_MASK_PRIORITY,
            )
        except (OSError, ValueError, KeyError) as exc:
            raise InvalidMapPackageError(f"Failed to write visual mask artifacts: {exc}") from exc

        context.add_report(
            PipelineStepReport(
                step_id=self.step_id,
                status="ok",
                inputs=("semantic_masks",),
                outputs=self._build_artifacts(
                    visual_json_path=visual_json_path,
                    combined_debug_path=combined_debug_path,
                    mask_paths=mask_paths,
                ),
                warnings=(
                    "visual masks are derived artifacts; gameplay collision is not modified",
                ),
                stats=self._build_stats(semantic_masks, visual_masks),
            ),
        )
        return context

    def _get_semantic_masks(self, context: VisualPipelineContext) -> SemanticMaskSet:
        """Return semantic masks from pipeline memory.

        Args:
            context: Current visual pipeline context.

        Returns:
            Semantic mask set.

        Raises:
            InvalidMapPackageError: If the semantic extraction step has not run.
        """
        value = context.memory.get("semantic_masks")
        if not isinstance(value, SemanticMaskSet):
            raise InvalidMapPackageError("Mask cleanup requires semantic_masks in pipeline memory.")
        return value

    def _build_visual_masks(self, semantic_masks: SemanticMaskSet) -> SemanticMaskSet:
        """Build visual-only masks from semantic source masks.

        Args:
            semantic_masks: Source semantic masks.

        Returns:
            Derived visual mask set.
        """
        forest = semantic_masks.require("forest_mask").rows
        road = semantic_masks.require("road_mask").rows
        ruin = semantic_masks.require("ruin_mask").rows
        collision = semantic_masks.require("collision_mask").rows
        open_area = semantic_masks.require("open_area_mask").rows

        forest_core = self._morphology.erode(forest, radius=1)
        forest_edge = self._morphology.difference(forest, forest_core)
        forest_shadow_band = self._morphology.intersection(
            self._morphology.difference(self._morphology.dilate(forest, radius=1), forest),
            open_area,
        )

        rows_by_id = OrderedDict(
            [
                ("forest_visual_mask", forest),
                ("forest_core_mask", forest_core),
                ("forest_edge_mask", forest_edge),
                ("forest_shadow_band_mask", forest_shadow_band),
                ("road_visual_mask", road),
                ("ruin_visual_mask", ruin),
                ("collision_lock_mask", collision),
                ("open_area_visual_mask", open_area),
            ],
        )
        descriptions = dict(_VISUAL_MASK_DEFINITIONS)
        masks: OrderedDict[str, SemanticMask] = OrderedDict()
        for mask_id, rows in rows_by_id.items():
            masks[mask_id] = SemanticMask(
                mask_id=mask_id,
                rows=rows,
                description=descriptions[mask_id],
            )
        return SemanticMaskSet(
            width_tiles=semantic_masks.width_tiles,
            height_tiles=semantic_masks.height_tiles,
            masks=masks,
        )

    def _validate_dimensions(
        self,
        visual_masks: SemanticMaskSet,
        semantic_masks: SemanticMaskSet,
    ) -> None:
        """Validate visual masks against source semantic dimensions.

        Args:
            visual_masks: Derived visual masks.
            semantic_masks: Source semantic masks.

        Raises:
            InvalidMapPackageError: If dimensions do not match.
        """
        if visual_masks.width_tiles != semantic_masks.width_tiles:
            raise InvalidMapPackageError("Visual mask width does not match semantic mask width.")
        if visual_masks.height_tiles != semantic_masks.height_tiles:
            raise InvalidMapPackageError("Visual mask height does not match semantic mask height.")
        for mask in visual_masks.masks.values():
            if mask.width != semantic_masks.width_tiles or mask.height != semantic_masks.height_tiles:
                raise InvalidMapPackageError(f"Invalid dimensions for visual mask: {mask.mask_id}")

    def _build_mask_paths(self, visual_dir: Path) -> OrderedDict[str, Path]:
        """Build individual visual mask output paths.

        Args:
            visual_dir: Visual mask output directory.

        Returns:
            Paths keyed by mask id.
        """
        paths: OrderedDict[str, Path] = OrderedDict()
        for mask_id, _description in _VISUAL_MASK_DEFINITIONS:
            paths[mask_id] = visual_dir / f"{mask_id}.png"
        return paths

    def _to_json_payload(self, visual_masks: SemanticMaskSet) -> dict[str, Any]:
        """Serialize visual masks to a JSON-compatible dictionary.

        Args:
            visual_masks: Visual mask set.

        Returns:
            Serialized visual mask payload.
        """
        return {
            "schema_version": "visual-masks-v1",
            "source": {
                "semantic_masks_key": "semantic_masks",
                "changes_gameplay_collision": False,
            },
            "dimensions": {
                "width_tiles": visual_masks.width_tiles,
                "height_tiles": visual_masks.height_tiles,
            },
            "masks": [mask.to_dict() for mask in visual_masks.masks.values()],
        }

    def _build_artifacts(
        self,
        *,
        visual_json_path: Path,
        combined_debug_path: Path,
        mask_paths: OrderedDict[str, Path],
    ) -> tuple[PipelineArtifact, ...]:
        """Build output artifact descriptors.

        Args:
            visual_json_path: Persisted visual mask JSON path.
            combined_debug_path: Combined debug preview path.
            mask_paths: Individual mask PNG paths.

        Returns:
            Output artifacts.
        """
        artifacts: list[PipelineArtifact] = [
            PipelineArtifact(
                artifact_id="visual_masks",
                kind="visual_mask_set",
                data_key="visual_masks",
                description="In-memory visual masks for downstream visual pipeline steps.",
            ),
            PipelineArtifact(
                artifact_id="visual_masks_json",
                kind="json",
                path=visual_json_path,
                description="Serialized visual-only derived masks with ASCII 0/1 rows.",
            ),
        ]
        for mask_id, path in mask_paths.items():
            artifacts.append(
                PipelineArtifact(
                    artifact_id=mask_id,
                    kind="debug_png",
                    path=path,
                    description=f"Debug PNG for {mask_id}.",
                ),
            )
        artifacts.append(
            PipelineArtifact(
                artifact_id="mask_cleanup_debug_png",
                kind="debug_png",
                path=combined_debug_path,
                description="Combined visual mask cleanup debug preview.",
            ),
        )
        return tuple(artifacts)

    def _build_stats(
        self,
        semantic_masks: SemanticMaskSet,
        visual_masks: SemanticMaskSet,
    ) -> dict[str, int | float | str | bool]:
        """Build mask cleanup statistics.

        Args:
            semantic_masks: Source semantic masks.
            visual_masks: Derived visual masks.

        Returns:
            Scalar statistics for the step report.
        """
        stats: dict[str, int | float | str | bool] = {
            "width_tiles": visual_masks.width_tiles,
            "height_tiles": visual_masks.height_tiles,
            "changes_gameplay_collision": False,
            "forest_core_radius_tiles": 1,
            "forest_shadow_radius_tiles": 1,
        }
        for mask_id, count in visual_masks.stats().items():
            stats[f"{mask_id}_tiles"] = count
        stats["source_forest_mask_tiles"] = semantic_masks.require("forest_mask").active_tiles
        stats["source_collision_mask_tiles"] = semantic_masks.require("collision_mask").active_tiles
        return stats

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Write JSON data to disk.

        Args:
            path: Destination path.
            data: JSON-compatible dictionary.

        Raises:
            OSError: If the file cannot be written.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
