"""Visual pipeline runner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from topdown_shooter import __version__
from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.visual_pipeline.config import VisualPipelineConfig
from topdown_shooter.visual_pipeline.context import VisualPipelineContext
from topdown_shooter.visual_pipeline.reports import PipelineStepReport
from topdown_shooter.visual_pipeline.steps.base import VisualPipelineStep
from topdown_shooter.visual_pipeline.steps.ingest_validation import IngestValidationStep
from topdown_shooter.visual_pipeline.steps.semantic_extraction import SemanticExtractionStep
from topdown_shooter.visual_pipeline.steps.placeholders import PlaceholderStep
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(frozen=True, slots=True)
class VisualPipelineResult:
    """Result of a visual pipeline execution.

    Attributes:
        report_path: Persisted pipeline report path.
        status: Overall pipeline status.
        generated_artifacts: Relative generated artifact paths.
        report: Full pipeline report dictionary.
    """

    report_path: Path
    status: str
    generated_artifacts: tuple[str, ...]
    report: dict[str, Any]


class VisualPipeline:
    """Run visual preparation stages in the order defined by the visual normalizer spec."""

    REPORTS_DIR = "reports"
    REPORT_FILE = "visual_pipeline_report.json"

    def __init__(
        self,
        *,
        config: VisualPipelineConfig | None = None,
        steps: Iterable[VisualPipelineStep] | None = None,
    ) -> None:
        """Initialize the visual pipeline.

        Args:
            config: Optional pipeline configuration.
            steps: Optional step sequence override for tests.
        """
        self._config = config or VisualPipelineConfig()
        self._steps = tuple(steps) if steps is not None else self.build_default_steps()

    @property
    def step_ids(self) -> tuple[str, ...]:
        """Return configured step identifiers in execution order.

        Returns:
            Step identifiers.
        """
        return tuple(step.step_id for step in self._steps)

    @classmethod
    def build_default_steps(cls) -> tuple[VisualPipelineStep, ...]:
        """Build the full visual pipeline step sequence.

        Returns:
            Pipeline steps in visual normalizer specification order.
        """
        return (
            IngestValidationStep(),
            SemanticExtractionStep(),
            PlaceholderStep("02_mask_cleanup_morphology"),
            PlaceholderStep("03_region_analysis"),
            PlaceholderStep("04_terrain_transitions"),
            PlaceholderStep("05_forest_mass_renderer"),
            PlaceholderStep("06_road_brush_renderer"),
            PlaceholderStep("07_ruins_normalizer"),
            PlaceholderStep("08_affordance_maps"),
            PlaceholderStep("09_scene_stamping"),
            PlaceholderStep("10_decoration_scattering"),
            PlaceholderStep("11_layering_render_order"),
            PlaceholderStep("12_gameplay_validation"),
            PlaceholderStep("13_export_debug_output"),
        )

    def run(
        self,
        *,
        package: GeneratedMapPackage,
        runtime_map: RuntimeMap,
        output_dir: Path,
    ) -> VisualPipelineResult:
        """Run the configured visual pipeline.

        Args:
            package: Loaded source package.
            runtime_map: Runtime map built from gameplay source data.
            output_dir: Prepared-map output directory.

        Returns:
            Pipeline execution result.
        """
        context = VisualPipelineContext(
            package=package,
            runtime_map=runtime_map,
            output_dir=output_dir,
            config=self._config,
        )
        for step in self._steps:
            context = step.run(context)

        report = self._build_report(context)
        report_path = output_dir / self.REPORTS_DIR / self.REPORT_FILE
        if self._config.write_report:
            self._write_report(report_path, report)
        generated_artifacts = self._build_generated_artifacts(
            output_dir=output_dir,
            report_path=report_path,
            context=context,
        )
        return VisualPipelineResult(
            report_path=report_path,
            status=str(report["status"]),
            generated_artifacts=generated_artifacts,
            report=report,
        )


    def _build_generated_artifacts(
        self,
        *,
        output_dir: Path,
        report_path: Path,
        context: VisualPipelineContext,
    ) -> tuple[str, ...]:
        """Build relative generated artifact paths for persisted files.

        Args:
            output_dir: Prepared-map output directory.
            report_path: Persisted pipeline report path.
            context: Final pipeline context.

        Returns:
            Relative artifact paths in deterministic order.
        """
        artifacts: list[str] = [self._relative_path(report_path, output_dir=output_dir)]
        seen = set(artifacts)
        for artifact in context.artifacts.values():
            if artifact.path is None:
                continue
            relative_path = self._relative_path(artifact.path, output_dir=output_dir)
            if relative_path in seen:
                continue
            seen.add(relative_path)
            artifacts.append(relative_path)
        return tuple(artifacts)

    def _relative_path(self, path: Path, *, output_dir: Path) -> str:
        """Return a path relative to the output directory when possible.

        Args:
            path: Path to serialize.
            output_dir: Prepared-map output directory.

        Returns:
            Relative path string when the path is inside ``output_dir``.
        """
        try:
            return str(path.relative_to(output_dir))
        except ValueError:
            return str(path)

    def _build_report(self, context: VisualPipelineContext) -> dict[str, Any]:
        """Build the full pipeline report dictionary.

        Args:
            context: Final pipeline context.

        Returns:
            JSON-serializable pipeline report.
        """
        return {
            "schema_version": "visual-pipeline-report-v1",
            "status": self._build_status(context.reports),
            "pipeline": {
                "id": "visual_normalizer_v1",
                "version": context.config.pipeline_version,
                "implemented_steps": self._count_reports_by_status(context.reports, "ok"),
                "skipped_steps": self._count_reports_by_status(context.reports, "skipped"),
            },
            "prepared_by": {
                "project": "topdown-shooter",
                "version": __version__,
            },
            "source": {
                "format": (
                    "map_package"
                    if context.package.structured_map is not None
                    else "legacy tactical_map"
                ),
                "profile": context.package.manifest.profile,
                "resolved_seed": context.package.manifest.resolved_seed,
            },
            "dimensions": {
                "width_tiles": context.runtime_map.width_tiles,
                "height_tiles": context.runtime_map.height_tiles,
                "tile_size_px": context.runtime_map.tile_size_px,
            },
            "artifacts": [
                artifact.to_dict(output_dir=context.output_dir)
                for artifact in context.artifacts.values()
            ],
            "steps": [report.to_dict() for report in context.reports],
        }

    def _build_status(self, reports: list[PipelineStepReport]) -> str:
        """Build overall pipeline status from step reports.

        Args:
            reports: Step reports.

        Returns:
            Overall status label.
        """
        statuses = {report.status for report in reports}
        if "failed" in statuses:
            return "failed"
        if "warning" in statuses:
            return "warning"
        return "ok"

    def _count_reports_by_status(
        self,
        reports: list[PipelineStepReport],
        status: str,
    ) -> int:
        """Count reports with the requested status.

        Args:
            reports: Step reports.
            status: Status to count.

        Returns:
            Number of matching reports.
        """
        return sum(1 for report in reports if report.status == status)

    def _write_report(self, report_path: Path, report: dict[str, Any]) -> None:
        """Persist the pipeline report.

        Args:
            report_path: Destination report path.
            report: Report dictionary.

        Raises:
            InvalidMapPackageError: If writing fails.
        """
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise InvalidMapPackageError(
                f"Failed to write visual pipeline report: {report_path}: {exc}",
            ) from exc
