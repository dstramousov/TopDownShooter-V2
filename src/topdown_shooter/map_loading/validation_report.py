"""Validation report model for generated map packages."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Validation issue reported by the generator.

    Attributes:
        code: Stable issue code.
        level: Issue level.
        details: Raw issue details.
    """

    code: str
    level: str
    details: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationIssue":
        """Create a validation issue from raw data.

        Args:
            data: Raw issue dictionary.

        Returns:
            Parsed validation issue.
        """
        return cls(
            code=str(data.get("code", "unknown")),
            level=str(data.get("level", "unknown")),
            details=dict(data.get("details", {})),
        )


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Generator-side validation report.

    Attributes:
        status: Validation status.
        errors: Reported errors.
        warnings: Reported warnings.
        raw: Original report dictionary.
    """

    status: str
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationReport":
        """Create a validation report from a raw dictionary.

        Args:
            data: Raw report dictionary.

        Returns:
            Parsed validation report.
        """
        return cls(
            status=str(data.get("status", "unknown")),
            errors=[ValidationIssue.from_dict(item) for item in data.get("errors", [])],
            warnings=[ValidationIssue.from_dict(item) for item in data.get("warnings", [])],
            raw=data,
        )

    @property
    def has_blocking_errors(self) -> bool:
        """Return whether the report contains blocking validation errors."""
        return self.status == "failed" or bool(self.errors)
