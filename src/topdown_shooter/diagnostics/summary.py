"""Human-readable map inspection summaries."""

from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.world.runtime_map import RuntimeMap


def build_inspection_summary(package: GeneratedMapPackage, runtime_map: RuntimeMap) -> str:
    """Build a concise map inspection summary.

    Args:
        package: Loaded generated map package.
        runtime_map: Built runtime map.

    Returns:
        Human-readable inspection summary.
    """
    manifest = package.manifest
    report = package.validation_report
    tactical = runtime_map.tactical_summary
    objects = runtime_map.runtime_objects_summary
    structured_map = package.structured_map
    warning_codes = ", ".join(issue.code for issue in report.warnings) or "none"
    source_format = "map_package" if structured_map is not None else "legacy tactical_map"
    map_schema = structured_map.index_schema_version if structured_map is not None else "not loaded"
    package_schema = (
        structured_map.package_schema_version if structured_map is not None else "not loaded"
    )

    gameplay_zone_types = dict(runtime_map.gameplay_zone_counts_by_type)

    return "\n".join(
        [
            "Map package loaded",
            "",
            "Package:",
            f"- generator: {manifest.versions.generator}",
            f"- manifest schema: {manifest.schema_version}",
            f"- tactical schema: {manifest.versions.schemas.get('tactical_map', 'unknown')}",
            f"- source format: {source_format}",
            f"- map package schema: {package_schema}",
            f"- map index schema: {map_schema}",
            f"- profile: {manifest.profile}",
            f"- resolved seed: {manifest.resolved_seed}",
            "",
            "Map:",
            f"- size: {runtime_map.width_tiles}x{runtime_map.height_tiles}",
            f"- tile size: {runtime_map.tile_size_px} px",
            f"- start: ({runtime_map.start_tile.x}, {runtime_map.start_tile.y})",
            f"- goal: ({runtime_map.goal_tile.x}, {runtime_map.goal_tile.y})",
            f"- walkable tiles: {runtime_map.walkable_tile_count}",
            f"- blocked tiles: {runtime_map.blocked_tile_count}",
            "",
            "Tactical:",
            f"- combat zones: {tactical.combat_zones}",
            f"- cover points: {tactical.cover_points}",
            f"- choke points: {tactical.choke_points}",
            f"- flank routes: {tactical.flank_routes}",
            f"- enemy spawns: {tactical.enemy_spawn_zones}",
            f"- fallback positions: {tactical.fallback_positions}",
            "",
            "Runtime objects:",
            f"- total: {objects.total_objects}",
            f"- types: {dict(objects.counts_by_type)}",
            f"- movement blockers: {objects.movement_blockers}",
            f"- projectile blockers: {objects.projectile_blockers}",
            f"- footprint objects: {objects.footprint_objects}",
            f"- interactive objects: {objects.interactive_objects}",
            f"- loot objects: {objects.loot_objects}",
            f"- explosive objects: {objects.explosive_objects}",
            f"- elevation cells: {len(runtime_map.elevation.cells)}",
            "",
            "Structured data:",
            f"- runtime grids: {runtime_map.runtime_grids.grid_names}",
            f"- gameplay zones: {len(runtime_map.gameplay_zones)}",
            f"- gameplay zone types: {gameplay_zone_types}",
            f"- gameplay zone coverage tiles: {runtime_map.gameplay_zone_coverage_tiles}",
            f"- elevation features: {len(runtime_map.elevation_features)}",
            f"- elevation transitions: {len(runtime_map.elevation_transitions)}",
            "",
            "Validation:",
            f"- status: {report.status}",
            f"- errors: {len(report.errors)}",
            f"- warnings: {len(report.warnings)}",
            f"- warning codes: {warning_codes}",
        ],
    )
