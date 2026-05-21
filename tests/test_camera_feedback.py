"""Tests for shared camera feedback impulses."""

from topdown_shooter.combat.projectiles import (
    ProjectileEvent,
    ProjectileEventType,
    ProjectileOwner,
)
from topdown_shooter.gameplay.camera_feedback import CameraFeedbackSystem
from topdown_shooter.gameplay.explosions import RuntimeExplosionResult
from topdown_shooter.world.coordinates import WorldCoord


def test_camera_feedback_adds_player_shot_recoil() -> None:
    """Player shots should create a short camera feedback impulse."""
    feedback = CameraFeedbackSystem()
    event = ProjectileEvent(
        event_type=ProjectileEventType.SPAWNED,
        position=WorldCoord(10.0, 10.0),
        owner=ProjectileOwner.PLAYER,
        direction_x=1.0,
        direction_y=0.0,
        visual_profile="pistol",
    )

    feedback.add_projectile_events(
        (event,),
        player_position=WorldCoord(10.0, 10.0),
        tile_size_px=16,
    )
    feedback.update(0.01)

    assert feedback.active_impulses == 1
    assert abs(feedback.offset.x) > 0.0 or abs(feedback.offset.y) > 0.0


def test_camera_feedback_ignores_enemy_spawn_recoil() -> None:
    """Enemy shot spawn events should not shake the player camera by themselves."""
    feedback = CameraFeedbackSystem()
    event = ProjectileEvent(
        event_type=ProjectileEventType.SPAWNED,
        position=WorldCoord(10.0, 10.0),
        owner=ProjectileOwner.ENEMY,
        direction_x=1.0,
        direction_y=0.0,
        visual_profile="enemy",
    )

    feedback.add_projectile_events(
        (event,),
        player_position=WorldCoord(10.0, 10.0),
        tile_size_px=16,
    )
    feedback.update(0.01)

    assert feedback.active_impulses == 0
    assert feedback.offset.x == 0.0
    assert feedback.offset.y == 0.0


def test_camera_feedback_clamps_near_explosion_offset() -> None:
    """Close explosions should produce a clamped screen punch."""
    feedback = CameraFeedbackSystem()
    explosion = RuntimeExplosionResult(
        object_id="barrel_001",
        object_type="rusted_barrel",
        position=WorldCoord(32.0, 32.0),
        radius_px=48.0,
    )

    feedback.add_explosions(
        (explosion,),
        player_position=WorldCoord(32.0, 32.0),
        tile_size_px=16,
    )
    feedback.update(0.01)

    assert feedback.active_impulses == 1
    assert abs(feedback.offset.x) <= 10.0
    assert abs(feedback.offset.y) <= 10.0
