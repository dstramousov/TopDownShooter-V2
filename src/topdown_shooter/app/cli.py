"""Command line interface for TopDownShooter V.2."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from topdown_shooter.app.inspect_map import inspect_map_package
from topdown_shooter.app.run_game import run_game
from topdown_shooter.config.runtime_config import RuntimeConfigError
from topdown_shooter.map_loading.errors import MapPackageError
from topdown_shooter.rendering.raylib_window import (
    InvalidControlBindingError,
    RaylibUnavailableError,
)

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(prog="topdown-shooter")
    parser.add_argument(
        "--map",
        dest="map_package_dir",
        type=Path,
        required=True,
        help="Path to a generated TopDownMapGen package directory.",
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--inspect-map",
        action="store_true",
        help="Inspect the generated map package and exit.",
    )
    mode_group.add_argument(
        "--run",
        action="store_true",
        help="Open a minimal raylib window and render the generated map.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface.

    Args:
        argv: Optional argument vector. Uses process arguments when omitted.

    Returns:
        Process exit code.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.inspect_map:
            summary = inspect_map_package(args.map_package_dir)
            sys.stdout.write(f"{summary}\n")
            return 0
        run_game(args.map_package_dir)
        return 0
    except MapPackageError as exc:
        sys.stderr.write(f"ERROR: Map package operation failed:\n{exc}\n")
        return 1
    except (RuntimeConfigError, RaylibUnavailableError, InvalidControlBindingError) as exc:
        sys.stderr.write(f"ERROR: Rendering failed:\n{exc}\n")
        return 1
