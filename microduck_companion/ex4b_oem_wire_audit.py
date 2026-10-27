"""EX4-B: OEM v44 wire-evidence review; never a physical execution receipt.

Pure, fixture-only analysis of an existing robotd JSON-RPC vocabulary.
No socket/client, actuator, writer, database, camera, Qwen or new scheduler.
An OEM reply acknowledges an intent or computes a target, not completion.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from .experience_ledger import _key, _epoch


PINNED_OEM_SHA = "942e58e3aa6dbb28e7037203fff11866122c7567"
PINNED_API_VERSION = 44
FIXTURE_SOURCE = "oem_v44_wire_fixture_only"
MAX_FRAMES = 8
MAX_LOCAL_WINDOW_S = 30.0  # Laboratory sanity check, not a robot deadline
_SKILL = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_TARGETS = {"robot.do", "robot.look", "robot.move", "robot.head", "robot.stop"}
_STATE_FIELDS = frozenset({
    "t", "t_ns", "move", "head", "policy", "safety", "loop", "joints",
    "targets", "velocities", "currents_ma", "odom", "theremin",
    "chorale", "imu", "frames", "skeleton",
})


def _number(value: object, *, nonnegative: bool = False) -> float:
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("nonfinite or nonnumeric OEM fixture value")
    out = float(value)
    if nonnegative and out < 0:
        raise ValueError("negative OEM fixture measurement")
    return out


def _integer(value: object, *, allow_zero: bool = False,
             maximum: int = 2_147_483_647) -> int:
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= maximum:
        raise ValueError("invalid OEM fixture integer")
    return value


def _obj(value: object, *, required: set[str],
         optional: set[str] | frozenset[str] = frozenset()) -> dict[str, Any]:
    if type(value) is not dict or not required <= value.keys() or not value.keys() <= required | optional:
        raise ValueError("missing or unexpected OEM fixture fields")
    return value


def _vector(value: object, n: int) -> tuple[float, ...]:
    if type(value) not in (list, tuple) or len(value) != n:
        raise ValueError("invalid OEM fixture vector shape")
    return tuple(_number(v) for v in value)


@dataclass(frozen=True)
class OemWireProposal:
    """Synthetic packet with explicit local provenance; not an issued command."""

    session: str
    sequence: int
    sent_monotonic_s: float
    packet: dict[str, Any]
    source: str = FIXTURE_SOURCE
    oem_sha: str = PINNED_OEM_SHA
    api_version: int = PINNED_API_VERSION

    def __post_init__(self) -> None:
        _key(self.session, self.sequence)
        _epoch(self.sent_monotonic_s)
        if (self.source != FIXTURE_SOURCE or self.oem_sha != PINNED_OEM_SHA
                or type(self.api_version) is not int
                or self.api_version != PINNED_API_VERSION):
            raise ValueError("unapproved OEM provenance or API version")


@dataclass(frozen=True)
class OemWireFrame:
    """Synthetic received reply or state, with a test-only local timestamp."""

    received_monotonic_s: float
    packet: dict[str, Any]
    source: str = FIXTURE_SOURCE

    def __post_init__(self) -> None:
        _epoch(self.received_monotonic_s)
        if self.source != FIXTURE_SOURCE:
            raise ValueError("unapproved OEM frame source")


@dataclass(frozen=True)
class OemWireVerdict:
    session: str
    sequence: int
    method: str
    request_id: int | None
    reply_status: str
    state_status: str
    reason: str
    source: str = FIXTURE_SOURCE
    authorized: str = "not_attested"
    executed: str = "not_attested"
    physical_execution_verified: bool = False
    causality_established: bool = False
    physical_learning_allowed: bool = False
    motor_commands_issued: int = 0


def _request(packet: dict[str, Any]) -> tuple[str, int | None]:
    p = _obj(packet, required={"jsonrpc", "method"},
             optional={"id", "params"})
    if p["jsonrpc"] != "2.0" or type(p["method"]) is not str:
        raise ValueError("invalid JSON-RPC request header")
    method = p["method"]
    if method not in _TARGETS:
        raise ValueError("unsupported or mutating OEM method")
    request_id = p.get("id")
    if request_id is not None:
        _integer(request_id)
    if method in {"robot.look", "robot.stop"} and request_id is None:
        raise ValueError("discrete method must be an answered request")
    params = p.get("params")
    if method == "robot.stop":
        if params not in (None, {}):
            raise ValueError("robot.stop has no parameters")
    elif method == "robot.do":
        x = _obj(params, required={"skill"})
        if type(x["skill"]) is not str or not _SKILL.fullmatch(x["skill"]):
            raise ValueError("invalid skill name")
    elif method == "robot.look":
        x = _obj(params, required={"x", "y", "z"}, optional={"neck_pitch"})
        for key in ("x", "y", "z"):
            _number(x[key])
        if "neck_pitch" in x:
            _number(x["neck_pitch"])
    elif method == "robot.move":
        x = _obj(params, required={"vx", "vy", "vyaw"})
        for key in ("vx", "vy", "vyaw"):
            _number(x[key])
    elif method == "robot.head":
        x = _obj(params, required={"neck_pitch", "head_pitch", "head_yaw", "head_roll"})
        for key in ("neck_pitch", "head_pitch", "head_yaw", "head_roll"):
            _number(x[key])
    return method, request_id


def _reply(frame: OemWireFrame, *, request_id: int, method: str) -> str:
    p = _obj(frame.packet, required={"jsonrpc", "id"},
             optional={"result", "error"})
    if p["jsonrpc"] != "2.0" or type(p["id"]) is not int or p["id"] != request_id:
        raise ValueError("uncorrelated JSON-RPC reply")
    if ("result" in p) == ("error" in p):
        raise ValueError("reply needs exactly one of result/error")
    if "error" in p:
        error = _obj(p["error"], required={"code", "message"}, optional={"data"})
        if type(error["code"]) is not int or type(error["message"]) is not str or not error["message"]:
            raise ValueError("malformed JSON-RPC error")
        return "rpc_error"
    if method == "robot.look":
        result = _obj(p["result"], required={"head", "clamped"})
        head = _obj(result["head"], required={
            "neck_pitch", "head_pitch", "head_yaw", "head_roll",
        })
        for val in head.values():
            _number(val)
        if type(result["clamped"]) is not bool:
            raise ValueError("malformed OEM gaze result")
        return "target_clamped_only" if result["clamped"] else "target_computed_only"
    result = _obj(p["result"], required={"accepted"}, optional={"reason"})
    if type(result["accepted"]) is not bool or (
        "reason" in result
        and (result["reason"] is not None and type(result["reason"]) is not str)
    ):
        raise ValueError("malformed OEM intent result")
    if not result["accepted"]:
        if not result.get("reason"):
            raise ValueError("OEM refusal lacks explanation")
        return "refused"
    if method == "robot.do":
        return "queued_only"
    if method == "robot.stop":
        return "zero_velocity_requested_only"
    return "intent_received_only"


def _state(frame: OemWireFrame) -> tuple[float, int, bool, bool]:
    packet = _obj(frame.packet, required={"jsonrpc", "method", "params"})
    if packet["jsonrpc"] != "2.0" or packet["method"] != "robot.state":
        raise ValueError("not an OEM state notification")
    p = _obj(packet["params"], required={"t", "t_ns", "move", "policy", "safety", "loop"},
             optional=_STATE_FIELDS - {"t", "t_ns", "move", "policy", "safety", "loop"})
    elapsed = _number(p["t"], nonnegative=True)
    mono = _integer(p["t_ns"], allow_zero=True, maximum=2**64 - 1)
    if type(p["policy"]) is not str or not p["policy"] or len(p["policy"]) > 64:
        raise ValueError("invalid policy label")
    move = _obj(p["move"], required={"requested", "applied"}, optional={"limited_by"})
    _vector(move["requested"], 3)
    _vector(move["applied"], 3)
    limits = move.get("limited_by", [])
    if type(limits) is not list or len(limits) > 8 or any(
        type(v) is not str or not 1 <= len(v) <= 64 for v in limits
    ):
        raise ValueError("invalid OEM limitation descriptions")
    safety = _obj(p["safety"], required={"fallen", "limp"},
                  optional={"gravity", "gain", "picked_up"})
    if type(safety["fallen"]) is not bool or type(safety["limp"]) is not bool:
        raise ValueError("invalid OEM safety flags")
    if "picked_up" in safety and type(safety["picked_up"]) is not bool:
        raise ValueError("invalid pickup flag")
    control_loop = _obj(p["loop"], required={"hz", "missed"})
    _number(control_loop["hz"], nonnegative=True)
    _integer(control_loop["missed"], allow_zero=True, maximum=2**64 - 1)
    unsafe = safety["fallen"] or safety["limp"] or safety.get("picked_up", False)
    limited = bool(limits)
    return elapsed, mono, unsafe, limited


def review_oem_wire_fixture(
    proposal: OemWireProposal,
    *,
    reply: OemWireFrame | None = None,
    states: tuple[OemWireFrame, ...] = (),
    now_monotonic_s: float,
) -> OemWireVerdict:
    """Reject contradictory, stale, future or uncorrelated synthetic OEM wire claims.

    Even accepted replies and fresh state frames are not proof that *this*
    request reached motors or caused the following observations. A real source
    identity and a trusted per-action completion receipt are absent in v44.
    """
    if not isinstance(proposal, OemWireProposal):
        raise TypeError("typed OEM fixture proposal required")
    now = _epoch(now_monotonic_s)
    sent = proposal.sent_monotonic_s
    if not sent <= now <= sent + MAX_LOCAL_WINDOW_S:
        raise ValueError("expired or future fixture conversation")
    method, request_id = _request(proposal.packet)
    if reply is not None and not isinstance(reply, OemWireFrame):
        raise TypeError("typed reply frame required")
    if type(states) is not tuple or len(states) > MAX_FRAMES:
        raise ValueError("bounded tuple of OEM state frames required")
    if reply is not None:
        if request_id is None:
            raise ValueError("notification cannot receive a JSON-RPC reply")
        if not sent <= reply.received_monotonic_s <= now:
            raise ValueError("reply time outside local fixture window")
        status = _reply(reply, request_id=request_id, method=method)
    else:
        status = "no_reply_expected" if request_id is None else "no_reply"
    previous_received = reply.received_monotonic_s if reply is not None else sent
    previous_elapsed = previous_ns = None
    unsafe = limited = False
    zero_clock = False
    for frame in states:
        if not isinstance(frame, OemWireFrame):
            raise TypeError("typed OEM state frame required")
        if not previous_received < frame.received_monotonic_s <= now:
            raise ValueError("replayed, reordered or future state receipt")
        elapsed, ns, bad, clamp = _state(frame)
        if previous_elapsed is not None and elapsed <= previous_elapsed:
            raise ValueError("nonadvancing daemon elapsed clock")
        if previous_ns is not None and (ns <= previous_ns or ns == 0):
            raise ValueError("nonadvancing daemon monotonic clock")
        zero_clock = zero_clock or ns == 0
        previous_elapsed, previous_ns = elapsed, ns
        previous_received = frame.received_monotonic_s
        unsafe = unsafe or bad
        limited = limited or clamp
    if not states:
        state_status = "not_observed"
    elif unsafe:
        state_status = "unsafe_unlinked_telemetry"
    elif zero_clock:
        state_status = "incomplete_clock_unlinked_telemetry"
    elif limited:
        state_status = "limited_unlinked_telemetry"
    else:
        state_status = "coherent_unlinked_telemetry"
    return OemWireVerdict(
        session=proposal.session,
        sequence=proposal.sequence,
        method=method,
        request_id=request_id,
        reply_status=status,
        state_status=state_status,
        reason="OEM v44 has no authenticated per-action start/finish/cause receipt",
    )


def review_oem_wire_batch(
    exchanges: tuple[tuple[OemWireProposal, OemWireFrame | None,
                           tuple[OemWireFrame, ...]], ...],
    *, now_monotonic_s: float,
) -> tuple[OemWireVerdict, ...]:
    """Local anti-replay for one bounded fixture batch, never a persistent writer."""
    if type(exchanges) is not tuple or len(exchanges) > 64:
        raise ValueError("bounded OEM fixture batch required")
    seen_cycles: set[tuple[str, int]] = set()
    seen_rpc: set[tuple[str, int]] = set()
    results: list[OemWireVerdict] = []
    for exchange in exchanges:
        if type(exchange) is not tuple or len(exchange) != 3:
            raise ValueError("invalid fixture exchange")
        proposal, reply, states = exchange
        result = review_oem_wire_fixture(
            proposal, reply=reply, states=states,
            now_monotonic_s=now_monotonic_s,
        )
        cycle = (result.session, result.sequence)
        rpc = (result.session, result.request_id) if result.request_id is not None else None
        if cycle in seen_cycles or (rpc is not None and rpc in seen_rpc):
            raise ValueError("duplicate local cycle or RPC ID in fixture batch")
        seen_cycles.add(cycle)
        if rpc is not None:
            seen_rpc.add(rpc)
        results.append(result)
    return tuple(results)
