"""P2a deterministic mock replay, SQLite local; NO motor or internet calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .episodic_memory import ExperienceMemory
from .mock_cycles import MockCycleRunner, MockConsequence
from .perception import PerceptionEvent, PerceptionSnapshot


def mock_snapshot(t: float, *, target: str | None = None,
                  safe: bool = True) -> PerceptionSnapshot:
    def event(kind, value, track=None):
        return PerceptionEvent(
            kind, value, "mock", t, 1., 1., track_id=track)
    events = [
        event("safe_area", safe), event("floor_clear", safe),
        event("obstacle_m", 1.), event("battery_pct", 85.),
    ]
    if target:
        events.append(event("object_label", "toy", target))
    return PerceptionSnapshot("mock", tuple(events), t)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mock cognitive cycles, not robot control")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--session", default="fixture-session")
    args = parser.parse_args(argv)
    memory = ExperienceMemory(args.database)
    try:
        runner = MockCycleRunner(memory, session=args.session)
        t = float(runner.sequence * 10 + 100)
        records = [runner.step(mock_snapshot(t), now=t+.1)]
        records.append(runner.step(
            mock_snapshot(t+2., target="fictive-toy"), now=t+2.5,
            followup=mock_snapshot(t+2.4, target="fictive-toy"),
            consequence=MockConsequence("fictive-toy", "positive", t+2.3),
        ))
        records.append(runner.step(
            mock_snapshot(t+4., safe=False), now=t+4.1))
        records.append(runner.step(
            mock_snapshot(t+6., target="fictive-toy"), now=t+6.1))
        print(json.dumps({
            "source": "mock_only",
            "session": args.session,
            "cycles": [
                {"sequence": x.sequence, "intention": x.plan.intention,
                 "disposition": x.disposition, "outcome": x.outcome,
                 "reward": x.reward} for x in records
            ],
            "journal_count": len(runner.history()),
            "learned_fictive_toy_preference":
                memory.get("fictive-toy").preference,
            "motor_commands_issued": 0,
            "hardware_validated": False,
        }, indent=2, sort_keys=True))
    finally:
        memory.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
