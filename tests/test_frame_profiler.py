"""Tests for frame profiler diagnostics."""

from topdown_shooter.diagnostics.frame_profiler import FrameProfiler, FrameProfilerConfig


def test_frame_profiler_collects_section_and_counters() -> None:
    """Profiler should expose measured sections and counters after one frame."""
    profiler = FrameProfiler(
        config=FrameProfilerConfig(
            enabled=True,
            log_interval_seconds=999.0,
            slow_frame_threshold_ms=25.0,
            draw_overlay=True,
            sample_window_size=8,
        ),
        label="test",
    )

    profiler.begin_frame()
    with profiler.section("update"):
        pass
    profiler.set_counter("enemies", 12)
    profiler.end_frame()

    snapshot = profiler.snapshot()
    assert snapshot.frame_last_ms >= 0.0
    assert "update" in snapshot.sections
    assert snapshot.counters["enemies"] == 12
    assert profiler.overlay_lines()


def test_frame_profiler_disabled_is_noop() -> None:
    """Disabled profiler should not retain sections or overlay lines."""
    profiler = FrameProfiler(
        config=FrameProfilerConfig(
            enabled=False,
            log_interval_seconds=1.0,
            slow_frame_threshold_ms=25.0,
            draw_overlay=True,
            sample_window_size=8,
        ),
        label="test",
    )

    profiler.begin_frame()
    with profiler.section("update"):
        pass
    profiler.set_counter("enemies", 12)
    profiler.end_frame()

    assert profiler.snapshot().sections == {}
    assert profiler.overlay_lines() == ()
