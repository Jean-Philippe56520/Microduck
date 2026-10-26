"""F6-C: opt-in, HOST-ONLY rate/resource gate for the existing F2-D supervisor.

The gate has no reader, socket, motor, SQLite, battery, temperature or PC
access. It accepts caller-supplied monotonic timestamps and PREVIOUS measured
process reports. It is *not* a real-time watchdog: Python/SQLite can still
block during a cycle and a completed write cannot be undone.

F6-C limits are POLICY EXAMPLES for fictional offline cycles, never measured
headroom or safe physical settings on RK3566. The gate does not queue frames:
over-budget batches are dropped whole BEFORE cognition or SQLite commits.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .passive_resilience import PassiveCycleReport


def _finite_nonnegative(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


@dataclass(frozen=True)
class OfflineBudgetLimits:
    """Process-local, voluntary controls for *fictional* passive cycles."""

    window_s: float = 10.0
    min_cycle_gap_s: float = 0.5
    max_window_cycles: int = 8
    max_window_events: int = 32
    cooldown_s: float = 5.0
    max_cycle_cpu_ms: float | None = None
    max_process_peak_rss_kib: int | None = None

    def __post_init__(self) -> None:
        for name in ("window_s", "cooldown_s"):
            value = getattr(self, name)
            if not _finite_nonnegative(value) or value <= 0 or value > 3600:
                raise ValueError(f"{name} must be a finite positive policy bound")
        if (not _finite_nonnegative(self.min_cycle_gap_s)
                or self.min_cycle_gap_s > self.window_s):
            raise ValueError("invalid minimum cycle gap")
        if (type(self.max_window_cycles) is not int
                or not 1 <= self.max_window_cycles <= 512):
            raise ValueError("invalid window cycle quota")
        if (type(self.max_window_events) is not int
                or not 1 <= self.max_window_events <= 8192):
            raise ValueError("invalid window event quota")
        if self.max_cycle_cpu_ms is not None and (
                not _finite_nonnegative(self.max_cycle_cpu_ms)
                or self.max_cycle_cpu_ms <= 0
                or self.max_cycle_cpu_ms > 5000):
            raise ValueError("invalid CPU policy threshold")
        if self.max_process_peak_rss_kib is not None and (
                type(self.max_process_peak_rss_kib) is not int
                or not 1 <= self.max_process_peak_rss_kib <= 4 * 1024 * 1024):
            raise ValueError("invalid process RSS policy threshold")


@dataclass(frozen=True)
class OfflineBudgetSnapshot:
    """Counters describe admissions and measured host reports, not actions."""

    admitted_cycles_in_window: int
    admitted_events_in_window: int
    refused: tuple[tuple[str, int], ...]
    completed_reports: int
    cooldown_until_monotonic_s: float
    latched_resource_failure: str | None
    pending_cycle: bool
    real_sensor_reads: int = 0
    pc_queries: int = 0
    motor_commands: int = 0

    def __post_init__(self) -> None:
        if (self.real_sensor_reads != 0 or self.pc_queries != 0
                or self.motor_commands != 0):
            raise ValueError("an offline gate never controls external hardware")


class OfflineResourceGate:
    """One process-local token/window gate for one PassiveCycleSupervisor.

    admit_cycle() MUST precede source.read(); admit_events() follows a fresh
    F1-B read and precedes F2 cognition and SQLite. report() closes the
    reservation even on failures. It is deliberately single-threaded; a
    concurrent or repeated start is denied, never queued.
    """

    def __init__(self, limits: OfflineBudgetLimits | None = None) -> None:
        self.limits = limits if limits is not None else OfflineBudgetLimits()
        if not isinstance(self.limits, OfflineBudgetLimits):
            raise TypeError("F6-C limits required")
        self._cycles: deque[float] = deque()
        self._events: deque[tuple[float, int]] = deque()
        self._last_clock: float | None = None
        self._last_admitted: float | None = None
        self._pending_at: float | None = None
        self._cooldown_until = 0.0
        self._latch: str | None = None
        self._refused: dict[str, int] = {}
        self._reports = 0

    def _refuse(self, reason: str) -> str:
        self._refused[reason] = self._refused.get(reason, 0) + 1
        return reason

    def _clock(self, now: object) -> str | None:
        if not _finite_nonnegative(now):
            return self._refuse("budget_invalid_clock")
        t = float(now)
        if self._last_clock is not None and t < self._last_clock:
            self._latch = "budget_clock_reset"
        self._last_clock = t
        return None

    def _prune(self, now: float) -> None:
        threshold = now - self.limits.window_s
        while self._cycles and self._cycles[0] <= threshold:
            self._cycles.popleft()
        while self._events and self._events[0][0] <= threshold:
            self._events.popleft()

    def admit_cycle(self, now_monotonic_s: float) -> str | None:
        """None means reserved, else precise idle status; no source read."""
        invalid = self._clock(now_monotonic_s)
        if invalid:
            return invalid
        now = float(now_monotonic_s)
        if self._latch is not None:
            return self._refuse(self._latch)
        if self._pending_at is not None:
            return self._refuse("budget_cycle_inflight")
        self._prune(now)
        if now < self._cooldown_until:
            return self._refuse("budget_cooldown")
        if (self._last_admitted is not None
                and now - self._last_admitted < self.limits.min_cycle_gap_s):
            return self._refuse("budget_cycle_gap")
        if len(self._cycles) >= self.limits.max_window_cycles:
            return self._refuse("budget_window_cycles")
        self._cycles.append(now)
        self._last_admitted = now
        self._pending_at = now
        return None

    def admit_events(self, count: int) -> str | None:
        """Drop over-budget batch BEFORE cognition and memory writes."""
        if self._pending_at is None:
            return self._refuse("budget_no_cycle")
        if type(count) is not int or not 0 <= count <= 64:
            return self._refuse("budget_invalid_events")
        current = sum(n for _, n in self._events)
        if current + count > self.limits.max_window_events:
            return self._refuse("budget_window_events")
        self._events.append((self._pending_at, count))
        return None

    def report(self, report: PassiveCycleReport, *,
               now_monotonic_s: float) -> None:
        """Post-hoc resource sampling cannot cancel past SQLite commits.

        Unknown RSS is acceptable only when NO RSS threshold was configured.
        If configured, unknown RSS or high-water-limit exceedance latches this
        session. A CPU or latency overrun schedules a future cooldown.
        """
        if self._pending_at is None:
            return
        self._pending_at = None
        self._reports += 1
        if self._clock(now_monotonic_s):
            self._latch = "budget_clock_unavailable"
            return
        now = float(now_monotonic_s)
        cpu = report.process_cpu_ms
        rss = report.process_peak_rss_kib
        if not _finite_nonnegative(cpu):
            self._latch = "budget_missing_cpu"
        elif (self.limits.max_cycle_cpu_ms is not None
                and cpu > self.limits.max_cycle_cpu_ms):
            self._cooldown_until = max(
                self._cooldown_until, now + self.limits.cooldown_s)
        if self.limits.max_process_peak_rss_kib is not None:
            if type(rss) is not int or rss <= 0:
                self._latch = "budget_missing_rss"
            elif rss > self.limits.max_process_peak_rss_kib:
                # ru_maxrss is a PROCESS high-water mark on Linux, so it
                # cannot be made smaller by waiting out a short cooldown.
                self._latch = "budget_rss_limit"
        if report.status in {
            "late_source", "late_before_commit", "late_after_commit",
        }:
            self._cooldown_until = max(
                self._cooldown_until, now + self.limits.cooldown_s)

    def snapshot(self) -> OfflineBudgetSnapshot:
        return OfflineBudgetSnapshot(
            admitted_cycles_in_window=len(self._cycles),
            admitted_events_in_window=sum(n for _, n in self._events),
            refused=tuple(sorted(self._refused.items())),
            completed_reports=self._reports,
            cooldown_until_monotonic_s=self._cooldown_until,
            latched_resource_failure=self._latch,
            pending_cycle=self._pending_at is not None,
        )
