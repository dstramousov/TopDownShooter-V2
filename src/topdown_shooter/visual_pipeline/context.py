"""Visual pipeline execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.visual_pipeline.artifacts import PipelineArtifact
from topdown_shooter.visual_pipeline.config import VisualPipelineConfig
from topdown_shooter.visual_pipeline.reports import PipelineStepReport
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(slots=True)
class VisualPipelineContext:
    """Mutable execution context shared by visual pipeline steps.

    Attributes:
        package: Loaded generator package.
        runtime_map: Runtime map built from source gameplay data.
        output_dir: Prepared-map output directory.
        config: Visual pipeline configuration.
        memory: In-memory step data keyed by stable names.
        artifacts: Produced artifacts keyed by artifact id.
        reports: Step reports in execution order.
    """

    package: GeneratedMapPackage
    runtime_map: RuntimeMap
    output_dir: Path
    config: VisualPipelineConfig = field(default_factory=VisualPipelineConfig)
    memory: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, PipelineArtifact] = field(default_factory=dict)
    reports: list[PipelineStepReport] = field(default_factory=list)

    def add_artifact(self, artifact: PipelineArtifact) -> None:
        """Register a produced artifact.

        Args:
            artifact: Artifact to register.
        """
        self.artifacts[artifact.artifact_id] = artifact

    def add_report(self, report: PipelineStepReport) -> None:
        """Append a step report and register its output artifacts.

        Args:
            report: Step report to append.
        """
        self.reports.append(report)
        for artifact in report.outputs:
            self.add_artifact(artifact)

    def artifact_ids(self) -> tuple[str, ...]:
        """Return known artifact ids in deterministic insertion order.

        Returns:
            Artifact ids.
        """
        return tuple(self.artifacts.keys())
