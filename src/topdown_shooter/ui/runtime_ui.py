"""Shared modal runtime UI for 2D and 3D gameplay modes."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.config.runtime_config import RuntimeConfig
from topdown_shooter.rendering.raylib_input import RaylibInputResolver, is_key_chord_pressed
from topdown_shooter.rendering.text import RaylibTextRenderer


@dataclass(frozen=True, slots=True)
class ControlsHelpLine:
    """Single controls help row.

    Attributes:
        binding: Human-readable key or mouse binding.
        description: Human-readable action description.
    """

    binding: str
    description: str


@dataclass(frozen=True, slots=True)
class RuntimeUiInput:
    """Runtime UI input result for the current frame.

    Attributes:
        should_exit: Whether the application should close.
        blocks_gameplay: Whether gameplay update should be paused this frame.
    """

    should_exit: bool
    blocks_gameplay: bool


@dataclass(frozen=True, slots=True)
class _ButtonRect:
    """Simple screen-space button rectangle."""

    x: int
    y: int
    width: int
    height: int

    def contains(self, px: float, py: float) -> bool:
        """Return whether a point is inside the rectangle."""
        return (
            float(self.x) <= px <= float(self.x + self.width)
            and float(self.y) <= py <= float(self.y + self.height)
        )


class RuntimeUi:
    """Draw and handle shared modal gameplay UI.

    The class owns UI state that must be identical across 2D and 3D modes:
    controls help, exit confirmation and debug overlay toggle state.
    """

    _OVERLAY_WIDTH = 760
    _HELP_TITLE = "Controls"
    _EXIT_TITLE = "Exit?"
    _YES_LABEL = "Yes"
    _NO_LABEL = "No"

    def __init__(
        self,
        raylib: object,
        config: RuntimeConfig,
        renderer_name: str,
        help_lines: tuple[ControlsHelpLine, ...],
    ) -> None:
        """Initialize shared runtime UI.

        Args:
            raylib: Imported pyray module.
            config: Runtime configuration.
            renderer_name: Human-readable renderer name.
            help_lines: Controls help rows for the current renderer mode.
        """
        self._raylib = raylib
        self._config = config
        self._renderer_name = renderer_name
        self._help_lines = help_lines
        self._text = RaylibTextRenderer(
            raylib=raylib,
            font_path=config.debug_overlay.font_path,
            font_spacing=config.debug_overlay.font_spacing,
        )
        self._debug_overlay_enabled = config.debug_overlay.enabled_by_default
        self._help_visible = False
        self._exit_confirm_visible = False
        self._exit_yes_selected = False
        self._yes_button = _ButtonRect(0, 0, 0, 0)
        self._no_button = _ButtonRect(0, 0, 0, 0)
        self._input = RaylibInputResolver(raylib)
        self._debug_key = self._input.optional_key(config.controls.debug_overlay.key)
        self._debug_modifiers = tuple(
            self._input.optional_key(modifier)
            for modifier in config.controls.debug_overlay.modifiers
        )
        self._help_key = self._input.optional_key(config.controls.help)
        self._quit_key = self._input.optional_key(config.controls.quit)
        self._enter_key = self._input.optional_key("KEY_ENTER")
        self._left_key = self._input.optional_key("KEY_LEFT")
        self._right_key = self._input.optional_key("KEY_RIGHT")
        self._a_key = self._input.optional_key("KEY_A")
        self._d_key = self._input.optional_key("KEY_D")
        self._mouse_left_button = self._input.optional_mouse_button("MOUSE_BUTTON_LEFT")

    @property
    def debug_overlay_enabled(self) -> bool:
        """Return whether the shared debug overlay should be drawn."""
        return self._debug_overlay_enabled

    def handle_input(self) -> RuntimeUiInput:
        """Handle modal UI input for the current frame.

        Returns:
            Input result that tells the caller whether to exit or pause gameplay.
        """
        should_exit = False
        if is_key_chord_pressed(self._raylib, self._debug_key, self._debug_modifiers):
            self._debug_overlay_enabled = not self._debug_overlay_enabled

        if self._raylib.is_key_pressed(self._help_key):
            self._help_visible = not self._help_visible
            if self._help_visible:
                self._exit_confirm_visible = False

        if self._raylib.is_key_pressed(self._quit_key):
            if self._exit_confirm_visible:
                self._exit_confirm_visible = False
            else:
                self._help_visible = False
                self._exit_confirm_visible = True
                self._exit_yes_selected = False

        if self._exit_confirm_visible:
            should_exit = self._handle_exit_confirm_input()

        return RuntimeUiInput(
            should_exit=should_exit,
            blocks_gameplay=self._help_visible or self._exit_confirm_visible,
        )

    def draw(self) -> None:
        """Draw visible modal UI."""
        if self._help_visible:
            self._draw_help_overlay()
        if self._exit_confirm_visible:
            self._draw_exit_confirmation()

    def unload(self) -> None:
        """Unload optional raylib resources owned by the UI."""
        self._text.unload()

    def _handle_exit_confirm_input(self) -> bool:
        """Handle exit confirmation input.

        Returns:
            Whether the user confirmed application exit.
        """
        if (
            self._raylib.is_key_pressed(self._left_key)
            or self._raylib.is_key_pressed(self._right_key)
            or self._raylib.is_key_pressed(self._a_key)
            or self._raylib.is_key_pressed(self._d_key)
        ):
            self._exit_yes_selected = not self._exit_yes_selected

        if self._raylib.is_key_pressed(self._enter_key):
            if self._exit_yes_selected:
                return True
            self._exit_confirm_visible = False
            return False

        if self._raylib.is_mouse_button_pressed(self._mouse_left_button):
            mouse = self._raylib.get_mouse_position()
            if self._yes_button.contains(float(mouse.x), float(mouse.y)):
                return True
            if self._no_button.contains(float(mouse.x), float(mouse.y)):
                self._exit_confirm_visible = False
                return False

        return False

    def _draw_help_overlay(self) -> None:
        """Draw the centered controls overlay."""
        config = self._config.debug_overlay
        font_size = config.font_size
        line_height = font_size + config.line_spacing
        title_height = font_size + config.section_spacing
        body_height = max(1, len(self._help_lines)) * line_height
        footer_height = line_height + config.section_spacing
        panel_width = min(self._OVERLAY_WIDTH, max(360, self._config.window.width - 80))
        panel_height = (
            config.padding * 2
            + title_height
            + body_height
            + footer_height
        )
        x = max(20, (self._config.window.width - panel_width) // 2)
        y = max(20, (self._config.window.height - panel_height) // 2)
        self._draw_panel(x, y, panel_width, panel_height)

        text_x = x + config.padding
        cursor_y = y + config.padding
        self._draw_text(
            f"{self._HELP_TITLE} - {self._renderer_name}",
            text_x,
            cursor_y,
            font_size,
            self._raylib.RAYWHITE,
        )
        cursor_y += title_height
        label_width = min(220, max(120, panel_width // 3))
        for line in self._help_lines:
            self._draw_text(line.binding, text_x, cursor_y, font_size, self._raylib.YELLOW)
            self._draw_text(
                line.description,
                text_x + label_width,
                cursor_y,
                font_size,
                self._raylib.RAYWHITE,
            )
            cursor_y += line_height
        cursor_y += config.section_spacing
        self._draw_text(
            "F1: close help / resume",
            text_x,
            cursor_y,
            font_size,
            self._raylib.LIGHTGRAY,
        )

    def _draw_exit_confirmation(self) -> None:
        """Draw the centered exit confirmation dialog."""
        config = self._config.debug_overlay
        font_size = config.font_size
        panel_width = 420
        panel_height = 170
        x = max(20, (self._config.window.width - panel_width) // 2)
        y = max(20, (self._config.window.height - panel_height) // 2)
        self._draw_panel(x, y, panel_width, panel_height)

        title_width = self._text.measure_text(self._EXIT_TITLE, font_size)
        self._draw_text(
            self._EXIT_TITLE,
            x + (panel_width - title_width) // 2,
            y + config.padding,
            font_size,
            self._raylib.RAYWHITE,
        )

        button_width = 120
        button_height = 42
        gap = 28
        buttons_total_width = button_width * 2 + gap
        button_y = y + panel_height - config.padding - button_height
        yes_x = x + (panel_width - buttons_total_width) // 2
        no_x = yes_x + button_width + gap
        self._yes_button = _ButtonRect(yes_x, button_y, button_width, button_height)
        self._no_button = _ButtonRect(no_x, button_y, button_width, button_height)
        self._draw_button(self._yes_button, self._YES_LABEL, selected=self._exit_yes_selected)
        self._draw_button(self._no_button, self._NO_LABEL, selected=not self._exit_yes_selected)

    def _draw_panel(self, x: int, y: int, width: int, height: int) -> None:
        """Draw a semi-transparent panel rectangle."""
        background = self._raylib.Color(0, 0, 0, self._config.debug_overlay.background_alpha)
        border = self._raylib.Color(220, 220, 220, 210)
        self._raylib.draw_rectangle(x, y, width, height, background)
        self._raylib.draw_rectangle_lines(x, y, width, height, border)

    def _draw_button(self, rect: _ButtonRect, label: str, *, selected: bool) -> None:
        """Draw a dialog button."""
        fill = self._raylib.Color(70, 70, 70, 235) if selected else self._raylib.Color(25, 25, 25, 220)
        border = self._raylib.YELLOW if selected else self._raylib.LIGHTGRAY
        self._raylib.draw_rectangle(rect.x, rect.y, rect.width, rect.height, fill)
        self._raylib.draw_rectangle_lines(rect.x, rect.y, rect.width, rect.height, border)
        font_size = self._config.debug_overlay.font_size
        text_width = self._text.measure_text(label, font_size)
        self._draw_text(
            label,
            rect.x + (rect.width - text_width) // 2,
            rect.y + (rect.height - font_size) // 2,
            font_size,
            self._raylib.RAYWHITE,
        )

    def _draw_text(self, text: str, x: int, y: int, font_size: int, color: object) -> None:
        """Draw text with the shared configured font."""
        self._text.draw_text(text, x, y, font_size, color)
