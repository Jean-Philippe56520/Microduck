"""F6-C: host-only complete offline cognition under synthetic burst pressure.

A fictional Unix socket feeds F1-B -> F2-B -> F1-C/F2-C through the EXISTING
F2-D supervisor with an optional F6-C admission policy. No daemon OEM,
network, Ollama, real camera, person, animal, sound, motor or robot is touched.
The measured CPU/elapsed/RSS are from the whole HOST process.
"""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import tempfile

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .offline_resource_budget import OfflineBudgetLimits, OfflineResourceGate
from .passive_demo import _fictional_unix_server, _frame, _item
from .passive_learning import PassiveLearning
from .passive_memory import PassiveObservationJournal
from .passive_resilience import PassiveCycleLimits, PassiveCycleSupervisor
from .passive_sources import FixtureUnixReader

FAKE_WALL = 1_780_000_000.0
SCHEDULE = (100.1, 100.2, 101.1, 102.1, 103.1, 104.2)
EXPECTED = (
    "ok", "budget_cycle_gap", "ok", "budget_window_events",
    "budget_window_cycles", "ok",
)


def run_demo() -> dict:
    memory = ExperienceMemory(":memory:")
    try:
        journal = PassiveObservationJournal(memory)
        learning = PassiveLearning(memory)
        brain = AutonomyBrain(memory)
        gate = OfflineResourceGate(OfflineBudgetLimits(
            window_s=4., min_cycle_gap_s=.5,
            max_window_cycles=3, max_window_events=2,
        ))
        # The third frame is rejected before cognition/memory. No buffered
        # replay is performed at the last tick: that uses the *fourth* frame.
        frames = (
            _frame(1, 100., _item("ball")),
            _frame(2, 101., _item("toy")),
            _frame(3, 102., _item("unknown")),
            _frame(4, 104., _item("bark", kind="sound_label")),
        )
        current = [SCHEDULE[0]]
        wall = [FAKE_WALL]
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory)/"f6c-fake-source.sock"
            with _fictional_unix_server(socket_path, frames):
                reader = FixtureUnixReader(
                    socket_path,timeout_s=.5,clock=lambda:current[0],
                )
                supervisor = PassiveCycleSupervisor(
                    reader=reader,brain=brain,
                    journal=journal,learning=learning,resource_gate=gate,
                    limits=PassiveCycleLimits(
                        max_cycles=8,max_events=8,
                        max_read_ms=500.,max_cycle_ms=1500.,
                    ),
                    monotonic_s=lambda:current[0],
                    wall_epoch_s=lambda:wall[0],
                )
                reports=[]
                for index,moment in enumerate(SCHEDULE):
                    current[0]=moment
                    wall[0]=FAKE_WALL+index
                    reports.append(supervisor.run_once())
                stats=supervisor.metrics()
                budget=gate.snapshot()
        statuses=tuple(r.status for r in reports)
        if statuses!=EXPECTED:
            raise RuntimeError(f"F6-C fixture unexpectedly changed: {statuses}")
        if (stats.cycles_attempted!=4 or stats.stored_observations!=3
                or stats.scored_consequences!=3
                or budget.admitted_events_in_window!=2
                or budget.admitted_cycles_in_window!=3
                or budget.pending_cycle):
            raise RuntimeError("the offline budget or SQLite failed")
        if (any(r.executed or r.motor_commands_issued for r in reports)
                or memory.experience_count()!=0):
            raise RuntimeError("F6-C cannot execute movement or fabricate outcomes")
        return {
            "kind":"full_f1_f2d_pipeline_on_fictional_unix_fixture",
            "synthetic_source_and_clocks":True,
            "statuses":statuses,
            "metrics":asdict(stats),
            "governor":asdict(budget),
            "pc_queries":0,
            "real_oem_socket_reads":0,
            "motor_commands_issued":0,
            "real_robot_validated":False,
        }
    finally:
        memory.close()


def main() -> int:
    print(json.dumps(run_demo(),sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
