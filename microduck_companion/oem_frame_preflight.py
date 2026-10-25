"""F3-E: fixture-only validator for the OEM local media.frame header.

Pinned OEM sends JSON response followed by exact UYVY bytes. This
module has NO socket code and cannot acquire camera images or move a robot.
A matching JSON envelope does not authenticate its source.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .passive_sources import _strict_json, PassiveSourceError

OEM_REVISION = "942e58e3aa6dbb28e7037203fff11866122c7567"
OEM_LOCAL_SOCKET = "/run/mediad/media.sock"
MAX_HEADER_BYTES = 2048
MAX_FRAME_BYTES = 4 * 1024 * 1024
MAX_AGE_US = 2_000_000
FUTURE_US = 100_000
MIN_INTERVAL_S = 5.
FIELDS = {"width","height","format","bytes","captured_at_unix_us","rotate"}

class FrameContractError(ValueError):
    """Invalid or unsafe frame-shaped metadata."""

@dataclass(frozen=True)
class FrameShape:
    width: int
    height: int
    rotation: int
    expected_bytes: int
    age_us: int
    tail_length_checked: bool = False
    source_verified: bool = False
    physical_camera_validated: bool = False
    motor_commands_issued: int = 0

@dataclass(frozen=True)
class CaptureChecklist:
    operator_opt_in: bool = False
    privacy_reviewed: bool = False
    peer_verified: bool = False
    revision_checked: bool = False
    robot_stationary_supervised: bool = False
    resource_audit_passed: bool = False

@dataclass(frozen=True)
class CapturePreflight:
    status: str
    missing: tuple[str, ...]
    frames_requested: int = 0
    transport_connected: bool = False
    sensor_authenticated: bool = False
    motor_commands_issued: int = 0


def parse_mock_frame_header(
    raw: bytes, *, now_unix_us: int, request_id: int = 1,
) -> FrameShape:
    if (type(raw) is not bytes or not raw or len(raw)>MAX_HEADER_BYTES
            or b"\n" in raw[:-1] or raw.endswith(b"\n\n")):
        raise FrameContractError("invalid header length/line")
    if type(now_unix_us) is not int or now_unix_us < 0:
        raise ValueError("invalid current unix time")
    if type(request_id) is not int or not 1 <= request_id <= 65535:
        raise ValueError("invalid expected request ID")
    try:
        data=_strict_json(raw.removesuffix(b"\n"))
    except (PassiveSourceError,ValueError,TypeError) as exc:
        raise FrameContractError("invalid response JSON") from exc
    if (set(data)!={"jsonrpc","id","result"} or data["jsonrpc"]!="2.0"
            or type(data["id"]) is not int or data["id"]!=request_id
            or type(data["result"]) is not dict):
        raise FrameContractError("unsupported response envelope")
    r=data["result"]
    if set(r)!=FIELDS:
        raise FrameContractError("unsupported frame header")
    if any(type(r[k]) is not int or r[k]<0 for k in
           ("width","height","bytes","captured_at_unix_us","rotate")):
        raise FrameContractError("invalid frame numeric fields")
    w,h=r["width"],r["height"]
    length=r["bytes"]
    if (not 2<=w<=4096 or w%2 or not 1<=h<=4096
            or type(r["format"]) is not str or r["format"]!="UYVY"
            or r["rotate"] not in (0,90,180,270)
            or length!=w*h*2 or length>MAX_FRAME_BYTES):
        raise FrameContractError("invalid UYVY geometry or memory cap")
    age=now_unix_us-r["captured_at_unix_us"]
    if not -FUTURE_US<=age<=MAX_AGE_US:
        raise FrameContractError("stale or future timestamp")
    return FrameShape(w,h,r["rotate"],length,age)


def check_mock_frame_tail(
    raw_header: bytes, raw_tail: bytes, *, now_unix_us: int,
) -> FrameShape:
    if type(raw_tail) is not bytes:
        raise FrameContractError("fixture tail must be bytes")
    from dataclasses import replace
    result=parse_mock_frame_header(raw_header,now_unix_us=now_unix_us)
    if len(raw_tail)!=result.expected_bytes:
        raise FrameContractError("incorrect fixture UYVY byte count")
    return replace(result,tail_length_checked=True)


def evaluate_capture_preflight(
    checks: CaptureChecklist, *, now_s: float, last_attempt_s: float|None=None,
) -> CapturePreflight:
    """Plan only: even all true claims do not authorize a real frame request."""
    if type(checks) is not CaptureChecklist:
        raise TypeError("capture checklist required")
    if (type(now_s) not in (int,float) or not math.isfinite(now_s)
            or now_s<0):
        raise ValueError("invalid monotonic time")
    if last_attempt_s is not None and (
        type(last_attempt_s) not in (int,float)
        or not math.isfinite(last_attempt_s)
        or not 0<=last_attempt_s<=now_s):
        raise ValueError("invalid previous monotonic time")
    names=(
        "operator_opt_in","privacy_reviewed","peer_verified",
        "revision_checked","robot_stationary_supervised",
        "resource_audit_passed",
    )
    if any(type(getattr(checks,k)) is not bool for k in names):
        raise ValueError("checklist flags must be boolean")
    missing=[k for k in names if not getattr(checks,k)]
    if last_attempt_s is not None and now_s-last_attempt_s<MIN_INTERVAL_S:
        missing.append("planned_minimum_interval")
    return CapturePreflight(
        "blocked" if missing else "declared_checks_only_no_capture_authorized",
        tuple(missing))
