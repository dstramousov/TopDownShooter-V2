"""Tile color palette for the raylib renderer."""

from __future__ import annotations


def build_tile_palette(raylib: object) -> dict[str, object]:
    """Build the tile color palette.

    Args:
        raylib: Imported pyray module.

    Returns:
        Mapping from tile symbol to raylib color.
    """
    return {
        "+": raylib.Color(56, 111, 59, 255),
        ".": raylib.Color(105, 128, 73, 255),
        "T": raylib.Color(22, 62, 32, 255),
        "#": raylib.Color(64, 64, 64, 255),
        "c": raylib.Color(122, 105, 72, 255),
        "b": raylib.Color(95, 82, 62, 255),
        "R": raylib.Color(119, 119, 119, 255),
        "f": raylib.Color(52, 83, 53, 255),
        "m": raylib.Color(72, 68, 52, 255),
        "w": raylib.Color(56, 84, 126, 255),
        "S": raylib.Color(68, 190, 92, 255),
        "G": raylib.Color(205, 177, 72, 255),
    }
