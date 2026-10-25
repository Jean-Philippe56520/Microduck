"""F2-D: bounded MOCK-only cycle supervision, restart-safe SQLite, diagnostics.

A runner is a test/bench harness around the existing F1/F2 brain. It does NOT
execute passive intentions, motors, camera, microphone or PC inference.
Latency and CPU timers describe the HOST process, not a real Microduck.
Budgets are cooperative/post-hoc, never a hard real-time watchdog.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import math
import sys
import sqlite3
import time
from typing import Callable

from .autonomy import AutonomyBrain
from .passive_intentions import PassiveIntent
from .passive_learning import PassiveLearning
from .passive_memory import PassiveObservationJournal
from .passive_sources import FixtureUnixReader, PassiveRead

if sys.platform.startswith("linux"):
    import resource
else:
    resource = None

MAX_METRIC_SAMPLES = 64
_ALLOWED_IDLE = frozenset({
    "no_current_observation", "no_high_scoring_passive_attention",
})


@dataclass(frozen=True)
class PassiveCycleLimits:
    """Per-process budgets, independent of any robot resource claims."""

    max_cycles: int = 16
    max_events: int = 128
    max_read_ms: float = 1000.0
    max_cycle_ms: float = 1500.0

    def __post_init__(self) -> None:
        if (type(self.max_cycles) is not int
                or not 1 <= self.max_cycles <= 512):
            raise ValueError("max_cycles must be in [1,512]")
        if (type(self.max_events) is not int
                or not 1 <= self.max_events <= 8192):
            raise ValueError("max_events must be in [1,8192]")
        for key in ("max_read_ms", "max_cycle_ms"):
            value = getattr(self, key)
            if (type(value) not in (int, float)
                    or not math.isfinite(value) or value <= 0):
                raise ValueError("cycle budgets must be finite positive numbers")
        if (self.max_read_ms > 3000.0
                or not self.max_read_ms <= self.max_cycle_ms <= 5000.0):
            raise ValueError("read/cycle budget limits out of range")


@dataclass(frozen=True)
class PassiveCycleReport:
    """Evidence for one local fixture cycle; not a movement outcome."""

    status: str
    intention: str
    reason: str
    source_events: int
    stored_observations: int
    scored_consequences: int
    source_ms: float
    elapsed_ms: float
    process_cpu_ms: float
    process_peak_rss_kib: int | None
    executed: bool = False
    motor_commands_issued: int = 0


@dataclass(frozen=True)
class PassiveCycleMetrics:
    """Bounded host-process measurements; no real-time or RK3566 guarantee."""

    cycles_attempted: int
    source_events_accepted: int
    stored_observations: int
    scored_consequences: int
    status_counts: tuple[tuple[str, int], ...]
    intention_counts: tuple[tuple[str, int], ...]
    recent_samples: int
    p50_elapsed_ms: float | None
    p95_elapsed_ms: float | None
    max_elapsed_ms: float | None
    mean_process_cpu_ms: float | None
    observed_peak_rss_kib: int | None
    cooldown_blocks: int
    consecutive_active_repeats: int
    simulated_motivation_energy: float


def _p_nearest(samples: tuple[float, ...], percent: float) -> float | None:
    if not samples:
        return None
    sorted_samples = sorted(samples)
    return sorted_samples[max(0, math.ceil(len(sorted_samples) * percent) - 1)]


def _peak_rss_kib() -> int | None:
    # Linux ru_maxrss is KiB and is a process *high-water mark*.
    # macOS uses bytes and Windows is unsupported: do not mislabel either.
    if resource is None:
        return None
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


class PassiveCycleSupervisor:
    """Runs one fixture read at a time, with bounded process-local state.

    The reader must be the existing F1-B Unix fixture adapter. A failure
    results in a non-executed idle report; historical SQLite rows are never
    replayed as live events. Cross-restart F2-C preferences are retrieved
    through the existing memory, not copied into a new database.

    max_read_ms is checked before cognition/SQLite; max_cycle_ms is checked
    after cognition and after commits. It is a *soft* budget: a slow Python or
    SQLite operation cannot be preempted or undone by this wrapper.
    """

    def __init__(
        self, *,
        reader: FixtureUnixReader,
        brain: AutonomyBrain,
        journal: PassiveObservationJournal,
        learning: PassiveLearning,
        limits: PassiveCycleLimits | None = None,
        monotonic_s: Callable[[], float] = time.monotonic,
        wall_epoch_s: Callable[[], float] = time.time,
        perf_counter_ns: Callable[[], int] = time.perf_counter_ns,
        process_time_ns: Callable[[], int] = time.process_time_ns,
    ) -> None:
        if not isinstance(reader, FixtureUnixReader):
            raise TypeError("F2-D requires the F1-B Unix fixture reader")
        if not isinstance(brain, AutonomyBrain):
            raise TypeError("F2-D requires the existing brain")
        if not isinstance(journal, PassiveObservationJournal):
            raise TypeError("F2-D requires the F1-C journal")
        if not isinstance(learning, PassiveLearning):
            raise TypeError("F2-D requires the F2-C learning ledger")
        if brain.memory is not journal._memory or learning._memory is not brain.memory:
            raise ValueError("brain, journal and learning require one SQLite")
        if limits is not None and not isinstance(limits, PassiveCycleLimits):
            raise TypeError("invalid F2-D limits")
        if not all(callable(fn) for fn in
                   (monotonic_s, wall_epoch_s, perf_counter_ns, process_time_ns)):
            raise TypeError("clocks must be callable")
        self.reader = reader
        self.brain = brain
        self.journal = journal
        self.learning = learning
        self.limits = limits or PassiveCycleLimits()
        self._mono = monotonic_s
        self._wall = wall_epoch_s
        self._perf = perf_counter_ns
        self._cpu = process_time_ns
        self._attempted = 0
        self._accepted_events = 0
        self._stored = 0
        self._scored = 0
        self._status: Counter[str] = Counter()
        self._intents: Counter[str] = Counter()
        self._samples: deque[tuple[float, float]] = deque(
            maxlen=MAX_METRIC_SAMPLES)

    def _report(
        self, *, status: str, intention: PassiveIntent,
        start_ns: int, start_cpu_ns: int, source_ms: float = 0.0,
        source_events: int = 0, stored: int = 0, scored: int = 0,
    ) -> PassiveCycleReport:
        elapsed_ms = max(0.0, (self._perf() - start_ns) / 1e6)
        cpu_ms = max(0.0, (self._cpu() - start_cpu_ns) / 1e6)
        report = PassiveCycleReport(
            status=status, intention=intention.intention,
            reason=intention.reason, source_events=source_events,
            stored_observations=stored, scored_consequences=scored,
            source_ms=source_ms, elapsed_ms=elapsed_ms,
            process_cpu_ms=cpu_ms, process_peak_rss_kib=_peak_rss_kib(),
        )
        self._status[status] += 1
        self._intents[report.intention] += 1
        self._samples.append((elapsed_ms, cpu_ms))
        return report

    @staticmethod
    def _idle(reason: str) -> PassiveIntent:
        return PassiveIntent("idle", reason)

    def run_once(self) -> PassiveCycleReport:
        """At most one fresh socket read and one bound cognitive proposal."""
        start_ns, start_cpu_ns = self._perf(), self._cpu()
        if self._attempted >= self.limits.max_cycles:
            return self._report(
                status="quota_cycles", intention=self._idle("cycle_quota"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns)
        self._attempted += 1
        try:
            # Check the existing SQLite before any cognitive change or read.
            self.brain.memory.conn.execute("SELECT 1").fetchone()
        except sqlite3.Error:
            return self._report(
                status="storage_unavailable",
                intention=self._idle("storage_unavailable"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns)
        source_started_ns = self._perf()
        try:
            reading = self.reader.read()
        except Exception:
            return self._report(
                status="source_exception", intention=self._idle("source_failed"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns)
        source_ms = max(0.0, (self._perf() - source_started_ns) / 1e6)
        if source_ms > self.limits.max_read_ms:
            return self._report(
                status="late_source", intention=self._idle("read_budget_exceeded"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns,
                source_ms=source_ms)
        if not isinstance(reading, PassiveRead) or reading.status != "ok":
            return self._report(
                status="source_unavailable",
                intention=self._idle("source_unavailable"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns,
                source_ms=source_ms)
        # F1-B validation is repeated inside F2-B; status alone is not proof.
        event_count = len(getattr(reading.snapshot, "events", ()))
        if self._accepted_events + event_count > self.limits.max_events:
            return self._report(
                status="quota_events",
                intention=self._idle("event_quota"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns,
                source_ms=source_ms)
        try:
            now_mono, now_wall = self._mono(), self._wall()
            proposed = self.brain.propose_balanced_passive(
                reading, journal=self.journal, learning=self.learning,
                now_monotonic_s=now_mono, now_wall_epoch_s=now_wall)
        except (sqlite3.Error, ValueError, TypeError):
            return self._report(
                status="planning_unavailable",
                intention=self._idle("planning_unavailable"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns,
                source_ms=source_ms)
        # A rejected, rate-limited or stale read cannot enter durable memory.
        if (proposed.intention == "idle" and proposed.reason not in _ALLOWED_IDLE):
            return self._report(
                status="invalid_or_deferred", intention=proposed,
                start_ns=start_ns, start_cpu_ns=start_cpu_ns,
                source_ms=source_ms)
        self._accepted_events += event_count
        if max(0.0, (self._perf() - start_ns) / 1e6) > self.limits.max_cycle_ms:
            return self._report(
                status="late_before_commit",
                intention=self._idle("cycle_budget_exceeded"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns,
                source_ms=source_ms, source_events=event_count)
        try:
            stored = self.journal.append(
                reading, now_monotonic_s=now_mono, now_wall_epoch_s=now_wall)
            consequences = self.learning.record(
                journal=self.journal, sequence=reading.sequence,
                now_wall_epoch_s=now_wall) if stored else ()
        except (sqlite3.Error, ValueError, TypeError):
            # SQLite may have journalled the categories before F2-C failed.
            # Never assert transaction-wide exactly-once or a learned outcome.
            return self._report(
                status="storage_unavailable",
                intention=self._idle("storage_unavailable"),
                start_ns=start_ns, start_cpu_ns=start_cpu_ns,
                source_ms=source_ms, source_events=event_count)
        self._stored += stored
        self._scored += len(consequences)
        late = max(0.0, (self._perf() - start_ns) / 1e6) > self.limits.max_cycle_ms
        # A late result is NOT a retroactively cancelled SQLite write.
        return self._report(
            status="late_after_commit" if late else "ok",
            intention=proposed,
            start_ns=start_ns, start_cpu_ns=start_cpu_ns,
            source_ms=source_ms, source_events=event_count,
            stored=stored, scored=len(consequences))

    def metrics(self) -> PassiveCycleMetrics:
        elapsed = tuple(e for e, _ in self._samples)
        cpu = tuple(c for _, c in self._samples)
        rhythm = self.brain.passive_rhythm_metrics()
        return PassiveCycleMetrics(
            cycles_attempted=self._attempted,
            source_events_accepted=self._accepted_events,
            stored_observations=self._stored,
            scored_consequences=self._scored,
            status_counts=tuple(sorted(self._status.items())),
            intention_counts=tuple(sorted(self._intents.items())),
            recent_samples=len(elapsed),
            p50_elapsed_ms=_p_nearest(elapsed, .50),
            p95_elapsed_ms=_p_nearest(elapsed, .95),
            max_elapsed_ms=max(elapsed) if elapsed else None,
            mean_process_cpu_ms=sum(cpu) / len(cpu) if cpu else None,
            observed_peak_rss_kib=_peak_rss_kib(),
            cooldown_blocks=rhythm.cooldown_blocks,
            consecutive_active_repeats=rhythm.consecutive_active_repeats,
            simulated_motivation_energy=rhythm.simulated_motivation_energy,
        )
