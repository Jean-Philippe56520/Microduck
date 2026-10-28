"""SIM-E1: one OEM MuJoCo-only J2e trial and a read-only memory comparison.

This is NOT training of a neural model, proof of gait, robot actuation or a
causal effect on a physical object. Run only behind the explicit sim-only gate.
The *existing* J2e runner is the sole source of motor RPCs and stop handling.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import sys
import time

from .autonomy import AutonomyBrain, Scene
from .episodic_memory import ExperienceMemory
from .sim_bridge import read_simulator_telemetry
from .sim_flat_zone import GroundTruthError, flat_zone_snapshot, read_verified_flat_ground
from .sim_motion import SimMotionError
from .sim_walk_trial import WALK_SPEED_MPS, WALK_TICKS, WalkTrialResult, run_walk_trial

SOURCE = "mujoco_verified_pose"
OUTCOMES = frozenset({"translation_observed", "no_progress_observed",
                       "inconclusive_drift", "unverified"})


class SimE1Error(ValueError):
    """An active simulated experiment has no acceptable evidence."""


class _NoSimulatorPreference:
    """Counterfactual on the SAME scene, no SQL writer or second SQLite."""

    def intent_preference(self, environment: str, action: str) -> float:
        return 0.0

    def observe(self, *_args, **_kwargs):
        raise SimE1Error("object perception is outside the SIM-E1 flat-scene contract")


def compare_decisions(scene: Scene, memory: ExperienceMemory) -> dict:
    """Keep perception and default motivations identical between two decisions.

    There is no object in the pinned flat simulator. This comparison isolates
    a simulator-specific *preference*; it does not prove generalization.
    """
    if scene.environment != "simulator" or scene.object_id is not None or scene.person_visible:
        raise SimE1Error("SIM-E1 needs the object-free simulated scene")
    with_history = AutonomyBrain(memory).choose(scene).intention
    no_history = AutonomyBrain(_NoSimulatorPreference()).choose(scene).intention
    return {
        "same_scene": True,
        "with_simulated_memory": with_history,
        "counterfactual_without_sim_preference": no_history,
        "choice_changed": with_history != no_history,
        "counterfactual_motor_commands": 0,
        "counterfactual_memory_writes": 0,
    }


def validate_experience(result: WalkTrialResult, memory: ExperienceMemory,
                        decisions: dict) -> dict:
    """Verify J2e and its ONE persisted sim row, never infer robot causality."""
    if (type(result.commands_sent) is not int or result.commands_sent != WALK_TICKS
            or result.stop_confirmed is not True
            or result.memory_source != SOURCE
            or result.trials_in_memory != 1
            or result.outcome not in OUTCOMES
            or not math.isclose(result.requested_speed_mps, WALK_SPEED_MPS)
            or result.preference_before != 0):
        raise SimE1Error("J2e evidence or fresh-database contract violated")
    if (not isinstance(decisions, dict)
            or decisions.get("same_scene") is not True
            or decisions.get("counterfactual_motor_commands") != 0
            or decisions.get("counterfactual_memory_writes") != 0
            or decisions.get("choice_changed") is not (
                decisions.get("with_simulated_memory") !=
                decisions.get("counterfactual_without_sim_preference")
            )):
        raise SimE1Error("invalid counterfactual report")
    if any(x not in {"halt", "rest", "idle", "explore"}
           for x in (decisions.get("with_simulated_memory"),
                     decisions.get("counterfactual_without_sim_preference"))):
        raise SimE1Error("unexpected decision for object-free simulator")
    rows = memory.conn.execute(
        """SELECT source,action,measured_m,baseline_m,simulated_duration_s,
                  stop_confirmed,healthy_after,safe_after,outcome,reward
           FROM sim_motion_trials"""
    ).fetchall()
    if len(rows) != 1:
        raise SimE1Error("expected exactly one sourced simulator episode")
    row = rows[0]
    if (row["source"] != SOURCE or row["action"] != "explore"
            or row["stop_confirmed"] != 1
            or row["healthy_after"] != 1 or row["safe_after"] != 1
            or row["outcome"] != result.outcome
            or result.outcome == "unverified"
            or memory.experience_count() != 0):
        raise SimE1Error("missing verified simulator episode or contaminated action log")
    for key, reported in (
        ("measured_m", result.measured_displacement_m),
        ("baseline_m", result.baseline_displacement_m),
        ("simulated_duration_s", result.simulated_duration_s),
    ):
        if (type(reported) not in (int, float) or not math.isfinite(reported)
                or not math.isclose(row[key], reported, abs_tol=1e-8, rel_tol=1e-9)):
            raise SimE1Error("MuJoCo result does not match the journal")
    if row["reward"] != result.reward:
        raise SimE1Error("result / journal reward mismatch")
    preference = memory.intent_preference("simulator", "explore")
    if (not math.isclose(preference, result.preference_after, abs_tol=1e-9)
            or memory.intent_preference("robot", "explore") != 0):
        raise SimE1Error("simulated preference leaked or differs from journal")
    if (result.outcome == "inconclusive_drift" and
            (result.reward is not None or preference != 0)):
        raise SimE1Error("ambiguous movement must not teach a preference")
    if (result.outcome in {"translation_observed", "no_progress_observed"}
            and result.reward not in (0.5, -0.5)):
        raise SimE1Error("unexpected simulated preference signal")
    return {
        "schema_version": 1,
        "run_kind": "single_bounded_active_simulation",
        "source": "pinned_official_mujoco_only",
        "motor_authority": "official_robotd_only_via_existing_j2e",
        "trial": asdict(result),
        "decisions": decisions,
        "sqlite_sim_motion_rows": 1,
        "simulated_preference_only": preference,
        "robot_preference": 0.0,
        "motor_commands_from_counterfactual": 0,
        "gait_validated": False,
        "object_interaction_validated": False,
        "real_robot_validated": False,
        "causal_effect_on_object_proven": False,
        "neural_training_performed": False,
        "learning_kind": "bounded_simulator_preference_update_if_evidence_qualifies",
        "conclusion": ("same-choice-after-one-trial" if not decisions["choice_changed"]
                       else "simulated-choice-differed"),
    }


def run_e1(state_dir: Path, rl_root: Path, database: Path, *, port: int = 17801) -> dict:
    """At most ONE existing J2e action; no retries or second motor experiment."""
    if database.exists() or any(Path(str(database) + suffix).exists()
                                for suffix in ("-wal", "-shm")):
        raise SimE1Error("refuse an existing database: one new trial only")
    result = run_walk_trial(state_dir, rl_root, database, port=port)
    memory = ExperienceMemory(database)
    try:
        now = time.monotonic()
        telemetry = read_simulator_telemetry(state_dir, timeout_s=3.0, hz=2)
        ground = read_verified_flat_ground(state_dir, rl_root, port=port, timeout_s=.5)
        snapshot = flat_zone_snapshot(telemetry, ground, now=now)
        scene = snapshot.to_scene(now=now)
        decisions = compare_decisions(scene, memory)
        return validate_experience(result, memory, decisions)
    finally:
        memory.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SIM-E1 single bounded MuJoCo experience")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--rl-root", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=17801)
    parser.add_argument("--enable-once", action="store_true")
    args = parser.parse_args(argv)
    if (not args.enable_once or os.environ.get("MICRODUCK_SIM_E1") != "YES"):
        print("SIM-E1 disabled: requires --enable-once and MICRODUCK_SIM_E1=YES",
              file=sys.stderr)
        return 2
    if args.output.exists():
        print("SIM-E1 report already exists; no replay permitted", file=sys.stderr)
        return 2
    try:
        report = run_e1(args.state_dir, args.rl_root, args.database, port=args.port)
    except (SimE1Error, SimMotionError, GroundTruthError, OSError, ValueError) as exc:
        print(f"SIM-E1 refused or inconclusive: {exc}", file=sys.stderr)
        return 1
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "outcome": report["trial"]["outcome"],
        "choice_changed": report["decisions"]["choice_changed"],
        "source": report["source"], "gait_validated": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
