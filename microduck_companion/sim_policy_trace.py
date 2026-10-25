"""Read-only diagnostics for the official robot.state motion/policy stream.

This validates *what robotd reported applying*, not whether the body actually
walked. Joint contact and correct gait still require independent validation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .sim_ipc import Notification, TelemetryError


@dataclass(frozen=True)
class PolicySample:
    policy: str
    requested: tuple[float, float, float]
    applied: tuple[float, float, float]
    limited_by: tuple[str, ...]
    received_at: float


def _triple(value: object, name: str) -> tuple[float, float, float]:
    if (not isinstance(value, list) or len(value) != 3 or
        any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise TelemetryError(f"invalid robot.state.move.{name}")
    return (float(value[0]), float(value[1]), float(value[2]))


def parse_policy_sample(note: Notification) -> PolicySample:
    if note.method != "robot.state":
        raise TelemetryError("not a robot.state notification")
    state = note.params
    policy, movement = state.get("policy"), state.get("move")
    if not isinstance(policy, str) or not policy.strip():
        raise TelemetryError("missing policy network label")
    if not isinstance(movement, dict):
        raise TelemetryError("missing robot.state.move diagnostics")
    limited = movement.get("limited_by", [])
    if not isinstance(limited, list) or any(not isinstance(v, str) for v in limited):
        raise TelemetryError("invalid motion limitations")
    return PolicySample(
        policy=policy,
        requested=_triple(movement.get("requested"), "requested"),
        applied=_triple(movement.get("applied"), "applied"),
        limited_by=tuple(limited),
        received_at=note.received_at,
    )


def summarize_policy_samples(samples: list[PolicySample]) -> dict:
    """Small JSON-friendly rollup, with no claim about gait or propulsion."""
    if not samples:
        return {
            "policy_samples": 0, "walk_policy_samples": 0,
            "stand_policy_samples": 0, "held_policy_samples": 0,
            "max_requested_vx_mps": 0., "max_applied_vx_mps": 0.,
            "limited_by": [],
        }
    return {
        "policy_samples": len(samples),
        "walk_policy_samples": sum(s.policy == "walk" for s in samples),
        "stand_policy_samples": sum(s.policy == "stand" for s in samples),
        "held_policy_samples": sum(s.policy == "held" for s in samples),
        "max_requested_vx_mps": max(s.requested[0] for s in samples),
        "max_applied_vx_mps": max(s.applied[0] for s in samples),
        "limited_by": sorted({reason for s in samples for reason in s.limited_by}),
    }
