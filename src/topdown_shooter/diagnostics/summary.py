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
    warning_codes = ", ".join(issue.code for issue in report.warnings) or "none"

    return "\n".join(
        [
            "Map package loaded",
            "",
            "Package:",
            f"- generator: {manifest.versions.generator}",
            f"- manifest schema: {manifest.schema_version}",
            f"- tactical schema: {manifest.versions.schemas.get('tactical_map', 'unknown')}",
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
            "Validation:",
            f"- status: {report.status}",
            f"- errors: {len(report.errors)}",
            f"- warnings: {len(report.warnings)}",
            f"- warning codes: {warning_codes}",
        ],
    )
