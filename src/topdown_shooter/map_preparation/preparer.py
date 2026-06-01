"""Prepared map package builder."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from topdown_shooter import __version__
from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage, MapPackageLoader
from topdown_shooter.world.runtime_map import RuntimeMap
from topdown_shooter.world.runtime_map_builder import RuntimeMapBuilder


@dataclass(frozen=True, slots=True)
class PreparedMapResult:
    """Result of a prepared map build.

    Attributes:
        output_dir: Directory containing the prepared map package.
        manifest_path: Written prepared-map manifest path.
        report_path: Written preparation report path.
        summary_path: Written human-readable preparation summary path.
        status: Overall preparation status.
        copied_artifacts: Relative artifact paths copied into the prepared package.
        visual_map_present: Whether a visual map export was found in the source package.
        structured_map_present: Whether a structured ``map_package/`` export was found.
    """

    output_dir: Path
    manifest_path: Path
    report_path: Path
    summary_path: Path
    status: str
    copied_artifacts: tuple[str, ...]
    visual_map_present: bool
    structured_map_present: bool


class MapPreparationService:
    """Build a runtime-ready prepared map package from generator output."""

    PREPARED_MANIFEST_FILE = "manifest.json"
    REPORTS_DIR = "reports"
    PREPARATION_REPORT_FILE = "preparation_report.json"
    PREPARATION_SUMMARY_FILE = "preparation_summary.txt"

    def __init__(
        self,
        *,
        loader: MapPackageLoader | None = None,
        runtime_builder: RuntimeMapBuilder | None = None,
    ) -> None:
        """Initialize the preparation service.

        Args:
            loader: Optional package loader override for tests.
            runtime_builder: Optional runtime map builder override for tests.
        """
        self._loader = loader or MapPackageLoader()
        self._runtime_builder = runtime_builder or RuntimeMapBuilder()

    def prepare(self, source_dir: Path, output_dir: Path) -> PreparedMapResult:
        """Prepare a generated map package for runtime consumption.

        Args:
            source_dir: Generated TopDownMapGen output directory.
            output_dir: Destination prepared-map directory.

        Returns:
            Preparation result with written artifact paths.

        Raises:
            InvalidMapPackageError: If source and output paths are unsafe or writing fails.
        """
        resolved_source_dir = source_dir.expanduser().resolve()
        resolved_output_dir = output_dir.expanduser().resolve()
        if resolved_source_dir == resolved_output_dir:
            raise InvalidMapPackageError("Prepared map output must differ from source map path.")

        package = self._loader.load(resolved_source_dir)
        runtime_map = self._runtime_builder.build(package)
        self._ensure_output_dir(resolved_output_dir)

        copied_artifacts = self._copy_runtime_artifacts(
            package=package,
            output_dir=resolved_output_dir,
        )
        visual_summary = self._build_visual_map_summary(package.package_dir)
        report = self._build_preparation_report(
            package=package,
            runtime_map=runtime_map,
            output_dir=resolved_output_dir,
            copied_artifacts=copied_artifacts,
            visual_summary=visual_summary,
        )
        manifest = self._build_prepared_manifest(
            package=package,
            runtime_map=runtime_map,
            output_dir=resolved_output_dir,
            copied_artifacts=copied_artifacts,
            report=report,
        )

        reports_dir = resolved_output_dir / self.REPORTS_DIR
        reports_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = resolved_output_dir / self.PREPARED_MANIFEST_FILE
        report_path = reports_dir / self.PREPARATION_REPORT_FILE
        summary_path = reports_dir / self.PREPARATION_SUMMARY_FILE

        self._write_json(manifest_path, manifest)
        self._write_json(report_path, report)
        summary = self.format_summary(report)
        self._write_text(summary_path, summary)

        return PreparedMapResult(
            output_dir=resolved_output_dir,
            manifest_path=manifest_path,
            report_path=report_path,
            summary_path=summary_path,
            status=str(report["status"]),
            copied_artifacts=tuple(copied_artifacts),
            visual_map_present=bool(visual_summary["present"]),
            structured_map_present=package.structured_map is not None,
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format a human-readable preparation summary.

        Args:
            report: Preparation report dictionary.

        Returns:
            Summary text suitable for CLI output.
        """
        source = self._require_report_dict(report, "source")
        dimensions = self._require_report_dict(report, "dimensions")
        visual = self._require_report_dict(report, "visual_map")
        output = self._require_report_dict(report, "output")
        copied_artifacts = output.get("copied_artifacts", [])
        copied_count = len(copied_artifacts) if isinstance(copied_artifacts, list) else 0
        visual_state = "present" if visual.get("present") is True else "missing"
        contract_state = str(visual.get("contract_status", "skipped"))

        return "\n".join(
            [
                "Map preparation completed",
                f"- status: {report.get('status', 'unknown')}",
                f"- source format: {source.get('format', 'unknown')}",
                f"- generator: {source.get('generator_version', 'unknown')}",
                f"- profile: {source.get('profile', 'unknown')}",
                (
                    "- size: "
                    f"{dimensions.get('width_tiles', 'unknown')}x"
                    f"{dimensions.get('height_tiles', 'unknown')}"
                    f" @ {dimensions.get('tile_size_px', 'unknown')} px"
                ),
                f"- visual map: {visual_state}",
                f"- visual contract: {contract_state}",
                f"- copied artifacts: {copied_count}",
                f"- output: {output.get('path', 'unknown')}",
                f"- report: {output.get('report_path', 'unknown')}",
            ],
        )

    def _ensure_output_dir(self, output_dir: Path) -> None:
        """Create the output directory if needed.

        Args:
            output_dir: Destination directory.

        Raises:
            InvalidMapPackageError: If the output path points to a file or cannot be created.
        """
        if output_dir.exists() and not output_dir.is_dir():
            raise InvalidMapPackageError(
                f"Prepared map output path must be a directory, not a file: {output_dir}",
            )
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise InvalidMapPackageError(
                f"Failed to create prepared map output directory: {output_dir}: {exc}",
            ) from exc

    def _copy_runtime_artifacts(
        self,
        *,
        package: GeneratedMapPackage,
        output_dir: Path,
    ) -> list[str]:
        """Copy runtime-relevant artifacts into the prepared map directory.

        Args:
            package: Loaded generated package.
            output_dir: Destination prepared-map directory.

        Returns:
            Relative paths copied into the prepared package.
        """
        copied: list[str] = []
        for file_name in (
            MapPackageLoader.MANIFEST_FILE,
            MapPackageLoader.VALIDATION_REPORT_FILE,
            MapPackageLoader.TACTICAL_MAP_FILE,
        ):
            source_path = package.package_dir / file_name
            if source_path.is_file():
                self._copy_file(source_path, output_dir / file_name)
                copied.append(file_name)

        for dir_name in ("map_package", "visual_map"):
            source_path = package.package_dir / dir_name
            if source_path.is_dir():
                self._copy_dir(source_path, output_dir / dir_name)
                copied.append(dir_name)

        return copied

    def _copy_file(self, source_path: Path, target_path: Path) -> None:
        """Copy a single file and preserve metadata when possible.

        Args:
            source_path: Source file path.
            target_path: Destination file path.

        Raises:
            InvalidMapPackageError: If copying fails.
        """
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
        except OSError as exc:
            raise InvalidMapPackageError(
                f"Failed to copy prepared map file {source_path} -> {target_path}: {exc}",
            ) from exc

    def _copy_dir(self, source_path: Path, target_path: Path) -> None:
        """Copy a directory into the prepared map package.

        Args:
            source_path: Source directory path.
            target_path: Destination directory path.

        Raises:
            InvalidMapPackageError: If copying fails.
        """
        try:
            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        except OSError as exc:
            raise InvalidMapPackageError(
                f"Failed to copy prepared map directory {source_path} -> {target_path}: {exc}",
            ) from exc

    def _build_visual_map_summary(self, package_dir: Path) -> dict[str, Any]:
        """Build a lightweight summary for an optional visual map export.

        Args:
            package_dir: Source package directory.

        Returns:
            Visual map summary dictionary.
        """
        visual_dir = package_dir / "visual_map"
        visual_map = self._try_read_json(visual_dir / "visual_map.json")
        visual_layers = self._try_read_json(visual_dir / "visual_layers.json")
        visual_objects = self._try_read_json(visual_dir / "visual_objects.json")
        visual_chunks = self._try_read_json(visual_dir / "visual_chunks.json")
        present = visual_dir.is_dir() or visual_map is not None
        contract = self._extract_visual_contract(visual_map or {})
        contract_status = self._build_visual_contract_status(contract, present=present)

        return {
            "present": present,
            "path": str(visual_dir) if present else None,
            "schema_version": str((visual_map or {}).get("schema_version", "unknown"))
            if visual_map is not None
            else "not loaded",
            "profile": str((visual_map or {}).get("profile", "unknown"))
            if visual_map is not None
            else "not loaded",
            "layers_count": self._count_collection(visual_layers, ("layers", "items")),
            "objects_count": self._count_collection(
                visual_objects,
                ("objects", "visual_objects", "items"),
            ),
            "generic_objects_count": self._count_generic_visual_objects(visual_objects),
            "chunks_count": self._count_collection(visual_chunks, ("chunks", "items")),
            "preview_png": (visual_dir / "preview.png").is_file(),
            "final_render_png": (visual_dir / "final_render.png").is_file(),
            "contract": contract,
            "contract_status": contract_status,
        }

    def _extract_visual_contract(self, visual_map: dict[str, Any]) -> dict[str, bool | None]:
        """Extract visual gameplay-safety flags from visual map metadata.

        Args:
            visual_map: Raw visual map dictionary.

        Returns:
            Contract flags with unknown values represented as ``None``.
        """
        contract = visual_map.get("contract")
        source = contract if isinstance(contract, dict) else visual_map
        return {
            "changes_gameplay": self._optional_bool(source.get("changes_gameplay")),
            "changes_collision": self._optional_bool(source.get("changes_collision")),
            "moves_markers": self._optional_bool(source.get("moves_markers")),
        }

    def _build_visual_contract_status(
        self,
        contract: dict[str, bool | None],
        *,
        present: bool,
    ) -> str:
        """Build the visual contract status label.

        Args:
            contract: Extracted visual contract flags.
            present: Whether a visual map exists.

        Returns:
            Contract status label.
        """
        if not present:
            return "skipped"
        if any(value is True for value in contract.values()):
            return "failed"
        if any(value is None for value in contract.values()):
            return "warning"
        return "passed"

    def _build_preparation_report(
        self,
        *,
        package: GeneratedMapPackage,
        runtime_map: RuntimeMap,
        output_dir: Path,
        copied_artifacts: list[str],
        visual_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the preparation report dictionary.

        Args:
            package: Loaded generated package.
            runtime_map: Built runtime map.
            output_dir: Destination prepared-map directory.
            copied_artifacts: Copied relative artifacts.
            visual_summary: Optional visual map summary.

        Returns:
            Preparation report dictionary.
        """
        dimensions_match = (
            runtime_map.width_tiles == package.manifest.dimensions.width_tiles
            and runtime_map.height_tiles == package.manifest.dimensions.height_tiles
            and runtime_map.tile_size_px == package.manifest.dimensions.tile_size_px
        )
        checks = [
            self._check("source_loaded", "passed", "Generator package was loaded."),
            self._check("runtime_map_built", "passed", "Runtime map was built from source data."),
            self._check(
                "dimensions_match_manifest",
                "passed" if dimensions_match else "failed",
                "Runtime dimensions must match generation manifest dimensions.",
            ),
            self._check(
                "structured_map_present",
                "passed" if package.structured_map is not None else "warning",
                "Structured map_package export is preferred for prepared maps.",
            ),
            self._check(
                "visual_map_present",
                "passed" if visual_summary["present"] else "warning",
                "Visual map export is expected for future baked rendering.",
            ),
            self._check(
                "visual_contract",
                str(visual_summary["contract_status"]),
                "Visual map must not change gameplay, collision, or marker positions.",
            ),
        ]
        status = self._build_overall_status(checks)
        report_path = output_dir / self.REPORTS_DIR / self.PREPARATION_REPORT_FILE

        return {
            "schema_version": "prepared-map-report-v1",
            "status": status,
            "prepared_by": {
                "project": "topdown-shooter",
                "version": __version__,
            },
            "source": {
                "path": str(package.package_dir),
                "format": self._source_format(package),
                "generator_version": package.manifest.versions.generator,
                "manifest_schema": package.manifest.schema_version,
                "profile": package.manifest.profile,
                "resolved_seed": package.manifest.resolved_seed,
            },
            "dimensions": {
                "width_tiles": runtime_map.width_tiles,
                "height_tiles": runtime_map.height_tiles,
                "tile_size_px": runtime_map.tile_size_px,
            },
            "runtime": {
                "start": {"x": runtime_map.start_tile.x, "y": runtime_map.start_tile.y},
                "goal": {"x": runtime_map.goal_tile.x, "y": runtime_map.goal_tile.y},
                "walkable_tiles": runtime_map.walkable_tile_count,
                "blocked_tiles": runtime_map.blocked_tile_count,
                "runtime_objects": runtime_map.runtime_objects_summary.total_objects,
                "runtime_grids": list(runtime_map.runtime_grids.grid_names),
                "gameplay_zones": len(runtime_map.gameplay_zones),
            },
            "visual_map": visual_summary,
            "checks": checks,
            "output": {
                "path": str(output_dir),
                "manifest_path": str(output_dir / self.PREPARED_MANIFEST_FILE),
                "report_path": str(report_path),
                "summary_path": str(output_dir / self.REPORTS_DIR / self.PREPARATION_SUMMARY_FILE),
                "copied_artifacts": copied_artifacts,
            },
        }

    def _build_prepared_manifest(
        self,
        *,
        package: GeneratedMapPackage,
        runtime_map: RuntimeMap,
        output_dir: Path,
        copied_artifacts: list[str],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the prepared map manifest dictionary.

        Args:
            package: Loaded generated package.
            runtime_map: Built runtime map.
            output_dir: Destination prepared-map directory.
            copied_artifacts: Copied relative artifacts.
            report: Preparation report dictionary.

        Returns:
            Prepared map manifest dictionary.
        """
        return {
            "schema_version": "prepared-map-manifest-v1",
            "prepared_by": {
                "project": "topdown-shooter",
                "version": __version__,
            },
            "source": {
                "path": str(package.package_dir),
                "format": self._source_format(package),
                "generator_version": package.manifest.versions.generator,
                "profile": package.manifest.profile,
                "resolved_seed": package.manifest.resolved_seed,
            },
            "dimensions": {
                "width_tiles": runtime_map.width_tiles,
                "height_tiles": runtime_map.height_tiles,
                "tile_size_px": runtime_map.tile_size_px,
            },
            "contract": {
                "changes_gameplay": False,
                "changes_collision": False,
                "moves_markers": False,
            },
            "artifacts": {
                "copied": copied_artifacts,
                "report": f"{self.REPORTS_DIR}/{self.PREPARATION_REPORT_FILE}",
                "summary": f"{self.REPORTS_DIR}/{self.PREPARATION_SUMMARY_FILE}",
            },
            "status": report["status"],
            "output_path": str(output_dir),
        }


    def _source_format(self, package: GeneratedMapPackage) -> str:
        """Return the loaded source package format label.

        Args:
            package: Loaded generated package.

        Returns:
            Source format label.
        """
        if package.structured_map is not None:
            return "map_package"
        return "legacy tactical_map"

    def _check(self, code: str, status: str, message: str) -> dict[str, str]:
        """Build a single preparation check entry.

        Args:
            code: Stable check code.
            status: Check status.
            message: Human-readable check description.

        Returns:
            Check dictionary.
        """
        return {"code": code, "status": status, "message": message}

    def _build_overall_status(self, checks: list[dict[str, str]]) -> str:
        """Build an overall report status from checks.

        Args:
            checks: Preparation checks.

        Returns:
            Overall status label.
        """
        statuses = {check["status"] for check in checks}
        if "failed" in statuses:
            return "failed"
        if "warning" in statuses:
            return "warning"
        return "passed"

    def _count_collection(self, data: dict[str, Any] | None, keys: tuple[str, ...]) -> int:
        """Count collection items under the first supported key.

        Args:
            data: Optional JSON object.
            keys: Candidate collection keys.

        Returns:
            Item count, or zero when no collection is found.
        """
        if data is None:
            return 0
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
            if isinstance(value, dict):
                return len(value)
        return 0

    def _count_generic_visual_objects(self, visual_objects: dict[str, Any] | None) -> int:
        """Count visual objects that still use a generic asset marker.

        Args:
            visual_objects: Optional visual objects export.

        Returns:
            Generic object count.
        """
        if visual_objects is None:
            return 0
        items = self._extract_collection_items(
            visual_objects,
            ("objects", "visual_objects", "items"),
        )
        generic_count = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            searchable = " ".join(
                str(item.get(key, ""))
                for key in (
                    "type",
                    "sprite_id",
                    "asset_id",
                    "asset_family",
                    "visual_id",
                    "family",
                )
            ).lower()
            if "generic" in searchable:
                generic_count += 1
        return generic_count

    def _extract_collection_items(
        self,
        data: dict[str, Any],
        keys: tuple[str, ...],
    ) -> list[Any]:
        """Extract collection items from common JSON collection shapes.

        Args:
            data: JSON object.
            keys: Candidate collection keys.

        Returns:
            Collection items as a list.
        """
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return list(value.values())
        return []

    def _optional_bool(self, value: Any) -> bool | None:
        """Return an optional boolean from raw JSON data.

        Args:
            value: Raw JSON value.

        Returns:
            Boolean value, or ``None`` when the value is not boolean.
        """
        return value if isinstance(value, bool) else None

    def _require_report_dict(self, report: dict[str, Any], key: str) -> dict[str, Any]:
        """Return a nested report dictionary.

        Args:
            report: Preparation report.
            key: Required nested key.

        Returns:
            Nested dictionary or an empty dictionary for malformed input.
        """
        value = report.get(key)
        return value if isinstance(value, dict) else {}

    def _try_read_json(self, path: Path) -> dict[str, Any] | None:
        """Read an optional JSON object.

        Args:
            path: JSON path.

        Returns:
            JSON object or ``None`` when absent.

        Raises:
            InvalidMapPackageError: If present JSON cannot be decoded as an object.
        """
        if not path.is_file():
            return None
        try:
            with path.open("r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
        except json.JSONDecodeError as exc:
            raise InvalidMapPackageError(f"Invalid JSON file: {path}: {exc}") from exc
        except OSError as exc:
            raise InvalidMapPackageError(f"Failed to read JSON file: {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise InvalidMapPackageError(f"JSON root must be an object: {path}")
        return data

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        """Write a JSON object using deterministic formatting.

        Args:
            path: Destination path.
            data: JSON object.

        Raises:
            InvalidMapPackageError: If writing fails.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise InvalidMapPackageError(f"Failed to write JSON file: {path}: {exc}") from exc

    def _write_text(self, path: Path, text: str) -> None:
        """Write UTF-8 text.

        Args:
            path: Destination path.
            text: Text content.

        Raises:
            InvalidMapPackageError: If writing fails.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{text}\n", encoding="utf-8")
        except OSError as exc:
            raise InvalidMapPackageError(f"Failed to write text file: {path}: {exc}") from exc
