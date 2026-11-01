"""P15-B1: finite host-only lifecycle for an external MOCK Unix fixture.

Reuses F2-D, F1-C and the existing single ExperienceMemory writer. No OEM
connections, camera capture, motor calls, service autoactivation, or PC model.
This is NOT a deployable companion daemon, robot observation or safety check.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import signal
import sqlite3
import sys
import threading

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .passive_learning import PassiveLearning
from .passive_memory import PassiveObservationJournal
from .passive_resilience import PassiveCycleLimits, PassiveCycleSupervisor
from .passive_sources import FixtureUnixReader

MAX_HOST_CYCLES = 16
MIN_INTERVAL_S = 0.5
MAX_INTERVAL_S = 2.0
FORBIDDEN_SOURCE_ROOTS = (Path("/run"), Path("/dev"), Path("/proc"), Path("/sys"))


def validate_fixture_args(socket_path: Path, database: Path, *,
                          cycles: int, interval_s: float) -> None:
    """Refuse OEM/virtual-system sockets before opening any SQLite database."""
    if not isinstance(socket_path, Path) or not socket_path.is_absolute():
        raise ValueError("mock Unix socket path must be absolute")
    resolved = socket_path.resolve(strict=False)
    if socket_path.is_symlink() or any(
        resolved == root or root in resolved.parents for root in FORBIDDEN_SOURCE_ROOTS
    ):
        raise ValueError("OEM and kernel socket locations are not mock fixtures")
    if not isinstance(database, Path) or not database.is_absolute():
        raise ValueError("SQLite path must be absolute")
    if database.resolve(strict=False) == resolved:
        raise ValueError("socket and SQLite cannot share a path")
    if type(cycles) is not int or not 1 <= cycles <= MAX_HOST_CYCLES:
        raise ValueError("host cycles must be between 1 and 16")
    if (type(interval_s) not in (float, int) or not math.isfinite(interval_s)
            or not MIN_INTERVAL_S <= interval_s <= MAX_INTERVAL_S):
        raise ValueError("interval must be between 0.5 and 2 seconds")


def run_fixture_lifecycle(socket_path: Path, database: Path, *,
                          cycles: int = 4, interval_s: float = 0.6,
                          stop_event: threading.Event | None = None) -> dict:
    """Finite, cooperative mock cycle; no live OEM source or physical effect.

    F2-D's wall/cycle deadlines are soft, and SIGTERM is cooperative: neither
    can interrupt a blocked SQLite operation or an in-flight fixture read.
    """
    validate_fixture_args(socket_path, database, cycles=cycles, interval_s=interval_s)
    if stop_event is not None and not isinstance(stop_event, threading.Event):
        raise TypeError("stop_event must be a threading.Event")
    stop = stop_event if stop_event is not None else threading.Event()
    if stop.is_set():
        return _result(0, 0, 0, 0, {}, True, memory_opened=False)

    memory = ExperienceMemory(database)
    try:
        journal = PassiveObservationJournal(memory)
        learning = PassiveLearning(memory)
        brain = AutonomyBrain(memory)
        runner = PassiveCycleSupervisor(
            reader=FixtureUnixReader(
                socket_path, timeout_s=0.4, max_age_s=1.0,
                min_interval_s=MIN_INTERVAL_S,
            ),
            brain=brain, journal=journal, learning=learning,
            limits=PassiveCycleLimits(
                max_cycles=cycles, max_events=128,
                max_read_ms=500, max_cycle_ms=1500,
            ),
        )
        for index in range(cycles):
            if stop.is_set():
                break
            report = runner.run_once()
            if report.executed or report.motor_commands_issued:
                raise RuntimeError("fixture cycle must never execute actions")
            if index + 1 < cycles and stop.wait(interval_s):
                break
        metrics = runner.metrics()
        return _result(
            metrics.cycles_attempted, metrics.stored_observations,
            metrics.scored_consequences, metrics.source_events_accepted,
            dict(metrics.status_counts), stop.is_set(), memory_opened=True,
        )
    finally:
        memory.close()


def _result(cycles: int, stored: int, scored: int, events: int,
            statuses: dict[str, int], stopped: bool, *, memory_opened: bool) -> dict:
    return {
        "status": "fixture_stop_requested" if stopped else "fixture_cycles_finished",
        "source": "untrusted_mock_fixture_unix_only",
        "cycles_attempted": cycles,
        "observations_stored": stored,
        "consequences_scored": scored,
        "events_accepted": events,
        "cycle_statuses": statuses,
        "stop_requested": stopped,
        "motor_commands_issued": 0,
        "camera_frames_captured": 0,
        "oem_sensor_validated": False,
        "robot_validated": False,
        "action_executed": False,
        "experience_memory_instances": 1 if memory_opened else 0,  # never a second SQLite
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock-only", action="store_true", required=True)
    parser.add_argument("--fixture-unix-socket", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--interval-s", type=float, default=0.6)
    args = parser.parse_args(argv)
    stop = threading.Event()
    old_handlers = {}

    def request_stop(_signal_number, _frame):
        stop.set()

    try:
        for code in (signal.SIGTERM, signal.SIGINT):
            old_handlers[code] = signal.signal(code, request_stop)
        result = run_fixture_lifecycle(
            args.fixture_unix_socket, args.database,
            cycles=args.cycles, interval_s=args.interval_s, stop_event=stop,
        )
    except (OSError, ValueError, TypeError, sqlite3.Error, RuntimeError) as exc:
        # No frame, memory, socket path, or exception text is logged.
        print("P15B_STOP: " + type(exc).__name__, file=sys.stderr)
        return 2
    finally:
        for code, original in old_handlers.items():
            signal.signal(code, original)
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
