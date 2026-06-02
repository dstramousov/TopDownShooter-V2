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
from topdown_shooter.map_preparation.pilot_art_preview import (
    PilotArtPreviewRenderer,
    PilotArtPreviewResult,
)
from topdown_shooter.map_preparation.prepared_visual_preview import (
    PreparedVisualPreviewRenderer,
    PreparedVisualPreviewResult,
)
from topdown_shooter.map_preparation.scene_quality import (
    VisualQualityAnalyzer,
    VisualQualityResult,
)
from topdown_shooter.map_preparation.visual_art_layers import (
    VisualArtLayerBuilder,
    VisualArtLayerResult,
)
from topdown_shooter.map_preparation.visual_context import (
    VisualContextAnalyzer,
    VisualContextResult,
)
from topdown_shooter.map_preparation.visual_object_family import (
    VisualObjectFamilyResolver,
    VisualObjectFamilyResult,
)
from topdown_shooter.map_preparation.visual_object_normalization import (
    VisualObjectNormalizationResult,
    VisualObjectNormalizer,
)
from topdown_shooter.map_preparation.visual_scene_dressing import (
    VisualSceneDressingGenerator,
    VisualSceneDressingResult,
)
from topdown_shooter.map_preparation.visual_scene_preset import (
    VisualScenePresetAssigner,
    VisualScenePresetResult,
)
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
    VISUAL_MAP_DIR = "visual_map"
    VISUAL_CONTEXT_FILE = "visual_context.json"
    VISUAL_REGIONS_FILE = "visual_regions.json"
    VISUAL_SCENE_CANDIDATES_FILE = "visual_scene_candidates.json"
    VISUAL_CONTEXT_REPORT_FILE = "visual_context_report.json"
    VISUAL_SCENE_RANKING_FILE = "visual_scene_ranking.json"
    VISUAL_QUALITY_REPORT_FILE = "visual_quality_report.json"
    VISUAL_QUALITY_SUMMARY_FILE = "visual_quality_summary.txt"
    VISUAL_OBJECT_FAMILIES_FILE = "visual_object_families.json"
    VISUAL_OBJECT_FAMILY_REPORT_FILE = "visual_object_family_report.json"
    VISUAL_OBJECT_FAMILY_SUMMARY_FILE = "visual_object_family_summary.txt"
    VISUAL_OBJECTS_NORMALIZED_FILE = "visual_objects_normalized.json"
    VISUAL_OBJECT_NORMALIZATION_REPORT_FILE = "visual_object_normalization_report.json"
    VISUAL_OBJECT_NORMALIZATION_SUMMARY_FILE = "visual_object_normalization_summary.txt"
    VISUAL_SCENE_PRESETS_FILE = "visual_scene_presets.json"
    VISUAL_SCENE_PRESET_REPORT_FILE = "visual_scene_preset_report.json"
    VISUAL_SCENE_PRESET_SUMMARY_FILE = "visual_scene_preset_summary.txt"
    VISUAL_SCENE_DRESSING_FILE = "visual_scene_dressing.json"
    VISUAL_OBJECTS_DRESSED_FILE = "visual_objects_dressed.json"
    VISUAL_SCENE_DRESSING_REPORT_FILE = "visual_scene_dressing_report.json"
    VISUAL_SCENE_DRESSING_SUMMARY_FILE = "visual_scene_dressing_summary.txt"
    PREPARED_PREVIEW_FILE = "prepared_preview.png"
    PREPARED_PREVIEW_LEGEND_FILE = "prepared_preview_legend.json"
    PREPARED_VISUAL_PREVIEW_REPORT_FILE = "prepared_visual_preview_report.json"
    PREPARED_VISUAL_PREVIEW_SUMMARY_FILE = "prepared_visual_preview_summary.txt"
    PILOT_ART_PREVIEW_FILE = "pilot_art_preview.png"
    PILOT_ART_PREVIEW_LEGEND_FILE = "pilot_art_preview_legend.json"
    PILOT_ART_PREVIEW_REPORT_FILE = "pilot_art_preview_report.json"
    PILOT_ART_PREVIEW_SUMMARY_FILE = "pilot_art_preview_summary.txt"
    VISUAL_ART_LAYERS_FILE = "visual_art_layers.json"
    VISUAL_ART_OBJECTS_FILE = "visual_art_objects.json"
    VISUAL_ART_CHUNKS_FILE = "visual_art_chunks.json"
    VISUAL_ART_LAYERS_REPORT_FILE = "visual_art_layers_report.json"
    VISUAL_ART_LAYERS_SUMMARY_FILE = "visual_art_layers_summary.txt"

    def __init__(
        self,
        *,
        loader: MapPackageLoader | None = None,
        runtime_builder: RuntimeMapBuilder | None = None,
        visual_context_analyzer: VisualContextAnalyzer | None = None,
        visual_quality_analyzer: VisualQualityAnalyzer | None = None,
        visual_object_family_resolver: VisualObjectFamilyResolver | None = None,
        visual_object_normalizer: VisualObjectNormalizer | None = None,
        visual_scene_preset_assigner: VisualScenePresetAssigner | None = None,
        visual_scene_dressing_generator: VisualSceneDressingGenerator | None = None,
        prepared_visual_preview_renderer: PreparedVisualPreviewRenderer | None = None,
        pilot_art_preview_renderer: PilotArtPreviewRenderer | None = None,
        visual_art_layer_builder: VisualArtLayerBuilder | None = None,
    ) -> None:
        """Initialize the preparation service.

        Args:
            loader: Optional package loader override for tests.
            runtime_builder: Optional runtime map builder override for tests.
            visual_context_analyzer: Optional visual context analyzer override for tests.
            visual_quality_analyzer: Optional visual quality analyzer override for tests.
            visual_object_family_resolver: Optional visual object family resolver override
                for tests.
            visual_object_normalizer: Optional visual object normalizer override for tests.
            visual_scene_preset_assigner: Optional visual scene preset assigner override for tests.
            visual_scene_dressing_generator: Optional visual scene dressing generator override
                for tests.
            prepared_visual_preview_renderer: Optional prepared visual preview renderer
                override for tests.
            pilot_art_preview_renderer: Optional pilot art preview renderer override for tests.
            visual_art_layer_builder: Optional visual art layer builder override for tests.
        """
        self._loader = loader or MapPackageLoader()
        self._runtime_builder = runtime_builder or RuntimeMapBuilder()
        self._visual_context_analyzer = visual_context_analyzer or VisualContextAnalyzer()
        self._visual_quality_analyzer = visual_quality_analyzer or VisualQualityAnalyzer()
        self._visual_object_family_resolver = (
            visual_object_family_resolver or VisualObjectFamilyResolver()
        )
        self._visual_object_normalizer = visual_object_normalizer or VisualObjectNormalizer()
        self._visual_scene_preset_assigner = (
            visual_scene_preset_assigner or VisualScenePresetAssigner()
        )
        self._visual_scene_dressing_generator = (
            visual_scene_dressing_generator or VisualSceneDressingGenerator()
        )
        self._prepared_visual_preview_renderer = (
            prepared_visual_preview_renderer or PreparedVisualPreviewRenderer()
        )
        self._pilot_art_preview_renderer = pilot_art_preview_renderer or PilotArtPreviewRenderer()
        self._visual_art_layer_builder = visual_art_layer_builder or VisualArtLayerBuilder()

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
        visual_map_source = self._load_visual_map_source(package.package_dir)
        visual_summary = self._build_visual_map_summary(visual_map_source)
        visual_object_family_result = self._visual_object_family_resolver.resolve(
            visual_map_source.get("visual_objects"),
        )
        visual_object_normalization_result = self._visual_object_normalizer.normalize(
            visual_objects=visual_map_source.get("visual_objects"),
            family_index=visual_object_family_result.family_index,
        )
        normalized_visual_summary = self._build_visual_map_summary(
            self._with_normalized_visual_objects(
                visual_map_source,
                visual_object_normalization_result.normalized_visual_objects,
            ),
        )
        visual_context_result = self._visual_context_analyzer.analyze(runtime_map)
        visual_quality_result = self._visual_quality_analyzer.analyze(
            visual_summary=normalized_visual_summary,
            scene_candidates=visual_context_result.scene_candidates,
        )
        visual_scene_preset_result = self._visual_scene_preset_assigner.assign(
            profile=package.manifest.profile,
            scene_ranking=visual_quality_result.scene_ranking,
            object_families=visual_object_family_result.family_index,
        )
        visual_scene_dressing_result = self._visual_scene_dressing_generator.generate(
            scene_presets=visual_scene_preset_result.scene_presets,
            visual_context=visual_context_result.context,
            normalized_visual_objects=visual_object_normalization_result.normalized_visual_objects,
        )
        prepared_visual_preview_result = self._prepared_visual_preview_renderer.render(
            visual_context=visual_context_result.context,
            scene_ranking=visual_quality_result.scene_ranking,
            scene_dressing=visual_scene_dressing_result.scene_dressing,
            dressed_visual_objects=visual_scene_dressing_result.dressed_visual_objects,
        )
        pilot_art_preview_result = self._pilot_art_preview_renderer.render(
            visual_context=visual_context_result.context,
            scene_dressing=visual_scene_dressing_result.scene_dressing,
            dressed_visual_objects=visual_scene_dressing_result.dressed_visual_objects,
        )
        visual_art_layer_result = self._visual_art_layer_builder.build(
            visual_context=visual_context_result.context,
            scene_dressing=visual_scene_dressing_result.scene_dressing,
            dressed_visual_objects=visual_scene_dressing_result.dressed_visual_objects,
        )
        generated_artifacts = self._write_visual_context_artifacts(
            output_dir=resolved_output_dir,
            result=visual_context_result,
        )
        generated_artifacts.extend(
            self._write_visual_object_family_artifacts(
                output_dir=resolved_output_dir,
                result=visual_object_family_result,
            ),
        )
        generated_artifacts.extend(
            self._write_visual_object_normalization_artifacts(
                output_dir=resolved_output_dir,
                result=visual_object_normalization_result,
            ),
        )
        generated_artifacts.extend(
            self._write_visual_quality_artifacts(
                output_dir=resolved_output_dir,
                result=visual_quality_result,
            ),
        )
        generated_artifacts.extend(
            self._write_visual_scene_preset_artifacts(
                output_dir=resolved_output_dir,
                result=visual_scene_preset_result,
            ),
        )
        generated_artifacts.extend(
            self._write_visual_scene_dressing_artifacts(
                output_dir=resolved_output_dir,
                result=visual_scene_dressing_result,
            ),
        )
        generated_artifacts.extend(
            self._write_prepared_visual_preview_artifacts(
                output_dir=resolved_output_dir,
                result=prepared_visual_preview_result,
            ),
        )
        generated_artifacts.extend(
            self._write_pilot_art_preview_artifacts(
                output_dir=resolved_output_dir,
                result=pilot_art_preview_result,
            ),
        )
        generated_artifacts.extend(
            self._write_visual_art_layer_artifacts(
                output_dir=resolved_output_dir,
                result=visual_art_layer_result,
            ),
        )
        report = self._build_preparation_report(
            package=package,
            runtime_map=runtime_map,
            output_dir=resolved_output_dir,
            copied_artifacts=copied_artifacts,
            generated_artifacts=generated_artifacts,
            visual_summary=visual_summary,
            visual_context_report=visual_context_result.report,
            visual_object_family_report=visual_object_family_result.family_report,
            visual_object_normalization_report=(
                visual_object_normalization_result.normalization_report
            ),
            visual_quality_report=visual_quality_result.quality_report,
            visual_scene_preset_report=visual_scene_preset_result.preset_report,
            visual_scene_dressing_report=visual_scene_dressing_result.dressing_report,
            prepared_visual_preview_report=prepared_visual_preview_result.preview_report,
            pilot_art_preview_report=pilot_art_preview_result.preview_report,
            visual_art_layers_report=visual_art_layer_result.art_report,
        )
        manifest = self._build_prepared_manifest(
            package=package,
            runtime_map=runtime_map,
            output_dir=resolved_output_dir,
            copied_artifacts=copied_artifacts,
            generated_artifacts=generated_artifacts,
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
        visual_context = self._require_report_dict(report, "visual_context")
        context_regions = self._require_report_dict(visual_context, "regions")
        context_scenes = self._require_report_dict(visual_context, "scene_candidates")
        visual_quality = self._require_report_dict(report, "visual_quality")
        visual_families = self._require_report_dict(report, "visual_object_families")
        visual_object_normalization = self._require_report_dict(
            report,
            "visual_object_normalization",
        )
        visual_scene_presets = self._require_report_dict(report, "visual_scene_presets")
        visual_scene_dressing = self._require_report_dict(report, "visual_scene_dressing")
        prepared_visual_preview = self._require_report_dict(report, "prepared_visual_preview")
        preview_rendered = self._require_report_dict(prepared_visual_preview, "rendered")
        pilot_art_preview = self._require_report_dict(report, "pilot_art_preview")
        pilot_rendered = self._require_report_dict(pilot_art_preview, "rendered")
        visual_art_layers = self._require_report_dict(report, "visual_art_layers")
        visual_art_counts = self._require_report_dict(visual_art_layers, "counts")
        quality_scenes = self._require_report_dict(visual_quality, "scene_ranking")
        quality_generic = self._require_report_dict(visual_quality, "generic_objects")
        family_generic = self._require_report_dict(visual_families, "generic_objects")
        normalization_counts = self._require_report_dict(
            visual_object_normalization,
            "counts",
        )
        preset_coverage = self._require_report_dict(visual_scene_presets, "preset_coverage")
        dressing_coverage = self._require_report_dict(
            visual_scene_dressing,
            "dressing_coverage",
        )
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
                f"- visual context: {visual_context.get('status', 'unknown')}",
                f"- forest regions: {context_regions.get('forest_regions', 'unknown')}",
                f"- clearings: {context_regions.get('clearing_regions', 'unknown')}",
                f"- scene candidates: {context_scenes.get('total_candidates', 'unknown')}",
                f"- visual quality: {visual_quality.get('status', 'unknown')}",
                (
                    "- accepted scenes: "
                    f"{quality_scenes.get('accepted_scenes', 'unknown')}"
                ),
                (
                    "- generic objects: "
                    f"{quality_generic.get('generic_objects', 'unknown')}"
                    f"/{quality_generic.get('total_objects', 'unknown')} "
                    f"{quality_generic.get('status', 'unknown')}"
                ),
                f"- object families: {visual_families.get('status', 'unknown')}",
                (
                    "- resolved generic families: "
                    f"{family_generic.get('resolved_generic_objects', 'unknown')}"
                    f"/{family_generic.get('generic_objects', 'unknown')}"
                ),
                f"- object normalization: {visual_object_normalization.get('status', 'unknown')}",
                (
                    "- remaining generic objects: "
                    f"{normalization_counts.get('remaining_generic_objects', 'unknown')}"
                    f"/{normalization_counts.get('total_objects', 'unknown')}"
                ),
                f"- scene presets: {visual_scene_presets.get('status', 'unknown')}",
                (
                    "- assigned scene presets: "
                    f"{preset_coverage.get('assigned_scenes', 'unknown')}"
                    f"/{preset_coverage.get('total_scenes', 'unknown')}"
                ),
                f"- scene dressing: {visual_scene_dressing.get('status', 'unknown')}",
                (
                    "- dressed scenes: "
                    f"{dressing_coverage.get('dressed_scenes', 'unknown')}"
                    f"/{dressing_coverage.get('assigned_scenes', 'unknown')}"
                ),
                (
                    "- dressing objects: "
                    f"{dressing_coverage.get('generated_objects', 'unknown')}"
                ),
                f"- prepared preview: {prepared_visual_preview.get('status', 'unknown')}",
                (
                    "- rendered normalized objects: "
                    f"{preview_rendered.get('normalized_objects', 'unknown')}"
                ),
                (
                    "- rendered dressing objects: "
                    f"{preview_rendered.get('dressing_objects', 'unknown')}"
                ),
                f"- pilot art preview: {pilot_art_preview.get('status', 'unknown')}",
                (
                    "- pilot terrain tiles: "
                    f"{pilot_rendered.get('terrain_tiles', 'unknown')}"
                ),
                (
                    "- pilot forest stamps: "
                    f"{pilot_rendered.get('forest_stamps', 'unknown')}"
                ),
                (
                    "- pilot forest region blobs: "
                    f"{pilot_rendered.get('forest_region_blobs', 'unknown')}"
                ),
                (
                    "- pilot rendered objects: "
                    f"{pilot_rendered.get('normalized_objects', 'unknown')}"
                ),
                (
                    "- pilot rendered dressing: "
                    f"{pilot_rendered.get('dressing_objects', 'unknown')}"
                ),
                f"- visual art layers: {visual_art_layers.get('status', 'unknown')}",
                (
                    "- visual art elements: "
                    f"{visual_art_counts.get('layer_elements', 'unknown')} layers / "
                    f"{visual_art_counts.get('object_elements', 'unknown')} objects"
                ),
                f"- visual art chunks: {visual_art_counts.get('chunks', 'unknown')}",
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

    def _write_visual_context_artifacts(
        self,
        *,
        output_dir: Path,
        result: VisualContextResult,
    ) -> list[str]:
        """Write generated visual context artifacts into the prepared package.

        Args:
            output_dir: Destination prepared-map directory.
            result: Visual context analyzer result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_CONTEXT_FILE}",
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_REGIONS_FILE}",
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_SCENE_CANDIDATES_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_CONTEXT_REPORT_FILE}",
        ]
        self._write_json(visual_dir / self.VISUAL_CONTEXT_FILE, result.context)
        self._write_json(visual_dir / self.VISUAL_REGIONS_FILE, result.regions)
        self._write_json(
            visual_dir / self.VISUAL_SCENE_CANDIDATES_FILE,
            result.scene_candidates,
        )
        self._write_json(reports_dir / self.VISUAL_CONTEXT_REPORT_FILE, result.report)
        return artifacts

    def _write_visual_object_family_artifacts(
        self,
        *,
        output_dir: Path,
        result: VisualObjectFamilyResult,
    ) -> list[str]:
        """Write generated visual object family artifacts into the prepared package.

        Args:
            output_dir: Destination prepared-map directory.
            result: Visual object family resolver result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_OBJECT_FAMILIES_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_OBJECT_FAMILY_REPORT_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_OBJECT_FAMILY_SUMMARY_FILE}",
        ]
        self._write_json(visual_dir / self.VISUAL_OBJECT_FAMILIES_FILE, result.family_index)
        self._write_json(
            reports_dir / self.VISUAL_OBJECT_FAMILY_REPORT_FILE,
            result.family_report,
        )
        self._write_text(
            reports_dir / self.VISUAL_OBJECT_FAMILY_SUMMARY_FILE,
            result.family_summary,
        )
        return artifacts

    def _write_visual_object_normalization_artifacts(
        self,
        *,
        output_dir: Path,
        result: VisualObjectNormalizationResult,
    ) -> list[str]:
        """Write generated normalized visual object artifacts.

        Args:
            output_dir: Destination prepared-map directory.
            result: Visual object normalization result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_OBJECTS_NORMALIZED_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_OBJECT_NORMALIZATION_REPORT_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_OBJECT_NORMALIZATION_SUMMARY_FILE}",
        ]
        self._write_json(
            visual_dir / self.VISUAL_OBJECTS_NORMALIZED_FILE,
            result.normalized_visual_objects,
        )
        self._write_json(
            reports_dir / self.VISUAL_OBJECT_NORMALIZATION_REPORT_FILE,
            result.normalization_report,
        )
        self._write_text(
            reports_dir / self.VISUAL_OBJECT_NORMALIZATION_SUMMARY_FILE,
            result.normalization_summary,
        )
        return artifacts

    def _write_visual_scene_preset_artifacts(
        self,
        *,
        output_dir: Path,
        result: VisualScenePresetResult,
    ) -> list[str]:
        """Write generated visual scene preset artifacts into the prepared package.

        Args:
            output_dir: Destination prepared-map directory.
            result: Visual scene preset assignment result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_SCENE_PRESETS_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_SCENE_PRESET_REPORT_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_SCENE_PRESET_SUMMARY_FILE}",
        ]
        self._write_json(visual_dir / self.VISUAL_SCENE_PRESETS_FILE, result.scene_presets)
        self._write_json(reports_dir / self.VISUAL_SCENE_PRESET_REPORT_FILE, result.preset_report)
        self._write_text(reports_dir / self.VISUAL_SCENE_PRESET_SUMMARY_FILE, result.preset_summary)
        return artifacts

    def _write_visual_scene_dressing_artifacts(
        self,
        *,
        output_dir: Path,
        result: VisualSceneDressingResult,
    ) -> list[str]:
        """Write generated visual scene dressing artifacts.

        Args:
            output_dir: Destination prepared-map directory.
            result: Visual scene dressing result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_SCENE_DRESSING_FILE}",
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_OBJECTS_DRESSED_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_SCENE_DRESSING_REPORT_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_SCENE_DRESSING_SUMMARY_FILE}",
        ]
        self._write_json(visual_dir / self.VISUAL_SCENE_DRESSING_FILE, result.scene_dressing)
        self._write_json(
            visual_dir / self.VISUAL_OBJECTS_DRESSED_FILE,
            result.dressed_visual_objects,
        )
        self._write_json(
            reports_dir / self.VISUAL_SCENE_DRESSING_REPORT_FILE,
            result.dressing_report,
        )
        self._write_text(
            reports_dir / self.VISUAL_SCENE_DRESSING_SUMMARY_FILE,
            result.dressing_summary,
        )
        return artifacts

    def _write_prepared_visual_preview_artifacts(
        self,
        *,
        output_dir: Path,
        result: PreparedVisualPreviewResult,
    ) -> list[str]:
        """Write generated prepared visual preview artifacts.

        Args:
            output_dir: Destination prepared-map directory.
            result: Prepared visual preview renderer result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.PREPARED_PREVIEW_FILE}",
            f"{self.VISUAL_MAP_DIR}/{self.PREPARED_PREVIEW_LEGEND_FILE}",
            f"{self.REPORTS_DIR}/{self.PREPARED_VISUAL_PREVIEW_REPORT_FILE}",
            f"{self.REPORTS_DIR}/{self.PREPARED_VISUAL_PREVIEW_SUMMARY_FILE}",
        ]
        self._write_bytes(visual_dir / self.PREPARED_PREVIEW_FILE, result.preview_png)
        self._write_json(visual_dir / self.PREPARED_PREVIEW_LEGEND_FILE, result.legend)
        self._write_json(
            reports_dir / self.PREPARED_VISUAL_PREVIEW_REPORT_FILE,
            result.preview_report,
        )
        self._write_text(
            reports_dir / self.PREPARED_VISUAL_PREVIEW_SUMMARY_FILE,
            result.preview_summary,
        )
        return artifacts

    def _write_pilot_art_preview_artifacts(
        self,
        *,
        output_dir: Path,
        result: PilotArtPreviewResult,
    ) -> list[str]:
        """Write generated pilot art preview artifacts.

        Args:
            output_dir: Destination prepared-map directory.
            result: Pilot art preview renderer result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.PILOT_ART_PREVIEW_FILE}",
            f"{self.VISUAL_MAP_DIR}/{self.PILOT_ART_PREVIEW_LEGEND_FILE}",
            f"{self.REPORTS_DIR}/{self.PILOT_ART_PREVIEW_REPORT_FILE}",
            f"{self.REPORTS_DIR}/{self.PILOT_ART_PREVIEW_SUMMARY_FILE}",
        ]
        self._write_bytes(visual_dir / self.PILOT_ART_PREVIEW_FILE, result.preview_png)
        self._write_json(visual_dir / self.PILOT_ART_PREVIEW_LEGEND_FILE, result.legend)
        self._write_json(
            reports_dir / self.PILOT_ART_PREVIEW_REPORT_FILE,
            result.preview_report,
        )
        self._write_text(
            reports_dir / self.PILOT_ART_PREVIEW_SUMMARY_FILE,
            result.preview_summary,
        )
        return artifacts

    def _write_visual_art_layer_artifacts(
        self,
        *,
        output_dir: Path,
        result: VisualArtLayerResult,
    ) -> list[str]:
        """Write generated visual art layer artifacts.

        Args:
            output_dir: Destination prepared-map directory.
            result: Visual art layer export result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_ART_LAYERS_FILE}",
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_ART_OBJECTS_FILE}",
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_ART_CHUNKS_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_ART_LAYERS_REPORT_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_ART_LAYERS_SUMMARY_FILE}",
        ]
        self._write_json(visual_dir / self.VISUAL_ART_LAYERS_FILE, result.visual_art_layers)
        self._write_json(visual_dir / self.VISUAL_ART_OBJECTS_FILE, result.visual_art_objects)
        self._write_json(visual_dir / self.VISUAL_ART_CHUNKS_FILE, result.visual_art_chunks)
        self._write_json(reports_dir / self.VISUAL_ART_LAYERS_REPORT_FILE, result.art_report)
        self._write_text(reports_dir / self.VISUAL_ART_LAYERS_SUMMARY_FILE, result.art_summary)
        return artifacts

    def _write_visual_quality_artifacts(
        self,
        *,
        output_dir: Path,
        result: VisualQualityResult,
    ) -> list[str]:
        """Write generated visual quality artifacts into the prepared package.

        Args:
            output_dir: Destination prepared-map directory.
            result: Visual quality analyzer result.

        Returns:
            Generated relative artifact paths.
        """
        visual_dir = output_dir / self.VISUAL_MAP_DIR
        reports_dir = output_dir / self.REPORTS_DIR
        artifacts = [
            f"{self.VISUAL_MAP_DIR}/{self.VISUAL_SCENE_RANKING_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_QUALITY_REPORT_FILE}",
            f"{self.REPORTS_DIR}/{self.VISUAL_QUALITY_SUMMARY_FILE}",
        ]
        self._write_json(visual_dir / self.VISUAL_SCENE_RANKING_FILE, result.scene_ranking)
        self._write_json(reports_dir / self.VISUAL_QUALITY_REPORT_FILE, result.quality_report)
        self._write_text(reports_dir / self.VISUAL_QUALITY_SUMMARY_FILE, result.quality_summary)
        return artifacts

    def _load_visual_map_source(self, package_dir: Path) -> dict[str, Any]:
        """Load optional visual map source artifacts once.

        Args:
            package_dir: Source package directory.

        Returns:
            Dictionary containing raw optional visual map artifacts and paths.
        """
        visual_dir = package_dir / "visual_map"
        return {
            "visual_dir": visual_dir,
            "visual_map": self._try_read_json(visual_dir / "visual_map.json"),
            "visual_layers": self._try_read_json(visual_dir / "visual_layers.json"),
            "visual_objects": self._try_read_json(visual_dir / "visual_objects.json"),
            "visual_chunks": self._try_read_json(visual_dir / "visual_chunks.json"),
        }

    def _with_normalized_visual_objects(
        self,
        visual_map_source: dict[str, Any],
        normalized_visual_objects: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a visual map source copy with normalized visual objects.

        Args:
            visual_map_source: Source visual map artifacts.
            normalized_visual_objects: Normalized visual objects artifact.

        Returns:
            Visual map source dictionary for quality checks.
        """
        updated = dict(visual_map_source)
        updated["visual_objects"] = normalized_visual_objects
        return updated

    def _build_visual_map_summary(self, visual_map_source: dict[str, Any]) -> dict[str, Any]:
        """Build a lightweight summary for an optional visual map export.

        Args:
            visual_map_source: Raw visual map source artifacts loaded from disk.

        Returns:
            Visual map summary dictionary.
        """
        visual_dir = visual_map_source.get("visual_dir")
        if not isinstance(visual_dir, Path):
            raise InvalidMapPackageError("Visual map source is missing visual_dir.")
        visual_map = self._optional_dict(visual_map_source.get("visual_map"))
        visual_layers = self._optional_dict(visual_map_source.get("visual_layers"))
        visual_objects = self._optional_dict(visual_map_source.get("visual_objects"))
        visual_chunks = self._optional_dict(visual_map_source.get("visual_chunks"))
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
        generated_artifacts: list[str],
        visual_summary: dict[str, Any],
        visual_context_report: dict[str, Any],
        visual_object_family_report: dict[str, Any],
        visual_object_normalization_report: dict[str, Any],
        visual_quality_report: dict[str, Any],
        visual_scene_preset_report: dict[str, Any],
        visual_scene_dressing_report: dict[str, Any],
        prepared_visual_preview_report: dict[str, Any],
        pilot_art_preview_report: dict[str, Any],
        visual_art_layers_report: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the preparation report dictionary.

        Args:
            package: Loaded generated package.
            runtime_map: Built runtime map.
            output_dir: Destination prepared-map directory.
            copied_artifacts: Copied relative artifacts.
            generated_artifacts: Generated relative artifacts.
            visual_summary: Optional visual map summary.
            visual_context_report: Visual context analyzer report.
            visual_object_family_report: Visual object family resolver report.
            visual_object_normalization_report: Visual object normalization report.
            visual_quality_report: Visual quality gates report.
            visual_scene_preset_report: Visual scene preset assignment report.
            visual_scene_dressing_report: Visual scene dressing generation report.
            prepared_visual_preview_report: Prepared visual preview renderer report.
            pilot_art_preview_report: Pilot art preview renderer report.
            visual_art_layers_report: Visual art layer export report.

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
            self._check(
                "visual_context_built",
                str(visual_context_report.get("status", "failed")),
                "Visual context analyzer must produce region and scene-candidate artifacts.",
            ),
            self._check(
                "visual_object_families_built",
                "passed",
                "Visual object family resolver must diagnose generic sprite usage.",
            ),
            self._check(
                "visual_object_normalization_built",
                "passed",
                "Visual object normalization must produce render-ready object families.",
            ),
            self._check(
                "visual_quality_built",
                "passed",
                "Visual quality gates must rank scenes and report non-blocking art readiness.",
            ),
            self._check(
                "visual_scene_presets_built",
                "passed",
                "Visual scene presets must be assigned to accepted ranked scenes.",
            ),
            self._check(
                "visual_scene_dressing_built",
                "passed",
                "Visual scene dressing must generate visual-only objects for assigned scenes.",
            ),
            self._check(
                "prepared_visual_preview_built",
                str(prepared_visual_preview_report.get("status", "failed")),
                "Prepared visual preview must render normalizer artifacts for review.",
            ),
            self._check(
                "pilot_art_preview_built",
                str(pilot_art_preview_report.get("status", "failed")),
                "Pilot art preview must render a non-debug painter-style map preview.",
            ),
            self._check(
                "visual_art_layers_built",
                str(visual_art_layers_report.get("status", "failed")),
                "Visual art layer export must turn painter decisions into prepared render data.",
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
            "visual_context": visual_context_report,
            "visual_object_families": visual_object_family_report,
            "visual_object_normalization": visual_object_normalization_report,
            "visual_quality": visual_quality_report,
            "visual_scene_presets": visual_scene_preset_report,
            "visual_scene_dressing": visual_scene_dressing_report,
            "prepared_visual_preview": prepared_visual_preview_report,
            "pilot_art_preview": pilot_art_preview_report,
            "visual_art_layers": visual_art_layers_report,
            "checks": checks,
            "output": {
                "path": str(output_dir),
                "manifest_path": str(output_dir / self.PREPARED_MANIFEST_FILE),
                "report_path": str(report_path),
                "summary_path": str(output_dir / self.REPORTS_DIR / self.PREPARATION_SUMMARY_FILE),
                "copied_artifacts": copied_artifacts,
                "generated_artifacts": generated_artifacts,
            },
        }

    def _build_prepared_manifest(
        self,
        *,
        package: GeneratedMapPackage,
        runtime_map: RuntimeMap,
        output_dir: Path,
        copied_artifacts: list[str],
        generated_artifacts: list[str],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the prepared map manifest dictionary.

        Args:
            package: Loaded generated package.
            runtime_map: Built runtime map.
            output_dir: Destination prepared-map directory.
            copied_artifacts: Copied relative artifacts.
            generated_artifacts: Generated relative artifacts.
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
                "generated": generated_artifacts,
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

    def _optional_dict(self, value: Any) -> dict[str, Any] | None:
        """Return a dictionary value or ``None``.

        Args:
            value: Raw value.

        Returns:
            Dictionary value or ``None``.
        """
        return value if isinstance(value, dict) else None

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

    def _write_bytes(self, path: Path, data: bytes) -> None:
        """Write binary data.

        Args:
            path: Destination path.
            data: Binary content.

        Raises:
            InvalidMapPackageError: If writing fails.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except OSError as exc:
            raise InvalidMapPackageError(f"Failed to write binary file: {path}: {exc}") from exc

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
