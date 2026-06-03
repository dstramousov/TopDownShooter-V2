"""Placeholder steps for the full visual pipeline contract."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.visual_pipeline.context import VisualPipelineContext
from topdown_shooter.visual_pipeline.reports import PipelineStepReport


@dataclass(frozen=True, slots=True)
class PlaceholderStep:
    """Pipeline step placeholder used until a stage is implemented.

    Attributes:
        step_id: Stable step identifier.
        reason: Explanation written to the pipeline report.
    """

    step_id: str
    reason: str = "not implemented in this MVP"

    def run(self, context: VisualPipelineContext) -> VisualPipelineContext:
        """Record that this pipeline stage is intentionally skipped.

        Args:
            context: Current visual pipeline context.

        Returns:
            Unchanged visual pipeline context with an appended skipped report.
        """
        context.add_report(
            PipelineStepReport(
                step_id=self.step_id,
                status="skipped",
                inputs=context.artifact_ids(),
                warnings=(self.reason,),
            ),
        )
        return context
