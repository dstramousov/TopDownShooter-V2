"""Visual scene preset assignment for prepared map baking."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class VisualScenePresetResult:
    """Visual scene preset assignment output.

    Attributes:
        scene_presets: Per-scene preset assignment artifact.
        preset_report: Compact preset assignment report.
        preset_summary: Human-readable preset assignment summary.
    """

    scene_presets: dict[str, Any]
    preset_report: dict[str, Any]
    preset_summary: str


class VisualScenePresetAssigner:
    """Assign deterministic visual dressing presets to accepted scenes."""

    PROFILE_ALIASES = {
        "dark_forest": "forest_ruins",
        "forest_ruins": "forest_ruins",
        "clear_map": "forest_ruins",
    }

    PRESET_RULES: dict[str, dict[str, Any]] = {
        "main_clearing": {
            "preset_id": "forest_clearing_light",
            "preset_family": "clearing",
            "description": "Open playable clearing with sparse forest debris and readable ground.",
            "dressing_budget": {
                "large_props": 0,
                "medium_props": 2,
                "small_decals": 10,
            },
            "required_visual_families": [
                "fallen_log",
                "stone_chunk",
                "bush_thicket",
            ],
            "allowed_decal_families": [
                "grass_wear",
                "leaf_noise",
                "small_stones",
            ],
        },
        "road_junction": {
            "preset_id": "road_junction_forest_ruins",
            "preset_family": "roadside",
            "description": "Old road junction with worn edges, stones, and sparse debris.",
            "dressing_budget": {
                "large_props": 0,
                "medium_props": 3,
                "small_decals": 12,
            },
            "required_visual_families": [
                "stone_chunk",
                "scrap_pile",
                "warning_sign",
            ],
            "allowed_decal_families": [
                "road_wear",
                "roadside_stones",
                "grass_intrusion",
            ],
        },
        "ruin_cluster": {
            "preset_id": "small_ruin_site",
            "preset_family": "ruins",
            "description": "Ruin cluster with rubble, moss, broken props, and readable blockers.",
            "dressing_budget": {
                "large_props": 1,
                "medium_props": 4,
                "small_decals": 16,
            },
            "required_visual_families": [
                "stone_chunk",
                "scrap_pile",
                "rusted_barrel",
                "old_grave_marker",
            ],
            "allowed_decal_families": [
                "rubble",
                "moss",
                "cracks",
                "wall_shadow",
            ],
        },
        "water_lowland": {
            "preset_id": "water_lowland_mud",
            "preset_family": "wetland",
            "description": "Wet lowland with muddy banks, reeds, and damp forest debris.",
            "dressing_budget": {
                "large_props": 0,
                "medium_props": 2,
                "small_decals": 14,
            },
            "required_visual_families": [
                "bush_thicket",
                "fallen_log",
                "stone_chunk",
            ],
            "allowed_decal_families": [
                "mud",
                "wet_grass",
                "reeds",
                "small_stones",
            ],
        },
    }

    def assign(
        self,
        *,
        profile: str,
        scene_ranking: dict[str, Any],
        object_families: dict[str, Any],
    ) -> VisualScenePresetResult:
        """Assign preset metadata to accepted visual scenes.

        Args:
            profile: Source visual/game profile name.
            scene_ranking: Ranked scene artifact from ``VisualQualityAnalyzer``.
            object_families: Object family index from ``VisualObjectFamilyResolver``.

        Returns:
            Preset assignment result with JSON-serializable artifacts.
        """
        normalized_profile = self._normalize_profile(profile)
        accepted_scenes = self._accepted_scene_items(scene_ranking)
        assigned_scenes = [
            self._assign_scene(
                scene=scene,
                normalized_profile=normalized_profile,
                available_families=self._available_object_families(object_families),
            )
            for scene in accepted_scenes
        ]
        scene_presets = self._build_scene_presets(
            profile=profile,
            normalized_profile=normalized_profile,
            assigned_scenes=assigned_scenes,
        )
        report = self._build_report(scene_presets)
        summary = self.format_summary(report)
        return VisualScenePresetResult(
            scene_presets=scene_presets,
            preset_report=report,
            preset_summary=summary,
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format scene preset coverage as readable text.

        Args:
            report: Preset assignment report dictionary.

        Returns:
            Human-readable summary.
        """
        coverage = self._dict_value(report, "preset_coverage")
        preset_counts = self._dict_value(coverage, "preset_counts_by_id")
        top_presets = ", ".join(
            f"{preset_id}:{count}"
            for preset_id, count in list(preset_counts.items())[:8]
        )
        if not top_presets:
            top_presets = "none"
        return "\n".join(
            [
                "Visual scene presets",
                f"- status: {report.get('status', 'unknown')}",
                f"- scenes: {coverage.get('total_scenes', 'unknown')}",
                f"- assigned scenes: {coverage.get('assigned_scenes', 'unknown')}",
                f"- unassigned scenes: {coverage.get('unassigned_scenes', 'unknown')}",
                f"- assigned ratio: {coverage.get('assigned_ratio_percent', 'unknown')}%",
                f"- top presets: {top_presets}",
            ],
        )

    def _build_scene_presets(
        self,
        *,
        profile: str,
        normalized_profile: str,
        assigned_scenes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the full scene preset artifact.

        Args:
            profile: Source profile name.
            normalized_profile: Normalized preset profile.
            assigned_scenes: Assigned scene entries.

        Returns:
            Scene presets artifact.
        """
        status_counts = Counter(str(scene["assignment_status"]) for scene in assigned_scenes)
        preset_counts = Counter(
            str(scene["preset_id"])
            for scene in assigned_scenes
            if scene["assignment_status"] == "assigned"
        )
        scene_type_counts = Counter(str(scene["scene_type"]) for scene in assigned_scenes)
        missing_scene_types = sorted(
            {
                str(scene["scene_type"])
                for scene in assigned_scenes
                if scene["assignment_status"] != "assigned"
            },
        )
        required_family_counts: Counter[str] = Counter()
        missing_family_counts: Counter[str] = Counter()
        for scene in assigned_scenes:
            required_family_counts.update(
                str(family) for family in scene.get("required_visual_families", [])
            )
            missing_family_counts.update(
                str(family) for family in scene.get("missing_current_families", [])
            )

        return {
            "schema_version": "visual-scene-presets-v1",
            "profile": profile,
            "normalized_profile": normalized_profile,
            "preset_rules_version": "forest-ruins-scene-presets-v1",
            "scenes": assigned_scenes,
            "summary": {
                "total_scenes": len(assigned_scenes),
                "assigned_scenes": status_counts["assigned"],
                "unassigned_scenes": len(assigned_scenes) - status_counts["assigned"],
                "assignment_counts": dict(sorted(status_counts.items())),
                "scene_type_counts": dict(sorted(scene_type_counts.items())),
                "preset_counts_by_id": dict(sorted(preset_counts.items())),
                "missing_scene_types": missing_scene_types,
                "required_family_counts": dict(sorted(required_family_counts.items())),
                "missing_current_family_counts": dict(sorted(missing_family_counts.items())),
            },
        }

    def _assign_scene(
        self,
        *,
        scene: dict[str, Any],
        normalized_profile: str,
        available_families: set[str],
    ) -> dict[str, Any]:
        """Assign one accepted scene to a preset rule.

        Args:
            scene: Accepted scene dictionary.
            normalized_profile: Normalized preset profile name.
            available_families: Families already observed in visual objects.

        Returns:
            Scene assignment entry.
        """
        scene_type = self._string_value(scene.get("scene_type"), default="generic_scene")
        rule = self.PRESET_RULES.get(scene_type)
        if rule is None:
            required_families: list[str] = []
            missing_families: list[str] = []
            return {
                "id": self._string_value(scene.get("id"), default="scene_unknown"),
                "source_scene_id": self._string_value(scene.get("id"), default="scene_unknown"),
                "source_candidate_id": self._string_value(
                    scene.get("source_candidate_id"),
                    default="unknown",
                ),
                "scene_type": scene_type,
                "preset_id": "generic_scene_review",
                "preset_family": "review",
                "preset_profile": normalized_profile,
                "assignment_status": "missing_preset",
                "score": self._int_value(scene.get("score"), default=0),
                "priority": self._int_value(scene.get("priority"), default=0),
                "bounds": self._dict_value(scene, "bounds"),
                "center": self._dict_value(scene, "center"),
                "dressing_budget": {"large_props": 0, "medium_props": 0, "small_decals": 0},
                "required_visual_families": required_families,
                "missing_current_families": missing_families,
                "allowed_decal_families": [],
                "notes": ["No preset rule exists for this scene type."],
                "next_stage": "scene_preset_rule_definition",
            }

        required_families = self._string_list(rule.get("required_visual_families"))
        missing_families = [
            family for family in required_families if family not in available_families
        ]
        return {
            "id": self._string_value(scene.get("id"), default="scene_unknown"),
            "source_scene_id": self._string_value(scene.get("id"), default="scene_unknown"),
            "source_candidate_id": self._string_value(
                scene.get("source_candidate_id"),
                default="unknown",
            ),
            "scene_type": scene_type,
            "candidate_type": self._string_value(scene.get("candidate_type"), default="unknown"),
            "preset_id": self._string_value(rule.get("preset_id"), default="generic_scene"),
            "preset_family": self._string_value(rule.get("preset_family"), default="generic"),
            "preset_profile": normalized_profile,
            "assignment_status": "assigned",
            "score": self._int_value(scene.get("score"), default=0),
            "priority": self._int_value(scene.get("priority"), default=0),
            "bounds": self._dict_value(scene, "bounds"),
            "center": self._dict_value(scene, "center"),
            "dressing_budget": self._dict_value(rule, "dressing_budget"),
            "required_visual_families": required_families,
            "missing_current_families": missing_families,
            "allowed_decal_families": self._string_list(rule.get("allowed_decal_families")),
            "description": self._string_value(rule.get("description"), default=""),
            "next_stage": "scene_dressing_generation",
        }

    def _build_report(self, scene_presets: dict[str, Any]) -> dict[str, Any]:
        """Build compact scene preset report.

        Args:
            scene_presets: Full scene presets artifact.

        Returns:
            Compact report dictionary.
        """
        summary = self._dict_value(scene_presets, "summary")
        total_scenes = self._int_value(summary.get("total_scenes"), default=0)
        assigned_scenes = self._int_value(summary.get("assigned_scenes"), default=0)
        unassigned_scenes = self._int_value(summary.get("unassigned_scenes"), default=0)
        assigned_ratio = self._ratio_percent(assigned_scenes, total_scenes)
        if unassigned_scenes > 0:
            status = "needs_work"
        elif total_scenes == 0:
            status = "warning"
        else:
            status = "ok"

        checks = [
            self._check(
                "scene_preset_assignment",
                "passed" if assigned_scenes > 0 or total_scenes == 0 else "warning",
                "Accepted scenes should be assigned to deterministic preset rules.",
            ),
            self._check(
                "scene_preset_coverage",
                status,
                "Every accepted scene type should have a known visual preset.",
            ),
        ]
        return {
            "schema_version": "visual-scene-preset-report-v1",
            "status": status,
            "profile": scene_presets.get("profile", "unknown"),
            "normalized_profile": scene_presets.get("normalized_profile", "unknown"),
            "preset_coverage": {
                "total_scenes": total_scenes,
                "assigned_scenes": assigned_scenes,
                "unassigned_scenes": unassigned_scenes,
                "assigned_ratio_percent": assigned_ratio,
                "assignment_counts": self._dict_value(summary, "assignment_counts"),
                "scene_type_counts": self._dict_value(summary, "scene_type_counts"),
                "preset_counts_by_id": self._dict_value(summary, "preset_counts_by_id"),
                "missing_scene_types": summary.get("missing_scene_types", []),
            },
            "family_requirements": {
                "required_family_counts": self._dict_value(summary, "required_family_counts"),
                "missing_current_family_counts": self._dict_value(
                    summary,
                    "missing_current_family_counts",
                ),
            },
            "checks": checks,
        }

    def _accepted_scene_items(self, scene_ranking: dict[str, Any]) -> list[dict[str, Any]]:
        """Return accepted scene dictionaries from a ranking artifact.

        Args:
            scene_ranking: Visual scene ranking dictionary.

        Returns:
            Accepted scene dictionaries.
        """
        scenes = scene_ranking.get("accepted_scenes")
        if not isinstance(scenes, list):
            return []
        return [scene for scene in scenes if isinstance(scene, dict)]

    def _available_object_families(self, object_families: dict[str, Any]) -> set[str]:
        """Return currently observed object families from a family artifact.

        Args:
            object_families: Visual object family artifact.

        Returns:
            Set of observed family names.
        """
        summary = self._dict_value(object_families, "summary")
        family_counts = self._dict_value(summary, "family_counts")
        return {str(family) for family in family_counts if str(family)}

    def _normalize_profile(self, profile: str) -> str:
        """Normalize source profile to a preset profile.

        Args:
            profile: Source profile label.

        Returns:
            Normalized preset profile label.
        """
        stripped_profile = profile.strip() if isinstance(profile, str) else ""
        return self.PROFILE_ALIASES.get(stripped_profile, stripped_profile or "forest_ruins")

    def _check(self, code: str, status: str, message: str) -> dict[str, str]:
        """Build a preset assignment check entry.

        Args:
            code: Stable check code.
            status: Check status.
            message: Human-readable check message.

        Returns:
            Check dictionary.
        """
        return {"code": code, "status": status, "message": message}

    def _dict_value(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        """Return a nested dictionary value.

        Args:
            data: Source dictionary.
            key: Key to read.

        Returns:
            Nested dictionary or empty dictionary.
        """
        value = data.get(key)
        return value if isinstance(value, dict) else {}

    def _int_value(self, value: Any, *, default: int) -> int:
        """Return an integer from raw JSON-like data.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Integer value or fallback.
        """
        return value if isinstance(value, int) and not isinstance(value, bool) else default

    def _ratio_percent(self, numerator: int, denominator: int) -> float:
        """Return a rounded percentage value.

        Args:
            numerator: Ratio numerator.
            denominator: Ratio denominator.

        Returns:
            Percentage rounded to two decimals.
        """
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100.0, 2)

    def _string_list(self, value: Any) -> list[str]:
        """Return a list of non-empty strings.

        Args:
            value: Raw JSON-like value.

        Returns:
            String list.
        """
        if not isinstance(value, list):
            return []
        strings: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                strings.append(item.strip())
        return strings

    def _string_value(self, value: Any, *, default: str) -> str:
        """Return a stripped string from raw JSON-like data.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            String value or fallback.
        """
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default
