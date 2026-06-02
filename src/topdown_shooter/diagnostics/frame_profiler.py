"""Lightweight frame timing diagnostics for interactive runtimes."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import time


@dataclass(frozen=True, slots=True)
class FrameProfilerConfig:
    """Frame profiler settings.

    Attributes:
        enabled: Whether frame profiling is enabled.
        log_interval_seconds: Seconds between console reports.
        slow_frame_threshold_ms: Frame duration threshold used by reports.
        draw_overlay: Whether a small profiler overlay is drawn in the runtime window.
        sample_window_size: Number of recent frames used for rolling averages.
    """

    enabled: bool
    log_interval_seconds: float
    slow_frame_threshold_ms: float
    draw_overlay: bool
    sample_window_size: int


@dataclass(frozen=True, slots=True)
class FrameProfilerSectionStats:
    """Rolling timing statistics for one measured section.

    Attributes:
        last_ms: Last measured section duration in milliseconds.
        average_ms: Average duration across the current sample window.
        max_ms: Maximum duration across the current sample window.
    """

    last_ms: float
    average_ms: float
    max_ms: float


@dataclass(frozen=True, slots=True)
class FrameProfilerSnapshot:
    """Profiler data prepared for rendering or logging.

    Attributes:
        frame_last_ms: Last full frame duration in milliseconds.
        frame_average_ms: Average full frame duration across the sample window.
        frame_max_ms: Maximum full frame duration across the sample window.
        sections: Section timing statistics keyed by section name.
        counters: Latest runtime counters keyed by counter name.
        slow_frame_threshold_ms: Slow frame threshold in milliseconds.
    """

    frame_last_ms: float
    frame_average_ms: float
    frame_max_ms: float
    sections: dict[str, FrameProfilerSectionStats]
    counters: dict[str, int | float | str | bool]
    slow_frame_threshold_ms: float


class FrameProfiler:
    """Collect low-overhead per-frame runtime timing diagnostics."""

    def __init__(self, config: FrameProfilerConfig, label: str) -> None:
        """Initialize the profiler.

        Args:
            config: Profiler settings.
            label: Short runtime label included in console reports.
        """
        self._config = config
        self._label = label
        sample_window_size = max(1, config.sample_window_size)
        self._frame_samples_ms: deque[float] = deque(maxlen=sample_window_size)
        self._section_samples_ms: dict[str, deque[float]] = {}
        self._current_sections_ms: dict[str, float] = {}
        self._current_counters: dict[str, int | float | str | bool] = {}
        self._frame_start_seconds = 0.0
        self._last_log_seconds = time.perf_counter()
        self._last_snapshot = FrameProfilerSnapshot(
            frame_last_ms=0.0,
            frame_average_ms=0.0,
            frame_max_ms=0.0,
            sections={},
            counters={},
            slow_frame_threshold_ms=config.slow_frame_threshold_ms,
        )

    @property
    def enabled(self) -> bool:
        """Return whether profiling is enabled."""
        return self._config.enabled

    @property
    def draw_overlay(self) -> bool:
        """Return whether the runtime should draw profiler overlay lines."""
        return self._config.enabled and self._config.draw_overlay

    def begin_frame(self) -> None:
        """Start collecting data for the current frame."""
        if not self._config.enabled:
            return
        self._current_sections_ms = {}
        self._current_counters = {}
        self._frame_start_seconds = time.perf_counter()

    @contextmanager
    def section(self, name: str) -> Iterator[None]:
        """Measure one named frame section.

        Args:
            name: Stable section identifier used in reports.
        """
        if not self._config.enabled:
            yield
            return
        started_at = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            self._current_sections_ms[name] = (
                self._current_sections_ms.get(name, 0.0) + elapsed_ms
            )

    def set_counter(self, name: str, value: int | float | str | bool) -> None:
        """Store a runtime counter for the current frame.

        Args:
            name: Counter identifier.
            value: Counter value to show in diagnostics.
        """
        if not self._config.enabled:
            return
        self._current_counters[name] = value

    def end_frame(self) -> None:
        """Finish current frame profiling and emit periodic console reports."""
        if not self._config.enabled or self._frame_start_seconds <= 0.0:
            return
        now = time.perf_counter()
        frame_ms = (now - self._frame_start_seconds) * 1000.0
        self._frame_samples_ms.append(frame_ms)
        for name, elapsed_ms in self._current_sections_ms.items():
            samples = self._section_samples_ms.setdefault(
                name,
                deque(maxlen=max(1, self._config.sample_window_size)),
            )
            samples.append(elapsed_ms)
        self._last_snapshot = self._build_snapshot()
        if now - self._last_log_seconds >= self._config.log_interval_seconds:
            self._last_log_seconds = now
            self._print_report(self._last_snapshot)

    def snapshot(self) -> FrameProfilerSnapshot:
        """Return the last completed frame profiler snapshot."""
        return self._last_snapshot

    def overlay_lines(self) -> tuple[str, ...]:
        """Return compact diagnostic lines suitable for drawing in the HUD."""
        if not self.draw_overlay:
            return ()
        snapshot = self._last_snapshot
        lines = [
            (
                "prof frame "
                f"last={snapshot.frame_last_ms:.1f}ms "
                f"avg={snapshot.frame_average_ms:.1f}ms "
                f"max={snapshot.frame_max_ms:.1f}ms"
            ),
        ]
        sorted_sections = sorted(
            snapshot.sections.items(),
            key=lambda item: item[1].average_ms,
            reverse=True,
        )
        for name, stats in sorted_sections[:8]:
            lines.append(f"{name}: {stats.last_ms:.1f}/{stats.average_ms:.1f}ms")
        if snapshot.counters:
            counter_text = " ".join(
                f"{name}={value}" for name, value in sorted(snapshot.counters.items())
            )
            lines.append(counter_text)
        return tuple(lines)

    def _build_snapshot(self) -> FrameProfilerSnapshot:
        section_stats: dict[str, FrameProfilerSectionStats] = {}
        for name, samples in self._section_samples_ms.items():
            if not samples:
                continue
            section_stats[name] = FrameProfilerSectionStats(
                last_ms=samples[-1],
                average_ms=sum(samples) / len(samples),
                max_ms=max(samples),
            )
        return FrameProfilerSnapshot(
            frame_last_ms=self._frame_samples_ms[-1] if self._frame_samples_ms else 0.0,
            frame_average_ms=(
                sum(self._frame_samples_ms) / len(self._frame_samples_ms)
                if self._frame_samples_ms
                else 0.0
            ),
            frame_max_ms=max(self._frame_samples_ms) if self._frame_samples_ms else 0.0,
            sections=section_stats,
            counters=dict(self._current_counters),
            slow_frame_threshold_ms=self._config.slow_frame_threshold_ms,
        )

    def _print_report(self, snapshot: FrameProfilerSnapshot) -> None:
        section_parts = []
        for name, stats in sorted(
            snapshot.sections.items(),
            key=lambda item: item[1].average_ms,
            reverse=True,
        )[:10]:
            section_parts.append(f"{name}={stats.average_ms:.2f}ms")
        counters = " ".join(
            f"{name}={value}" for name, value in sorted(snapshot.counters.items())
        )
        sections = " ".join(section_parts)
        slow = " SLOW" if snapshot.frame_average_ms >= snapshot.slow_frame_threshold_ms else ""
        print(
            f"[frame_profiler:{self._label}]{slow} "
            f"frame_avg={snapshot.frame_average_ms:.2f}ms "
            f"frame_last={snapshot.frame_last_ms:.2f}ms "
            f"frame_max={snapshot.frame_max_ms:.2f}ms "
            f"{sections} {counters}".rstrip(),
            flush=True,
        )
