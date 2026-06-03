"""Visual pipeline report contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from topdown_shooter.visual_pipeline.artifacts import PipelineArtifact

PipelineStepStatus = Literal["ok", "warning", "failed", "skipped"]


@dataclass(frozen=True, slots=True)
class PipelineStepReport:
    """Report produced by one visual pipeline step.

    Attributes:
        step_id: Stable step identifier.
        status: Step execution status.
        inputs: Artifact identifiers consumed by the step.
        outputs: Artifacts produced by the step.
        warnings: Non-blocking step warnings.
        errors: Blocking step errors.
        stats: Step-specific scalar statistics.
    """

    step_id: str
    status: PipelineStepStatus
    inputs: tuple[str, ...] = ()
    outputs: tuple[PipelineArtifact, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    stats: dict[str, int | float | str | bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report to a deterministic dictionary.

        Returns:
            JSON-serializable report dictionary.
        """
        return {
            "step_id": self.step_id,
            "status": self.status,
            "inputs": list(self.inputs),
            "outputs": [artifact.to_dict() for artifact in self.outputs],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "stats": dict(self.stats),
        }
