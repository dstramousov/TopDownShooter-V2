"""Small dependency-free PNG writer used by visual pipeline debug outputs."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

Color = tuple[int, int, int]


@dataclass(slots=True)
class RgbCanvas:
    """Simple RGB canvas with PNG export support.

    Attributes:
        width: Canvas width in pixels.
        height: Canvas height in pixels.
        background: Initial fill color.
    """

    width: int
    height: int
    background: Color = (0, 0, 0)
    _pixels: bytearray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate size and initialize pixel storage.

        Raises:
            ValueError: If the canvas dimensions are invalid.
        """
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Canvas dimensions must be positive.")
        self._pixels = bytearray(self.background * (self.width * self.height))

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        """Set one pixel when it is inside canvas bounds.

        Args:
            x: Pixel X coordinate.
            y: Pixel Y coordinate.
            color: RGB color.
        """
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        offset = (y * self.width + x) * 3
        self._pixels[offset:offset + 3] = bytes(color)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: Color) -> None:
        """Fill a rectangle clipped to canvas bounds.

        Args:
            x: Left pixel coordinate.
            y: Top pixel coordinate.
            width: Rectangle width.
            height: Rectangle height.
            color: RGB color.
        """
        left = max(0, x)
        top = max(0, y)
        right = min(self.width, x + width)
        bottom = min(self.height, y + height)
        if left >= right or top >= bottom:
            return
        row_bytes = bytes(color) * (right - left)
        for py in range(top, bottom):
            start = (py * self.width + left) * 3
            self._pixels[start:start + len(row_bytes)] = row_bytes

    def to_png_bytes(self) -> bytes:
        """Encode the canvas as PNG bytes.

        Returns:
            PNG-encoded image data.
        """
        rows = bytearray()
        row_stride = self.width * 3
        for row_index in range(self.height):
            rows.append(0)
            start = row_index * row_stride
            rows.extend(self._pixels[start:start + row_stride])
        return b"".join(
            [
                b"\x89PNG\r\n\x1a\n",
                self._png_chunk(
                    b"IHDR",
                    struct.pack(
                        ">IIBBBBB",
                        self.width,
                        self.height,
                        8,
                        2,
                        0,
                        0,
                        0,
                    ),
                ),
                self._png_chunk(b"IDAT", zlib.compress(bytes(rows), level=6)),
                self._png_chunk(b"IEND", b""),
            ],
        )

    def write_png(self, path: Path) -> None:
        """Write the canvas as a PNG file.

        Args:
            path: Destination path.

        Raises:
            OSError: If the file cannot be written.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.to_png_bytes())

    def _png_chunk(self, chunk_type: bytes, data: bytes) -> bytes:
        """Build one PNG chunk.

        Args:
            chunk_type: Four-byte PNG chunk type.
            data: Chunk payload.

        Returns:
            PNG chunk bytes.
        """
        checksum = zlib.crc32(chunk_type)
        checksum = zlib.crc32(data, checksum) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
