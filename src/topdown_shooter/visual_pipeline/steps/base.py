"""Base protocol for visual pipeline steps."""

from __future__ import annotations

from typing import Protocol

from topdown_shooter.visual_pipeline.context import VisualPipelineContext


class VisualPipelineStep(Protocol):
    """Protocol implemented by all visual pipeline steps."""

    step_id: str

    def run(self, context: VisualPipelineContext) -> VisualPipelineContext:
        """Run the pipeline step.

        Args:
            context: Current visual pipeline context.

        Returns:
            Updated visual pipeline context.
        """
