"""Command line interface for TopDownShooter V.2."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from topdown_shooter.app.inspect_map import inspect_map_package
from topdown_shooter.map_loading.errors import MapPackageError

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
    parser.add_argument(
        "--inspect-map",
        action="store_true",
        help="Inspect the generated map package and exit.",
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

    if not args.inspect_map:
        parser.error("Only --inspect-map is supported in version 0.0.2.")

    try:
        summary = inspect_map_package(args.map_package_dir)
    except MapPackageError as exc:
        sys.stderr.write(f"ERROR: Map package inspection failed:\n{exc}\n")
        return 1

    sys.stdout.write(f"{summary}\n")
    return 0
