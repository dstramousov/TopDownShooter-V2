"""Visual pipeline configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VisualPipelineConfig:
    """Configuration for the visual pipeline skeleton.

    Attributes:
        pipeline_version: Version label written to reports.
        strict_tile_size_px: Required logical tile size in pixels.
        write_report: Whether the pipeline should persist its report.
    """

    pipeline_version: str = "visual-pipeline-v1"
    strict_tile_size_px: int = 16
    write_report: bool = True
