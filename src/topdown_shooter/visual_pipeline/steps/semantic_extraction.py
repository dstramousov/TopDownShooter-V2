"""Semantic extraction step for the visual pipeline."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable

from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.visual_pipeline.artifacts import PipelineArtifact
from topdown_shooter.visual_pipeline.context import VisualPipelineContext
from topdown_shooter.visual_pipeline.debug.mask_renderer import SemanticMaskDebugRenderer
from topdown_shooter.visual_pipeline.masks import MaskRows, SemanticMask, SemanticMaskSet
from topdown_shooter.visual_pipeline.reports import PipelineStepReport
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import RuntimeMap
from topdown_shooter.world.tile import RuntimeTile

MaskPredicate = Callable[[RuntimeMap, RuntimeTile, TileCoord], bool]

_SEMANTIC_MASKS_DIR = "visual_map/semantic_masks"
_DEBUG_DIR = "visual_map/debug"
_SEMANTIC_MASKS_FILE = "semantic_masks.json"
_COMBINED_DEBUG_FILE = "01_semantic_masks.png"
_MASK_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("forest_mask", "Source forest-blocker tiles."),
    ("road_mask", "Source old-road tiles."),
    ("ruin_mask", "Source ruin floor and ruin wall tiles."),
    ("collision_mask", "Runtime movement-blocking tiles from gameplay truth."),
    ("open_area_mask", "Walkable open ground excluding forest, road, ruin, and water."),
)


class SemanticExtractionStep:
    """Build semantic masks and debug artifacts from the runtime map."""

    step_id = "01_semantic_extraction"

    def __init__(self, *, debug_renderer: SemanticMaskDebugRenderer | None = None) -> None:
        """Initialize the semantic extraction step.

        Args:
            debug_renderer: Optional debug renderer override for tests.
        """
        self._debug_renderer = debug_renderer or SemanticMaskDebugRenderer()

    def run(self, context: VisualPipelineContext) -> VisualPipelineContext:
        """Build semantic masks, persist debug artifacts, and update the context.

        Args:
            context: Current visual pipeline context.

        Returns:
            Updated visual pipeline context.

        Raises:
            InvalidMapPackageError: If masks or debug files cannot be produced.
        """
        mask_set = self._build_mask_set(context.runtime_map)
        self._validate_mask_dimensions(mask_set, context.runtime_map)
        context.memory["semantic_masks"] = mask_set

        semantic_dir = context.output_dir / _SEMANTIC_MASKS_DIR
        debug_dir = context.output_dir / _DEBUG_DIR
        semantic_json_path = semantic_dir / _SEMANTIC_MASKS_FILE
        combined_debug_path = debug_dir / _COMBINED_DEBUG_FILE
        mask_paths = self._build_mask_paths(semantic_dir)

        try:
            self._write_json(semantic_json_path, mask_set.to_dict())
            for mask_id, path in mask_paths.items():
                self._debug_renderer.render_individual_mask(mask_set.require(mask_id), path)
            self._debug_renderer.render_combined_preview(mask_set, combined_debug_path)
        except (OSError, ValueError, KeyError) as exc:
            raise InvalidMapPackageError(f"Failed to write semantic mask artifacts: {exc}") from exc

        context.add_report(
            PipelineStepReport(
                step_id=self.step_id,
                status="ok",
                inputs=("validated_runtime_map",),
                outputs=self._build_artifacts(
                    semantic_json_path=semantic_json_path,
                    combined_debug_path=combined_debug_path,
                    mask_paths=mask_paths,
                ),
                stats=self._build_stats(mask_set, context.runtime_map),
            ),
        )
        return context

    def _build_mask_set(self, runtime_map: RuntimeMap) -> SemanticMaskSet:
        """Build every MVP-1 semantic mask.

        Args:
            runtime_map: Runtime map source of truth.

        Returns:
            Semantic mask set.
        """
        masks: OrderedDict[str, SemanticMask] = OrderedDict()
        for mask_id, description in _MASK_DEFINITIONS:
            masks[mask_id] = SemanticMask(
                mask_id=mask_id,
                rows=self._build_rows(runtime_map, self._predicate_for(mask_id)),
                description=description,
            )
        return SemanticMaskSet(
            width_tiles=runtime_map.width_tiles,
            height_tiles=runtime_map.height_tiles,
            masks=masks,
        )

    def _predicate_for(self, mask_id: str) -> MaskPredicate:
        """Return a mask predicate by mask id.

        Args:
            mask_id: Mask identifier.

        Returns:
            Predicate used to compute the mask.

        Raises:
            KeyError: If the mask id is unknown.
        """
        predicates: dict[str, MaskPredicate] = {
            "forest_mask": self._is_forest,
            "road_mask": self._is_road,
            "ruin_mask": self._is_ruin,
            "collision_mask": self._is_collision,
            "open_area_mask": self._is_open_area,
        }
        return predicates[mask_id]

    def _build_rows(self, runtime_map: RuntimeMap, predicate: MaskPredicate) -> MaskRows:
        """Build mask rows using one predicate.

        Args:
            runtime_map: Runtime map source of truth.
            predicate: Mask predicate.

        Returns:
            Boolean mask rows.
        """
        rows: list[tuple[bool, ...]] = []
        for y, row in enumerate(runtime_map.tiles):
            mask_row: list[bool] = []
            for x, tile in enumerate(row):
                mask_row.append(predicate(runtime_map, tile, TileCoord(x=x, y=y)))
            rows.append(tuple(mask_row))
        return tuple(rows)

    def _is_forest(self, _runtime_map: RuntimeMap, tile: RuntimeTile, _coord: TileCoord) -> bool:
        """Return whether a tile belongs to the forest semantic class."""
        return tile.symbol == "T"

    def _is_road(self, _runtime_map: RuntimeMap, tile: RuntimeTile, _coord: TileCoord) -> bool:
        """Return whether a tile belongs to the road semantic class."""
        return tile.symbol == "."

    def _is_ruin(self, _runtime_map: RuntimeMap, tile: RuntimeTile, _coord: TileCoord) -> bool:
        """Return whether a tile belongs to the ruin semantic class."""
        return tile.symbol in {"R", "#"}

    def _is_collision(self, runtime_map: RuntimeMap, _tile: RuntimeTile, coord: TileCoord) -> bool:
        """Return whether runtime movement considers a tile blocked."""
        return not runtime_map.is_tile_walkable(coord)

    def _is_open_area(self, runtime_map: RuntimeMap, tile: RuntimeTile, coord: TileCoord) -> bool:
        """Return whether a tile is open walkable ground for later visual passes."""
        if self._is_collision(runtime_map, tile, coord):
            return False
        return tile.symbol not in {"T", ".", "R", "#", "w"}

    def _validate_mask_dimensions(
        self,
        mask_set: SemanticMaskSet,
        runtime_map: RuntimeMap,
    ) -> None:
        """Validate mask dimensions against the runtime map.

        Args:
            mask_set: Mask set to validate.
            runtime_map: Runtime map source of truth.

        Raises:
            InvalidMapPackageError: If a mask has invalid dimensions.
        """
        if mask_set.width_tiles != runtime_map.width_tiles:
            raise InvalidMapPackageError("Semantic mask width does not match runtime map width.")
        if mask_set.height_tiles != runtime_map.height_tiles:
            raise InvalidMapPackageError("Semantic mask height does not match runtime map height.")
        for mask in mask_set.masks.values():
            if mask.width != runtime_map.width_tiles or mask.height != runtime_map.height_tiles:
                raise InvalidMapPackageError(f"Invalid dimensions for semantic mask: {mask.mask_id}")

    def _build_mask_paths(self, semantic_dir: Path) -> OrderedDict[str, Path]:
        """Build individual mask output paths.

        Args:
            semantic_dir: Semantic mask output directory.

        Returns:
            Paths keyed by mask id.
        """
        paths: OrderedDict[str, Path] = OrderedDict()
        for mask_id, _description in _MASK_DEFINITIONS:
            paths[mask_id] = semantic_dir / f"{mask_id}.png"
        return paths

    def _build_artifacts(
        self,
        *,
        semantic_json_path: Path,
        combined_debug_path: Path,
        mask_paths: OrderedDict[str, Path],
    ) -> tuple[PipelineArtifact, ...]:
        """Build output artifact descriptors.

        Args:
            semantic_json_path: Persisted semantic mask JSON path.
            combined_debug_path: Combined debug preview path.
            mask_paths: Individual mask PNG paths.

        Returns:
            Output artifacts.
        """
        artifacts: list[PipelineArtifact] = [
            PipelineArtifact(
                artifact_id="semantic_masks",
                kind="semantic_mask_set",
                data_key="semantic_masks",
                description="In-memory semantic masks for downstream visual pipeline steps.",
            ),
            PipelineArtifact(
                artifact_id="semantic_masks_json",
                kind="json",
                path=semantic_json_path,
                description="Serialized semantic masks with ASCII 0/1 rows.",
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
                artifact_id="semantic_masks_debug_png",
                kind="debug_png",
                path=combined_debug_path,
                description="Combined semantic mask debug preview.",
            ),
        )
        return tuple(artifacts)

    def _build_stats(
        self,
        mask_set: SemanticMaskSet,
        runtime_map: RuntimeMap,
    ) -> dict[str, int | float | str | bool]:
        """Build semantic extraction statistics.

        Args:
            mask_set: Produced mask set.
            runtime_map: Runtime map source of truth.

        Returns:
            Scalar statistics for the step report.
        """
        stats: dict[str, int | float | str | bool] = {
            "width_tiles": mask_set.width_tiles,
            "height_tiles": mask_set.height_tiles,
            "tile_count": mask_set.width_tiles * mask_set.height_tiles,
            "collision_source": "runtime_map.is_tile_walkable",
        }
        for mask_id, count in mask_set.stats().items():
            stats[f"{mask_id}_tiles"] = count
        return stats

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Write a deterministic JSON file.

        Args:
            path: Destination JSON path.
            data: JSON object.

        Raises:
            OSError: If the file cannot be written.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
