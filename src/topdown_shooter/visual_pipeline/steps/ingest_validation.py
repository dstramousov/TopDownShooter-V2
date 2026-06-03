"""Ingest and validation step for the visual pipeline."""

from __future__ import annotations

from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.visual_pipeline.artifacts import PipelineArtifact
from topdown_shooter.visual_pipeline.context import VisualPipelineContext
from topdown_shooter.visual_pipeline.reports import PipelineStepReport


class IngestValidationStep:
    """Validate source gameplay data before visual-only processing."""

    step_id = "00_ingest_validation"

    def run(self, context: VisualPipelineContext) -> VisualPipelineContext:
        """Validate map dimensions, tile size, and critical markers.

        Args:
            context: Current visual pipeline context.

        Returns:
            Updated visual pipeline context.

        Raises:
            InvalidMapPackageError: If the source map violates hard invariants.
        """
        errors = self._collect_errors(context)
        if errors:
            report = PipelineStepReport(
                step_id=self.step_id,
                status="failed",
                inputs=("source_package", "runtime_map"),
                errors=tuple(errors),
                stats=self._build_stats(context),
            )
            context.add_report(report)
            raise InvalidMapPackageError("Visual pipeline ingest validation failed.")

        report = PipelineStepReport(
            step_id=self.step_id,
            status="ok",
            inputs=("source_package", "runtime_map"),
            outputs=(
                PipelineArtifact(
                    artifact_id="validated_runtime_map",
                    kind="runtime_map",
                    data_key="runtime_map",
                    description="Runtime map validated as visual-pipeline source of truth.",
                ),
            ),
            stats=self._build_stats(context),
        )
        context.add_report(report)
        return context

    def _collect_errors(self, context: VisualPipelineContext) -> list[str]:
        """Collect validation errors without mutating the context.

        Args:
            context: Current visual pipeline context.

        Returns:
            Validation error messages.
        """
        runtime_map = context.runtime_map
        manifest_dimensions = context.package.manifest.dimensions
        errors: list[str] = []
        if runtime_map.tile_size_px != context.config.strict_tile_size_px:
            errors.append(
                f"tile_size_px must be {context.config.strict_tile_size_px}, "
                f"got {runtime_map.tile_size_px}.",
            )
        if runtime_map.width_tiles <= 0 or runtime_map.height_tiles <= 0:
            errors.append("runtime map dimensions must be positive.")
        if runtime_map.width_tiles != manifest_dimensions.width_tiles:
            errors.append("runtime map width does not match manifest width.")
        if runtime_map.height_tiles != manifest_dimensions.height_tiles:
            errors.append("runtime map height does not match manifest height.")
        if runtime_map.tile_size_px != manifest_dimensions.tile_size_px:
            errors.append("runtime map tile size does not match manifest tile size.")
        if not runtime_map.is_inside_tile_bounds(runtime_map.start_tile):
            errors.append("start tile is outside map bounds.")
        if not runtime_map.is_inside_tile_bounds(runtime_map.goal_tile):
            errors.append("goal tile is outside map bounds.")
        if not runtime_map.tiles:
            errors.append("runtime map tile grid is empty.")
        return errors

    def _build_stats(
        self,
        context: VisualPipelineContext,
    ) -> dict[str, int | float | str | bool]:
        """Build validation statistics.

        Args:
            context: Current visual pipeline context.

        Returns:
            Scalar validation stats.
        """
        runtime_map = context.runtime_map
        return {
            "width_tiles": runtime_map.width_tiles,
            "height_tiles": runtime_map.height_tiles,
            "tile_size_px": runtime_map.tile_size_px,
            "walkable_tiles": runtime_map.walkable_tile_count,
            "blocked_tiles": runtime_map.blocked_tile_count,
            "runtime_objects": runtime_map.runtime_objects_summary.total_objects,
            "runtime_grids": len(runtime_map.runtime_grids.grid_names),
            "structured_map_present": context.package.structured_map is not None,
        }
