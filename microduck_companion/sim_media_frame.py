"""SIM-1A: acquire ONE ephemeral OEM MuJoCo mediad frame, read-only.

The official pinned mediad frame socket serves JSON-RPC NDJSON metadata and
exactly one raw UYVY payload. The caller must never claim object recognition,
sensor authentication, floor safety, action completion or a motor permission.
No file, database, model, network service or motor RPC is touched here.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import select
import socket
import stat
import sys
import time

MAX_FRAME_BYTES = 16 * 1024 * 1024
MAX_HEADER_BYTES = 2048
MAX_TIMEOUT_S = 3.0
MAX_AGE_S = 2.0
REQUEST = b'{"jsonrpc":"2.0","id":1,"method":"media.frame"}\n'


class MediaFrameError(ValueError):
    """Frame missing, malformed, stale or not provably complete."""


@dataclass(frozen=True)
class EphemeralMediaFrame:
    width: int
    height: int
    rotate: int
    captured_at_unix_us: int
    pixels_uyvy: bytes
    peer_uid: int | None

    @property
    def evidence(self) -> dict:
        return {
            "status": "frame_received_not_authenticated",
            "width": self.width,
            "height": self.height,
            "rotate": self.rotate,
            "bytes": len(self.pixels_uyvy),
            "captured_at_unix_us": self.captured_at_unix_us,
            "peer_uid_observed": self.peer_uid,
            "format": "UYVY",
            "source_claim": "simulated_oem_media_frame_socket_unverified",
            "semantic_category_verified": False,
            "floor_certified": False,
            "motor_commands_issued": 0,
            "image_persisted": False,
        }


def _read_exact(conn: socket.socket, size: int, deadline: float) -> bytes:
    data = bytearray()
    while len(data) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise MediaFrameError("frame deadline exceeded")
        readable, _, _ = select.select([conn], [], [], remaining)
        if not readable:
            raise MediaFrameError("frame deadline exceeded")
        try:
            chunk = conn.recv(min(size - len(data), 65536))
        except (OSError, TimeoutError) as exc:
            raise MediaFrameError("frame receive failed") from exc
        if not chunk:
            raise MediaFrameError("truncated frame payload")
        data.extend(chunk)
    return bytes(data)


def _read_header(conn: socket.socket, deadline: float) -> dict:
    # Read one byte at a time: recv() must not consume raw UYVY after NDJSON.
    line = bytearray()
    while len(line) < MAX_HEADER_BYTES:
        byte = _read_exact(conn, 1, deadline)
        if byte == b"\n":
            break
        line.extend(byte)
    else:
        raise MediaFrameError("media.frame header too long")

    def unique(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise MediaFrameError("duplicate header key")
            result[key] = value
        return result

    try:
        obj = json.loads(
            line.decode("utf-8"), object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                MediaFrameError("invalid nonfinite JSON literal")),
        )
    except (UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise MediaFrameError("invalid media.frame header") from exc
    if (type(obj) is not dict or set(obj) != {"jsonrpc", "id", "result"}
            or obj["jsonrpc"] != "2.0" or type(obj["id"]) is not int
            or obj["id"] != 1 or type(obj["result"]) is not dict):
        raise MediaFrameError("unexpected media.frame response")
    return obj["result"]


def acquire_simulated_oem_frame(path: str | Path, *, timeout_s: float = 2.0,
                                max_age_s: float = 2.0) -> EphemeralMediaFrame:
    """Ask mediad once, bound entire read, reject invalid pixels and timestamps.

    Socket identity is deliberately NOT trusted: path/uid alone cannot prove
    official binaries or physical hardware. Read pixels only; no camera driver.
    """
    if (type(timeout_s) not in (float, int)
            or not math.isfinite(timeout_s) or not 0 < timeout_s <= MAX_TIMEOUT_S
            or type(max_age_s) not in (float, int)
            or not math.isfinite(max_age_s) or not 0 < max_age_s <= MAX_AGE_S):
        raise ValueError("invalid acquisition bounds")
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("media.frame socket must have an absolute path")
    deadline = time.monotonic() + timeout_s
    try:
        if not stat.S_ISSOCK(path.lstat().st_mode):
            raise MediaFrameError("not a Unix socket")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
            conn.settimeout(timeout_s)
            conn.connect(str(path))
            peer_uid = None
            if hasattr(socket, "SO_PEERCRED"):
                import struct
                pid, peer_uid, gid = struct.unpack(
                    "3i", conn.getsockopt(
                        socket.SOL_SOCKET, socket.SO_PEERCRED,
                        struct.calcsize("3i")),
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MediaFrameError("frame deadline exceeded")
            conn.settimeout(remaining)
            conn.sendall(REQUEST)
            header = _read_header(conn, deadline)
            if set(header) != {
                "width", "height", "format", "bytes",
                "captured_at_unix_us", "rotate"
            }:
                raise MediaFrameError("wrong media.frame result schema")
            width, height, length = (
                header["width"], header["height"], header["bytes"]
            )
            stamp, rotation = header["captured_at_unix_us"], header["rotate"]
            if (any(type(v) is not int for v in (
                    width, height, length, stamp, rotation))
                    or not 0 < width <= 4096 or width % 2
                    or not 0 < height <= 4096
                    or length != width * height * 2
                    or not 0 < length <= MAX_FRAME_BYTES
                    or header["format"] != "UYVY"
                    or rotation not in (0, 90, 180, 270)
                    or stamp <= 0):
                raise MediaFrameError("invalid UYVY geometry or timestamp")
            pixels = _read_exact(conn, length, deadline)
            age_s = time.time() - stamp / 1_000_000
            if not -0.25 <= age_s <= max_age_s:
                raise MediaFrameError("stale or future capture timestamp")
    except (OSError, TimeoutError) as exc:
        raise MediaFrameError("mediad frame socket unavailable") from exc
    return EphemeralMediaFrame(
        width, height, rotation, stamp, pixels, peer_uid,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One read-only OEM MuJoCo mediad frame; no image saved"
    )
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        frame = acquire_simulated_oem_frame(
            args.state_dir.resolve() / "duck-a-frame.sock"
        )
    except (MediaFrameError, ValueError) as exc:
        print(json.dumps({"status": "STOP_NO_VALID_CAMERA_FRAME",
                          "detail": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(frame.evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
