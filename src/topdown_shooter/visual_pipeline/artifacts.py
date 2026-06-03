"""Visual pipeline artifact contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PipelineArtifact:
    """Describes data or a file produced by a visual pipeline step.

    Attributes:
        artifact_id: Stable artifact identifier used by later steps.
        kind: Artifact kind, for example ``json_report`` or ``runtime_map``.
        path: Optional filesystem path when the artifact is persisted.
        data_key: Optional in-memory context key when the artifact is not persisted.
        description: Human-readable artifact description.
    """

    artifact_id: str
    kind: str
    path: Path | None = None
    data_key: str | None = None
    description: str = ""

    def to_dict(self, *, output_dir: Path | None = None) -> dict[str, Any]:
        """Serialize the artifact to a deterministic dictionary.

        Args:
            output_dir: Optional output root used to make persisted paths relative.

        Returns:
            JSON-serializable artifact dictionary.
        """
        serialized: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "description": self.description,
        }
        if self.data_key is not None:
            serialized["data_key"] = self.data_key
        if self.path is not None:
            serialized["path"] = self._serialize_path(self.path, output_dir=output_dir)
        return serialized

    def _serialize_path(self, path: Path, *, output_dir: Path | None) -> str:
        """Serialize a path relative to the output directory when possible.

        Args:
            path: Path to serialize.
            output_dir: Optional output root.

        Returns:
            String path.
        """
        if output_dir is None:
            return str(path)
        try:
            return str(path.relative_to(output_dir))
        except ValueError:
            return str(path)
