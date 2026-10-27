"""EX4-A: read-only provenance audit of existing consequences.

No adapter in this repository authenticates a physical robotd execution
receipt. Therefore no legacy record, EX1 mock resolution, EX2 temporal cue,
P2a mock reward, MuJoCo pose trial or X2 passive telemetry can authorize
physical causal learning. This module reads only ExperienceMemory.conn.
It creates no table, reward, motor command, model or second writer.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re

from .episodic_memory import ExperienceMemory
from .experience_ledger import _key, _epoch, MAX_RESOLUTION_DELAY_S
from .experience_effects import MockCue, MockEffectPair, _assess


_SIM_SESSION = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


@dataclass(frozen=True)
class EvidenceVerdict:
    """Four distinct evidence stages, NOT an execution authorization.

    Status describes only the record's existing provenance. The physical
    fields deliberately remain false until an OEM adapter with independently
    verifiable robot receipts is implemented and tested on the robot.
    """

    family: str
    key: str
    status: str
    proposed: str
    authorized: str
    executed: str
    observed: str
    effect: str
    source: str
    corrected: bool = False
    verified_on_robot: bool = False
    causality_established: bool = False
    physical_learning_allowed: bool = False


def _verdict(
    family: str, key: str, status: str, *,
    proposed: str = "unverified",
    executed: str = "not_attested",
    observed: str = "not_attested",
    effect: str = "unknown",
    source: str = "unverified",
    corrected: bool = False,
) -> EvidenceVerdict:
    return EvidenceVerdict(
        family=family, key=key, status=status,
        proposed=proposed, authorized="not_attested",
        executed=executed, observed=observed, effect=effect,
        source=source, corrected=corrected,
    )


def _sim_key(session: object, sequence: object) -> str:
    if type(session) is not str or _SIM_SESSION.fullmatch(session) is None:
        raise ValueError("session must be an opaque ASCII session key")
    if type(sequence) is not int or not 1 <= sequence <= 2_147_483_647:
        raise ValueError("invalid simulation sequence")
    return session + ":" + str(sequence)


def _id(identifier: object) -> int:
    if type(identifier) is not int or not 1 <= identifier <= 2_147_483_647:
        raise ValueError("invalid positive record ID")
    return identifier


def _numeric(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("invalid numeric evidence")
    return float(value)


class ExecutionEvidenceAudit:
    """EX4-A safety gate over one pre-existing ExperienceMemory.

    All methods perform SELECTs only. They do not initialize producer
    modules (which could create tables), update a score, or accept a caller's
    claim of a robotd acknowledgement. Existing correction flags are reread
    on every query, so withdrawal works across process restarts.
    """

    def __init__(self, memory: ExperienceMemory) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("reuse the existing ExperienceMemory")
        self._memory = memory

    def _exists(self, name: str) -> bool:
        return self._memory.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone() is not None

    def review_ex1(self, *, session: str, sequence: int) -> EvidenceVerdict:
        """EX1/EX2: even a changed post-cue proves time ordering, not cause."""
        _key(session, sequence)
        key = session + ":" + str(sequence)
        family = "ex1_ex2_mock"
        if not self._exists("ex1_mock_experiences"):
            return _verdict(family, key, "missing")
        p = self._memory.conn.execute("""
            SELECT id,intention,target_kind,target_category,source,active,
                   status,proposed_at_epoch_s,resolved_at_epoch_s
            FROM ex1_mock_experiences WHERE session=? AND sequence=?
        """, (session, sequence)).fetchone()
        if p is None:
            return _verdict(family, key, "missing")
        if p["active"] == 0:
            return _verdict(
                family, key, "withdrawn", proposed="mock_fixture",
                source="mock_fixture_only", corrected=True,
            )
        if p["active"] != 1 or p["source"] != "mock_fixture_only":
            return _verdict(family, key, "invalid_provenance")
        try:
            start = _epoch(p["proposed_at_epoch_s"])
            end = p["resolved_at_epoch_s"]
            if p["status"] == "proposed":
                if end is not None:
                    raise ValueError("proposal has a resolution timestamp")
            elif p["status"] in {"mock_executed", "refused", "interrupted"}:
                end = _epoch(end)
                if not start <= end <= start + MAX_RESOLUTION_DELAY_S:
                    raise ValueError("resolution chronology invalid")
            else:
                raise ValueError("unsupported EX1 status")
        except (TypeError, ValueError):
            return _verdict(family, key, "invalid_provenance")
        e = None
        if self._exists("ex2_mock_effects"):
            e = self._memory.conn.execute(
                "SELECT * FROM ex2_mock_effects WHERE ex1_id=?",
                (p["id"],),
            ).fetchone()
        if p["status"] != "mock_executed":
            if e is not None and e["active"] == 1:
                return _verdict(family, key, "invalid_provenance")
            return _verdict(
                family, key, p["status"], proposed="mock_fixture",
                source="mock_fixture_only",
            )
        if e is None:
            return _verdict(
                family, key, "mock_resolution_only", proposed="mock_fixture",
                executed="scripted_mock_only", source="mock_fixture_only",
            )
        if e["active"] == 0:
            return _verdict(
                family, key, "withdrawn_effect", proposed="mock_fixture",
                executed="scripted_mock_only", source="mock_fixture_only",
                corrected=True,
            )
        if (e["active"] != 1 or e["source"] != "mock_fixture_only"
                or e["same_scene"] not in (0, 1)
                or e["competing_event"] not in (0, 1)):
            return _verdict(family, key, "invalid_provenance")
        try:
            before = MockCue(
                e["cue_kind"], e["before_value"],
                e["before_epoch_s"], e["before_confidence"],
            )
            after = MockCue(
                e["cue_kind"], e["after_value"],
                e["after_epoch_s"], e["after_confidence"],
            )
            pair = MockEffectPair(
                session, sequence, before, after,
                bool(e["same_scene"]), bool(e["competing_event"]),
            )
            if ((p["target_kind"] == "sound_label") !=
                    (pair.before.kind == "sound")):
                raise ValueError("mismatched modalities")
            if not (start - 2 <= before.observed_at_epoch_s
                    <= start < end <= after.observed_at_epoch_s <= end + 2):
                raise ValueError("EX2 cue outside EX1 lifecycle")
            expected = _assess(
                pair, unknown_target=p["target_category"] == "unknown",
            )
            if tuple(e[k] for k in (
                "effect_status", "association_status", "reason_code",
            )) != expected:
                raise ValueError("EX2 annotations contradict the cues")
        except (TypeError, ValueError):
            return _verdict(family, key, "invalid_provenance")
        association = e["association_status"]
        status = {
            "temporal_only": "mock_temporal_only",
            "confounded": "mock_confounded",
            "none": "mock_unchanged",
            "indeterminate": "mock_indeterminate",
        }[association]
        return _verdict(
            family, key, status, proposed="mock_fixture",
            executed="scripted_mock_only", observed="synthetic_cue",
            effect=e["effect_status"], source="mock_fixture_only",
        )

    def review_p2a(self, *, session: str, sequence: int) -> EvidenceVerdict:
        """P2a's mock feedback cannot be imported as physical reward."""
        key = _sim_key(session, sequence)
        family = "p2a_mock"
        if not self._exists("mock_cognitive_cycles"):
            return _verdict(family, key, "missing")
        r = self._memory.conn.execute("""
            SELECT intention,disposition,outcome,reward,source
            FROM mock_cognitive_cycles WHERE session=? AND sequence=?
        """, (session, sequence)).fetchone()
        if r is None:
            return _verdict(family, key, "missing")
        if r["source"] != "mock":
            return _verdict(family, key, "invalid_provenance")
        expected = {
            "explicit_mock_positive": .4,
            "explicit_mock_negative": -.4,
        }
        reward = r["reward"]
        if r["disposition"] == "mock_feedback":
            if (r["intention"] != "inspect_object"
                    or r["outcome"] not in expected
                    or reward is None
                    or not math.isfinite(float(reward))
                    or abs(float(reward) - expected[r["outcome"]]) > 1e-12):
                return _verdict(family, key, "invalid_provenance")
            return _verdict(
                family, key, "mock_feedback_only",
                proposed="mock_fixture", executed="scripted_mock_only",
                observed="synthetic_followup", effect=r["outcome"],
                source="mock",
            )
        safe = (
            ("blocked_motion", "no_motor_command_issued"),
            ("unverified", "no_mock_consequence_provided"),
            ("observation_only", "no_actuation_or_causal_claim"),
        )
        if (r["disposition"], r["outcome"]) not in safe or reward is not None:
            return _verdict(family, key, "invalid_provenance")
        return _verdict(
            family, key, "no_verified_execution",
            proposed="mock_fixture", source="mock",
        )

    def review_sim_motion(self, *, trial_id: int) -> EvidenceVerdict:
        """A MuJoCo pose and simulated reward are never a robotd receipt."""
        trial_id = _id(trial_id)
        key = str(trial_id)
        family = "mujoco_pose"
        if not self._exists("sim_motion_trials"):
            return _verdict(family, key, "missing")
        r = self._memory.conn.execute(
            "SELECT * FROM sim_motion_trials WHERE id=?", (trial_id,),
        ).fetchone()
        if r is None:
            return _verdict(family, key, "missing")
        if r["source"] != "mujoco_verified_pose" or r["action"] != "explore":
            return _verdict(family, key, "invalid_provenance")
        try:
            measured = _numeric(r["measured_m"])
            baseline = _numeric(r["baseline_m"])
            duration = _numeric(r["simulated_duration_s"])
            if min(measured, baseline) < 0 or not 0 < duration <= 10:
                raise ValueError("invalid simulated measurements")
            flags = (r["stop_confirmed"], r["healthy_after"], r["safe_after"])
            if any(x not in (0, 1) for x in flags):
                raise ValueError("invalid binary attestations")
            if not all(flags):
                outcome, reward = "unverified", None
            elif baseline > .005:
                outcome, reward = "inconclusive_drift", None
            elif measured >= max(.01, 3 * baseline + .005):
                outcome, reward = "translation_observed", .5
            else:
                outcome, reward = "no_progress_observed", -.5
            if (r["outcome"] != outcome
                    or (reward is None and r["reward"] is not None)
                    or (reward is not None and (
                        r["reward"] is None or _numeric(r["reward"]) != reward
                    ))):
                raise ValueError("inconsistent simulated outcome")
        except (ValueError, TypeError):
            return _verdict(family, key, "invalid_provenance")
        return _verdict(
            family, key,
            "simulated_effect_only" if reward is not None
            else "simulated_inconclusive",
            proposed="unverified", executed="simulator_only",
            observed="simulated_pose", effect=outcome,
            source="mujoco_verified_pose",
        )

    def review_sim_passive(
        self, *, session: str, sequence: int,
    ) -> EvidenceVerdict:
        """X2/P2b coherent telemetry does NOT show an action executed."""
        key = _sim_key(session, sequence)
        family = "x2_sim_passive"
        if not self._exists("sim_passive_cycles"):
            return _verdict(family, key, "missing")
        r = self._memory.conn.execute("""
            SELECT source,quality,outcome,reward,motor_commands,
                   intention,observed_at
            FROM sim_passive_cycles WHERE session=? AND sequence=?
        """, (session, sequence)).fetchone()
        if r is None:
            return _verdict(family, key, "missing")
        try:
            _epoch(r["observed_at"])
        except (ValueError, TypeError):
            return _verdict(family, key, "invalid_provenance")
        if (r["source"] != "simulator_ipc"
                or r["quality"] not in (
                    "coherent", "invalid_or_missing", "nonadvancing_frame"
                )
                or r["outcome"] != "no_action_executed"
                or r["reward"] is not None or r["motor_commands"] != 0):
            return _verdict(family, key, "invalid_provenance")
        return _verdict(
            family, key, "no_action_executed",
            proposed="simulated_proposal", observed="simulated_telemetry",
            source="simulator_ipc",
        )

    def review_legacy_action(self, *, action_id: int) -> EvidenceVerdict:
        """Legacy experiences lacks source/receipt: never elevate its outcome."""
        action_id = _id(action_id)
        key = str(action_id)
        family = "legacy_experiences"
        if not self._exists("experiences"):
            return _verdict(family, key, "missing")
        exists = self._memory.conn.execute(
            "SELECT 1 FROM experiences WHERE id=?", (action_id,),
        ).fetchone()
        if exists is None:
            return _verdict(family, key, "missing")
        return _verdict(family, key, "legacy_unverifiable")
