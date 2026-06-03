"""Connected component region analysis step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.visual_pipeline.artifacts import PipelineArtifact
from topdown_shooter.visual_pipeline.context import VisualPipelineContext
from topdown_shooter.visual_pipeline.debug.region_renderer import RegionAnalysisDebugRenderer
from topdown_shooter.visual_pipeline.masks import SemanticMaskSet
from topdown_shooter.visual_pipeline.regions import RegionAnalyzer, RegionSet
from topdown_shooter.visual_pipeline.reports import PipelineStepReport

_REGIONS_DIR = "visual_map/regions"
_DEBUG_DIR = "visual_map/debug"
_REGIONS_FILE = "region_analysis.json"
_COMBINED_DEBUG_FILE = "03_region_analysis.png"


class RegionAnalysisStep:
    """Analyze connected regions from visual-only masks."""

    step_id = "03_region_analysis"

    def __init__(
        self,
        *,
        analyzer: RegionAnalyzer | None = None,
        debug_renderer: RegionAnalysisDebugRenderer | None = None,
    ) -> None:
        """Initialize the region analysis step.

        Args:
            analyzer: Optional region analyzer override for tests.
            debug_renderer: Optional debug renderer override for tests.
        """
        self._analyzer = analyzer or RegionAnalyzer()
        self._debug_renderer = debug_renderer or RegionAnalysisDebugRenderer()

    def run(self, context: VisualPipelineContext) -> VisualPipelineContext:
        """Analyze visual masks, persist region artifacts, and update context.

        Args:
            context: Current visual pipeline context.

        Returns:
            Updated visual pipeline context.

        Raises:
            InvalidMapPackageError: If visual masks are missing or artifacts cannot be written.
        """
        visual_masks = self._get_visual_masks(context)
        try:
            region_set = self._analyzer.analyze(visual_masks)
        except (KeyError, ValueError) as exc:
            raise InvalidMapPackageError(f"Failed to analyze visual regions: {exc}") from exc

        context.memory["region_analysis"] = region_set
        regions_dir = context.output_dir / _REGIONS_DIR
        debug_dir = context.output_dir / _DEBUG_DIR
        regions_json_path = regions_dir / _REGIONS_FILE
        combined_debug_path = debug_dir / _COMBINED_DEBUG_FILE

        try:
            self._write_json(regions_json_path, region_set.to_dict())
            self._debug_renderer.render(region_set, combined_debug_path)
        except (OSError, ValueError) as exc:
            raise InvalidMapPackageError(f"Failed to write region analysis artifacts: {exc}") from exc

        context.add_report(
            PipelineStepReport(
                step_id=self.step_id,
                status="ok",
                inputs=("visual_masks",),
                outputs=self._build_artifacts(
                    regions_json_path=regions_json_path,
                    combined_debug_path=combined_debug_path,
                ),
                warnings=(
                    "region analysis is visual-only; gameplay collision is not modified",
                ),
                stats=self._build_stats(region_set),
            ),
        )
        return context

    def _get_visual_masks(self, context: VisualPipelineContext) -> SemanticMaskSet:
        """Return visual masks from pipeline memory.

        Args:
            context: Current visual pipeline context.

        Returns:
            Visual mask set.

        Raises:
            InvalidMapPackageError: If mask cleanup has not run.
        """
        value = context.memory.get("visual_masks")
        if not isinstance(value, SemanticMaskSet):
            raise InvalidMapPackageError("Region analysis requires visual_masks in pipeline memory.")
        return value

    def _build_artifacts(
        self,
        *,
        regions_json_path: Path,
        combined_debug_path: Path,
    ) -> tuple[PipelineArtifact, ...]:
        """Build output artifact descriptors.

        Args:
            regions_json_path: Persisted region JSON path.
            combined_debug_path: Combined debug preview path.

        Returns:
            Output artifacts.
        """
        return (
            PipelineArtifact(
                artifact_id="region_analysis",
                kind="region_set",
                data_key="region_analysis",
                description="In-memory connected regions for downstream visual pipeline steps.",
            ),
            PipelineArtifact(
                artifact_id="region_analysis_json",
                kind="json",
                path=regions_json_path,
                description="Connected component region analysis metadata.",
            ),
            PipelineArtifact(
                artifact_id="region_analysis_debug_png",
                kind="debug_png",
                path=combined_debug_path,
                description="Color-coded region analysis debug preview.",
            ),
        )

    def _build_stats(self, region_set: RegionSet) -> dict[str, int | float | str | bool]:
        """Build scalar region analysis statistics.

        Args:
            region_set: Region analysis result.

        Returns:
            Scalar statistics for the step report.
        """
        stats: dict[str, int | float | str | bool] = {
            "width_tiles": region_set.width_tiles,
            "height_tiles": region_set.height_tiles,
            "changes_gameplay_collision": False,
        }
        stats.update(region_set.stats())
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
