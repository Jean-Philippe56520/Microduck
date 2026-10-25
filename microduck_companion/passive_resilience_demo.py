"""F2-D: repeatable host benchmark over TWO separate MOCK Unix sessions.

Synthetic clock values describe fixture chronology; wall/CPU/RSS timings come
from the actual CI runner process. No real sensor, robot action or AI model.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import tempfile

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .passive_demo import _fictional_unix_server, _frame, _item
from .passive_learning import PassiveLearning
from .passive_memory import PassiveObservationJournal
from .passive_resilience import PassiveCycleLimits, PassiveCycleSupervisor
from .passive_sources import FixtureUnixReader

WALL_BASE = 1_770_000_000.0
_SESSIONS = frozenset({"first", "second"})


def _scenario(session: str) -> tuple[tuple[float, bytes], ...]:
    if session == "first":
        return (
            (100.1, _frame(1, 100., _item("ball"))),
            (101.1, _frame(2, 101., _item("ball"))),
            (102.1, b""),  # one failed Unix fixture: no journal/reward
            (103.1, _frame(4, 103., _item("toy"))),
            (104.1, _frame(5, 104., _item("unknown"))),
            (105.1, _frame(6, 105., _item("knock", kind="sound_label"))),
        )
    if session == "second":
        # New process, new journal session and reset monotonic origin.
        return (
            (10.1, _frame(1, 10., _item("ball"))),
            (11.1, _frame(2, 11., _item("meow", kind="sound_label"))),
            (12.1, b""),  # network loss must never replay the old sound
            (13.1, _frame(4, 13., _item("dog"))),
        )
    raise ValueError("session must be first or second")


def run_session(database: str | Path, *, session: str) -> dict:
    """Independent invocations must share only their SQLite, not fake clocks."""
    if session not in _SESSIONS:
        raise ValueError("session must be first or second")
    memory = ExperienceMemory(database)
    try:
        journal = PassiveObservationJournal(memory)
        learning = PassiveLearning(memory)
        prior = journal.recent(now_wall_epoch_s=WALL_BASE + 30)
        if session == "first" and prior:
            raise RuntimeError("first session requires a fresh SQLite")
        if session == "second":
            if (len(prior) != 5
                    or learning.preference("observe") < 0.03
                    or learning.preference("listen") != 0.02):
                raise RuntimeError("second session needs verified first stage")
        brain = AutonomyBrain(memory)
        moments = _scenario(session)
        logical = [moments[0][0]]
        wall = [WALL_BASE]
        reports = []
        with tempfile.TemporaryDirectory() as folder:
            socket_path = Path(folder) / "mock-source.sock"
            with _fictional_unix_server(socket_path,
                                        tuple(data for _, data in moments)):
                reader = FixtureUnixReader(
                    socket_path, timeout_s=0.5, clock=lambda: logical[0],
                )
                supervisor = PassiveCycleSupervisor(
                    reader=reader, brain=brain, journal=journal,
                    learning=learning,
                    limits=PassiveCycleLimits(
                        max_cycles=len(moments), max_events=12,
                        max_read_ms=500., max_cycle_ms=1500.,
                    ),
                    monotonic_s=lambda: logical[0],
                    wall_epoch_s=lambda: wall[0],
                )
                for i, (moment, _) in enumerate(moments):
                    logical[0] = moment
                    wall[0] = WALL_BASE + i + (0 if session == "first" else 10)
                    reports.append(supervisor.run_once())
                stats = supervisor.metrics()
        if any(x.executed or x.motor_commands_issued for x in reports):
            raise RuntimeError("fixture supervisor cannot operate motors")
        if [x.status for x in reports].count("source_unavailable") != 1:
            raise RuntimeError("expected exactly one source outage")
        if stats.stored_observations != (5 if session == "first" else 3):
            raise RuntimeError("unexpected F1-C rows after interruption")
        if stats.scored_consequences != stats.stored_observations:
            raise RuntimeError("unexpected F2-C consequences")
        result = {
            "session": session,
            "environment": "host_python_fixture_unix",
            "synthetic_clock": True,
            "source_outages": 1,
            "proposals": [r.intention for r in reports],
            "statuses": [r.status for r in reports],
            "metrics": asdict(stats),
            "bias_observe": learning.preference("observe"),
            "bias_listen": learning.preference("listen"),
            "executed_actions": 0,
            "motor_commands": 0,
        }
        return result
    finally:
        memory.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--session", required=True, choices=sorted(_SESSIONS))
    args = parser.parse_args()
    print(json.dumps(run_session(args.database, session=args.session),
                     allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
