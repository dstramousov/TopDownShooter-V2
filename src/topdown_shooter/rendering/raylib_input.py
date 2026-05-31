"""Shared raylib input helpers."""

from __future__ import annotations


class InvalidRaylibBindingError(RuntimeError):
    """Raised when a configured raylib binding cannot be resolved."""


class RaylibInputResolver:
    """Resolve configured raylib input bindings by constant name."""

    def __init__(self, raylib: object) -> None:
        """Initialize the resolver.

        Args:
            raylib: Imported pyray module.
        """
        self._raylib = raylib

    def key(self, key_name: str) -> int:
        """Resolve a raylib key constant by name.

        Args:
            key_name: Raylib key constant name.

        Returns:
            Resolved raylib key constant.

        Raises:
            InvalidRaylibBindingError: If the key is not available.
        """
        key_value = getattr(self._raylib, key_name, None)
        if not isinstance(key_value, int):
            raise InvalidRaylibBindingError(
                f"Unknown raylib key binding in runtime config: {key_name}",
            )
        return key_value

    def optional_key(self, key_name: str) -> int:
        """Resolve a key constant and return ``-1`` when it is unavailable."""
        try:
            return self.key(key_name)
        except InvalidRaylibBindingError:
            return -1

    def mouse_button(self, button_name: str) -> int:
        """Resolve a raylib mouse button constant by name.

        Args:
            button_name: Raylib mouse button constant name.

        Returns:
            Resolved raylib mouse button constant.

        Raises:
            InvalidRaylibBindingError: If the button is not available.
        """
        button_value = getattr(self._raylib, button_name, None)
        if not isinstance(button_value, int):
            raise InvalidRaylibBindingError(
                f"Unknown raylib mouse binding in runtime config: {button_name}",
            )
        return button_value

    def optional_mouse_button(self, button_name: str) -> int:
        """Resolve a mouse button and return ``0`` when it is unavailable."""
        try:
            return self.mouse_button(button_name)
        except InvalidRaylibBindingError:
            return 0

    def keys(self, key_names: tuple[str, ...]) -> tuple[int, ...]:
        """Resolve multiple raylib key constants by name."""
        return tuple(self.key(key_name) for key_name in key_names)

def is_any_key_down(raylib: object, keys: tuple[int, ...]) -> bool:
    """Return whether any key in ``keys`` is held down."""
    return any(raylib.is_key_down(key) for key in keys)


def configure_raylib_logging(raylib: object) -> None:
    """Reduce raylib logging noise before opening a window."""
    set_level = getattr(raylib, "set_trace_log_level", None)
    warning_level = getattr(raylib, "LOG_WARNING", None)
    if callable(set_level) and isinstance(warning_level, int):
        set_level(warning_level)
