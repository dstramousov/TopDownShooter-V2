"""Binary morphology helpers for visual-only mask processing."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from topdown_shooter.visual_pipeline.masks import MaskRows


@dataclass(frozen=True, slots=True)
class BinaryMorphology:
    """Apply dependency-free binary morphology to tile-aligned masks."""

    def dilate(self, rows: MaskRows, *, radius: int = 1) -> MaskRows:
        """Dilate a binary mask with a square structuring element.

        Args:
            rows: Source mask rows.
            radius: Chebyshev radius in tiles.

        Returns:
            Dilated mask rows.

        Raises:
            ValueError: If ``radius`` is negative or rows are not rectangular.
        """
        self._validate(rows)
        if radius < 0:
            raise ValueError("Morphology radius must not be negative.")
        if radius == 0 or not rows:
            return rows
        height = len(rows)
        width = len(rows[0])
        output: list[tuple[bool, ...]] = []
        for y in range(height):
            output_row: list[bool] = []
            for x in range(width):
                output_row.append(self._any_active_near(rows, x=x, y=y, radius=radius))
            output.append(tuple(output_row))
        return tuple(output)

    def erode(self, rows: MaskRows, *, radius: int = 1) -> MaskRows:
        """Erode a binary mask with a square structuring element.

        Args:
            rows: Source mask rows.
            radius: Chebyshev radius in tiles.

        Returns:
            Eroded mask rows.

        Raises:
            ValueError: If ``radius`` is negative or rows are not rectangular.
        """
        self._validate(rows)
        if radius < 0:
            raise ValueError("Morphology radius must not be negative.")
        if radius == 0 or not rows:
            return rows
        height = len(rows)
        width = len(rows[0])
        output: list[tuple[bool, ...]] = []
        for y in range(height):
            output_row: list[bool] = []
            for x in range(width):
                output_row.append(self._all_active_near(rows, x=x, y=y, radius=radius))
            output.append(tuple(output_row))
        return tuple(output)

    def opening(self, rows: MaskRows, *, radius: int = 1) -> MaskRows:
        """Open a binary mask by erosion followed by dilation.

        Args:
            rows: Source mask rows.
            radius: Chebyshev radius in tiles.

        Returns:
            Opened mask rows.
        """
        return self.dilate(self.erode(rows, radius=radius), radius=radius)

    def closing(self, rows: MaskRows, *, radius: int = 1) -> MaskRows:
        """Close a binary mask by dilation followed by erosion.

        Args:
            rows: Source mask rows.
            radius: Chebyshev radius in tiles.

        Returns:
            Closed mask rows.
        """
        return self.erode(self.dilate(rows, radius=radius), radius=radius)

    def fill_small_holes(self, rows: MaskRows, *, max_area_tiles: int) -> MaskRows:
        """Fill inactive connected components that do not touch map borders.

        Args:
            rows: Source mask rows.
            max_area_tiles: Maximum hole area to fill.

        Returns:
            Mask rows with small internal holes filled.

        Raises:
            ValueError: If ``max_area_tiles`` is negative or rows are invalid.
        """
        self._validate(rows)
        if max_area_tiles < 0:
            raise ValueError("Maximum hole area must not be negative.")
        if max_area_tiles == 0 or not rows:
            return rows
        mutable = [list(row) for row in rows]
        for component in self._components(rows, active_value=False):
            if component.touches_border or len(component.cells) > max_area_tiles:
                continue
            for x, y in component.cells:
                mutable[y][x] = True
        return tuple(tuple(row) for row in mutable)

    def remove_small_objects(self, rows: MaskRows, *, min_area_tiles: int) -> MaskRows:
        """Remove active connected components smaller than a threshold.

        Args:
            rows: Source mask rows.
            min_area_tiles: Minimum kept component area.

        Returns:
            Mask rows with tiny active components removed.

        Raises:
            ValueError: If ``min_area_tiles`` is negative or rows are invalid.
        """
        self._validate(rows)
        if min_area_tiles < 0:
            raise ValueError("Minimum object area must not be negative.")
        if min_area_tiles <= 1 or not rows:
            return rows
        mutable = [list(row) for row in rows]
        for component in self._components(rows, active_value=True):
            if len(component.cells) >= min_area_tiles:
                continue
            for x, y in component.cells:
                mutable[y][x] = False
        return tuple(tuple(row) for row in mutable)

    def difference(self, left: MaskRows, right: MaskRows) -> MaskRows:
        """Return cells active in ``left`` and inactive in ``right``.

        Args:
            left: Left mask rows.
            right: Right mask rows.

        Returns:
            Difference mask rows.
        """
        self._validate_same_shape(left, right)
        return tuple(
            tuple(left_value and not right_value for left_value, right_value in zip(left_row, right_row))
            for left_row, right_row in zip(left, right)
        )

    def intersection(self, left: MaskRows, right: MaskRows) -> MaskRows:
        """Return cells active in both masks.

        Args:
            left: Left mask rows.
            right: Right mask rows.

        Returns:
            Intersection mask rows.
        """
        self._validate_same_shape(left, right)
        return tuple(
            tuple(left_value and right_value for left_value, right_value in zip(left_row, right_row))
            for left_row, right_row in zip(left, right)
        )

    def union(self, left: MaskRows, right: MaskRows) -> MaskRows:
        """Return cells active in either mask.

        Args:
            left: Left mask rows.
            right: Right mask rows.

        Returns:
            Union mask rows.
        """
        self._validate_same_shape(left, right)
        return tuple(
            tuple(left_value or right_value for left_value, right_value in zip(left_row, right_row))
            for left_row, right_row in zip(left, right)
        )

    def _validate_same_shape(self, left: MaskRows, right: MaskRows) -> None:
        """Validate that two masks have the same rectangular shape."""
        self._validate(left)
        self._validate(right)
        if len(left) != len(right):
            raise ValueError("Mask heights must match.")
        if left and len(left[0]) != len(right[0]):
            raise ValueError("Mask widths must match.")

    def _validate(self, rows: MaskRows) -> None:
        """Validate that rows form a rectangular mask."""
        if not rows:
            return
        width = len(rows[0])
        for row in rows:
            if len(row) != width:
                raise ValueError("Mask rows must be rectangular.")

    def _any_active_near(self, rows: MaskRows, *, x: int, y: int, radius: int) -> bool:
        """Return whether any nearby source cell is active."""
        height = len(rows)
        width = len(rows[0])
        for ny in range(max(0, y - radius), min(height, y + radius + 1)):
            for nx in range(max(0, x - radius), min(width, x + radius + 1)):
                if rows[ny][nx]:
                    return True
        return False

    def _all_active_near(self, rows: MaskRows, *, x: int, y: int, radius: int) -> bool:
        """Return whether every nearby source cell is active and inside bounds."""
        height = len(rows)
        width = len(rows[0])
        if x - radius < 0 or y - radius < 0:
            return False
        if x + radius >= width or y + radius >= height:
            return False
        for ny in range(y - radius, y + radius + 1):
            for nx in range(x - radius, x + radius + 1):
                if not rows[ny][nx]:
                    return False
        return True

    def _components(self, rows: MaskRows, *, active_value: bool) -> tuple["_Component", ...]:
        """Return 4-connected components for the requested value."""
        if not rows:
            return ()
        height = len(rows)
        width = len(rows[0])
        visited: set[tuple[int, int]] = set()
        components: list[_Component] = []
        for y in range(height):
            for x in range(width):
                if (x, y) in visited or rows[y][x] is not active_value:
                    continue
                components.append(
                    self._flood_component(
                        rows,
                        x=x,
                        y=y,
                        active_value=active_value,
                        visited=visited,
                    ),
                )
        return tuple(components)

    def _flood_component(
        self,
        rows: MaskRows,
        *,
        x: int,
        y: int,
        active_value: bool,
        visited: set[tuple[int, int]],
    ) -> "_Component":
        """Flood-fill one 4-connected component."""
        height = len(rows)
        width = len(rows[0])
        queue: deque[tuple[int, int]] = deque([(x, y)])
        visited.add((x, y))
        cells: list[tuple[int, int]] = []
        touches_border = False
        while queue:
            current_x, current_y = queue.popleft()
            cells.append((current_x, current_y))
            if (
                current_x == 0
                or current_y == 0
                or current_x == width - 1
                or current_y == height - 1
            ):
                touches_border = True
            for next_x, next_y in self._neighbors4(current_x, current_y, width=width, height=height):
                if (next_x, next_y) in visited or rows[next_y][next_x] is not active_value:
                    continue
                visited.add((next_x, next_y))
                queue.append((next_x, next_y))
        return _Component(cells=tuple(cells), touches_border=touches_border)

    def _neighbors4(
        self,
        x: int,
        y: int,
        *,
        width: int,
        height: int,
    ) -> tuple[tuple[int, int], ...]:
        """Return in-bounds 4-connected neighbors."""
        neighbors: list[tuple[int, int]] = []
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            neighbors.append((nx, ny))
        return tuple(neighbors)


@dataclass(frozen=True, slots=True)
class _Component:
    """Connected component data used by morphology helpers."""

    cells: tuple[tuple[int, int], ...]
    touches_border: bool
