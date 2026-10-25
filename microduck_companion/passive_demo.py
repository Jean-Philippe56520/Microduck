"""F1-D: complete *fictional* passive pipeline, independently restartable.

F1-B Unix fixture -> F1-A conservative projection -> F1-C existing SQLite
-> existing AutonomyBrain, which must select 'halt' with no safety sensors.

A tiny local server provides canned categories; it is NOT mediad, a camera,
microphone, MuJoCo perception, object recognition or a motor adapter.
Two CLI invocations with --session first / second share one SQLite database.
The resulting JSON contains only artificial category names, never track IDs,
raw media, personal identities, motor commands, or model hypotheses.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import math
from pathlib import Path
import socket
import sys
import tempfile
import threading
from typing import Iterator

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .passive_memory import PassiveObservationJournal
from .passive_observations import summarize_passive
from .passive_sources import FixtureUnixReader, PassiveRead
from .perception import PerceptionSnapshot

_SESSION_NAMES = frozenset({"first", "second"})


def _item(label: str, *, kind: str = "object_label",
          confidence: float = 0.96) -> dict:
    item: dict = {
        "kind": kind, "category": label,
        "confidence": confidence, "ttl_s": 1.0,
    }
    if kind == "object_label":
        # Ephemeral *fixture* IDs are never exported or persisted.
        item["track_id"] = "track-fictional"
    return item


def _frame(seq: int, mono: float, *items: dict) -> bytes:
    return (json.dumps({
        "schema_version": 1,
        "sequence": seq,
        "sample_monotonic_s": mono,
        "events": items,
    }, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _scenario(session: str) -> tuple[tuple[float, bytes], ...]:
    if session == "first":
        return (
            (100.1, _frame(1, 100., _item("ball"))),
            (101.1, _frame(2, 101., _item("ball"))),
            (102.1, _frame(3, 102., _item("ball"), _item("toy"))),
            (103.1, _frame(4, 103., _item("unknown"))),
            (104.1, b""),  # Explicit fixture disconnection, not a sensor fact.
            (105.1, _frame(6, 105., _item("knock", kind="sound_label"))),
        )
    if session == "second":
        # Monotonic origin starts over. It MUST NOT reuse the first session
        # clock or treat the old journal as a fresh frame.
        return (
            (10.1, _frame(1, 10., _item("ball"))),
            (11.1, _frame(2, 11., _item("dog"))),
            (12.1, b""),  # No reuse of the previous successful dog frame.
            (13.1, _frame(4, 13., _item("ball"))),
        )
    raise ValueError("session must be first or second")


@contextmanager
def _fictional_unix_server(path: Path, replies: tuple[bytes, ...]
                          ) -> Iterator[None]:
    """Answer each connection once with canned data; no network access."""
    if not hasattr(socket, "AF_UNIX"):
        raise RuntimeError("F1-D integrated demo requires Unix sockets")
    errors: list[Exception] = []
    stop = threading.Event()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        listener.listen(1)
        listener.settimeout(0.2)

        def serve() -> None:
            try:
                for response in replies:
                    while not stop.is_set():
                        try:
                            conn, _ = listener.accept()
                        except socket.timeout:
                            continue
                        except OSError:
                            return
                        with conn:
                            if response:
                                conn.sendall(response)
                        break
            except OSError as exc:
                errors.append(exc)

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        try:
            yield
        finally:
            stop.set()
            worker.join(timeout=2.)
            if worker.is_alive():
                raise RuntimeError("fictional IPC server did not stop")
            if errors:
                raise RuntimeError("fictional IPC server failed") from errors[0]


def _passive_cycle(reading: PassiveRead, *, memory: ExperienceMemory,
                   journal: PassiveObservationJournal, brain: AutonomyBrain,
                   now_mono: float, now_wall: float) -> dict:
    """Only a new, validated source frame may create an observation.

    Journals are historical. They can inform category familiarity, but NEVER
    become current motor safety measurements, individual recognition or an
    executed motor action. Even a failed source ends with an explicit halt.
    """
    if not isinstance(reading, PassiveRead):
        raise TypeError("F1-D expects the F1-B PassiveRead")
    if type(now_mono) not in (int, float) or not math.isfinite(now_mono):
        raise ValueError("invalid monotonic clock")
    if type(now_wall) not in (int, float) or not math.isfinite(now_wall):
        raise ValueError("invalid wall clock")

    observations = ()
    previous_counts: list[int] = []
    if reading.status == "ok":
        observations = summarize_passive(reading.snapshot, now=now_mono)
        previous_counts = [
            journal.category_count(obs.kind, obs.category,
                                   now_wall_epoch_s=now_wall)
            if obs.usable_category else 0
            for obs in observations
        ]

    added = journal.append(
        reading, now_monotonic_s=now_mono, now_wall_epoch_s=now_wall)

    # F1-B only provides object/sound categories, no floor, zone, ToF, or
    # battery clearance. With no safety facts the existing brain MUST halt.
    # Failed reads are NEVER allowed to carry a previous or forged snapshot.
    safe_snapshot = (reading.snapshot if reading.status == "ok"
                     else PerceptionSnapshot("mock", (), now_mono))
    plan = brain.choose_from_snapshot(safe_snapshot, now=now_mono)
    if plan.intention != "halt":
        raise RuntimeError("passive-only data must never authorize an action")

    seen = []
    if reading.status == "ok" and added == len(observations):
        for obs, old in zip(observations, previous_counts):
            seen.append({
                "kind": obs.kind,
                "category": obs.category,
                "status": obs.status,
                "source": obs.claimed_source,
                "familiarity": (
                    "new_category" if old == 0 else "previously_seen_category"
                ) if obs.usable_category else "unresolved",
            })
    return {
        "source_status": reading.status,
        "stored_rows": added,
        "observations": seen,
        "intention": plan.intention,
        "disposition": "no_motor_execution",
        "motor_commands": 0,
    }


def run_session(database: str | Path, *, session: str) -> dict:
    """Run a canned *local* six/four-step session against shared SQLite.

    Running first and second in separate OS processes is required to prove
    cross-process memory survival. The second session refuses to invent a
    successful prior run if it cannot find the archived first-session 'ball'.
    """
    if session not in _SESSION_NAMES:
        raise ValueError("session must be first or second")
    scenario = _scenario(session)
    memory = ExperienceMemory(database)
    try:
        journal = PassiveObservationJournal(memory)
        # Fail BEFORE any new events if the caller skipped/repeated a stage.
        # The two CLI sessions are not interchangeable and must use the same
        # historical SQLite file, not two identical sets of fake observations.
        prior = journal.recent(now_wall_epoch_s=1_770_000_020., limit=20)
        if session == "first" and prior:
            raise RuntimeError("first session requires empty passive history")
        if session == "second":
            expected_pairs = [
                ("ball", "identified"), ("ball", "identified"),
                ("unknown", "conflict"), ("unknown", "unknown"),
                ("knock", "identified"),
            ]
            if (len(prior) != 5
                    or [(x.category, x.status) for x in reversed(prior)]
                       != expected_pairs
                    or journal.category_count(
                        "object_label", "ball",
                        now_wall_epoch_s=1_770_000_020.) != 2):
                raise RuntimeError("second session requires completed first history")
        brain = AutonomyBrain(memory)
        with tempfile.TemporaryDirectory(prefix="microduck-f1d-") as folder:
            path = Path(folder) / "mock.sock"
            clock = [scenario[0][0]]
            with _fictional_unix_server(path, tuple(r for _, r in scenario)):
                reader = FixtureUnixReader(
                    path, timeout_s=.5, max_age_s=1., min_interval_s=.5,
                    clock=lambda: clock[0],
                )
                records = []
                base = 1_770_000_000.
                for index, (now, _) in enumerate(scenario):
                    clock[0] = now
                    result = reader.read()
                    records.append(_passive_cycle(
                        result, memory=memory, journal=journal, brain=brain,
                        now_mono=now, now_wall=base + (
                            index if session == "first" else 20 + index),
                    ))
        latest_wall = base + (20 if session == "second" else 0) + len(scenario)
        history = journal.recent(now_wall_epoch_s=latest_wall, limit=20)
        return {
            "scenario": "fictional_f1d_unix_fixture_only",
            "session": session,
            "cycles": records,
            "cycles_count": len(records),
            "session_id": journal.session_id,
            "historical_categories": len(history),
            "ball_category_count": journal.category_count(
                "object_label", "ball", now_wall_epoch_s=latest_wall),
            "source": "mock_only",
            "no_raw_media": True,
            "no_identity_recognition": True,
            "historical_is_not_live_perception": True,
            "motor_commands_issued": 0,
            "physical_robot_validated": False,
            "oem_sensor_connected": False,
            "phase_f1_d_demo_passed": False,  # Set after assertions below.
        }
    finally:
        memory.close()


def _check_expected(report: dict) -> None:
    c = report["cycles"]
    if report["session"] == "first":
        expected = [
            ("ok", "new_category", "ball", "identified", 1),
            ("ok", "previously_seen_category", "ball", "identified", 1),
            ("ok", "unresolved", "unknown", "conflict", 1),
            ("ok", "unresolved", "unknown", "unknown", 1),
            ("unavailable_or_invalid", None, None, None, 0),
            ("ok", "new_category", "knock", "identified", 1),
        ]
        expected_ball, expected_history = 2, 5
    else:
        expected = [
            ("ok", "previously_seen_category", "ball", "identified", 1),
            ("ok", "new_category", "dog", "identified", 1),
            ("unavailable_or_invalid", None, None, None, 0),
            ("ok", "previously_seen_category", "ball", "identified", 1),
        ]
        expected_ball, expected_history = 4, 8
    if report["ball_category_count"] != expected_ball:
        raise RuntimeError("F1-D historical category counts contradict scenario")
    if report["historical_categories"] != expected_history:
        raise RuntimeError("F1-D persisted historical rows mismatch")
    if len(c) != len(expected):
        raise RuntimeError("F1-D incomplete observation session")
    for actual, (status, novelty, category, label_status, stored) in zip(c, expected):
        if (actual["source_status"] != status
                or actual["stored_rows"] != stored
                or actual["intention"] != "halt"
                or actual["motor_commands"] != 0):
            raise RuntimeError("F1-D source/safety/record mismatch")
        observations = actual["observations"]
        if novelty is None:
            if observations:
                raise RuntimeError("F1-D reused stale category after source loss")
        elif (len(observations) != 1 or
              observations[0]["familiarity"] != novelty or
              observations[0]["category"] != category or
              observations[0]["status"] != label_status or
              observations[0]["source"] != "mock"):
            raise RuntimeError("F1-D observation novelty/provenance mismatch")
    if any(report[k] is not v for k, v in {
        "no_raw_media": True, "no_identity_recognition": True,
        "historical_is_not_live_perception": True,
        "physical_robot_validated": False, "oem_sensor_connected": False,
    }.items()):
        raise RuntimeError("F1-D failed safety/provenance attestation")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="F1-D two-session fictional passive demo (no motor/mediad)")
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--session", choices=sorted(_SESSION_NAMES), required=True)
    args = p.parse_args(argv)
    try:
        result = run_session(args.database, session=args.session)
        _check_expected(result)
        result["phase_f1_d_demo_passed"] = True
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"F1-D failed closed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
