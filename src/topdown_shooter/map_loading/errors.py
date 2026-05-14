"""Errors raised while loading generated map packages."""


class MapPackageError(RuntimeError):
    """Base error for invalid generated map packages."""


class MissingMapPackageFileError(MapPackageError):
    """Raised when a required map package file is missing."""


class InvalidMapPackageError(MapPackageError):
    """Raised when a map package cannot be used by the runtime."""
