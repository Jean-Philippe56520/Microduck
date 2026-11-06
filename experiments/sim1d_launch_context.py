"""Read-only Linux launch evidence for SIM-1D, never camera or pixel GT.

The official launcher owns all services. This guard only checks its existing
pidfiles, processes, socket peers, listener ownership and pinned source trees.
It sends no RPC, changes no scene and cannot authenticate a physical sensor.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import socket
import stat
import struct
import subprocess

OEM_PIN = "942e58e3aa6dbb28e7037203fff11866122c7567"
RL_PIN = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
MODULE = "mjlab_microduck.sim.body_server"
SCENES = {"ball": "scene_ball.xml", "empty": "scene.xml"}


class LaunchContextError(ValueError):
    """The requested experiment cannot be tied to its live launch context."""


def _read(path: Path, limit: int = 16384) -> bytes:
    with path.open("rb") as stream:
        value = stream.read(limit + 1)
    if len(value) > limit:
        raise LaunchContextError("oversized launch evidence")
    return value


def _options(argv: tuple[str, ...]) -> dict[str, str | bool]:
    """Accept only explicit, unambiguous options emitted by duck-sim."""
    result: dict[str, str | bool] = {}
    i = 0
    while i < len(argv):
        name = argv[i]
        if not name.startswith("--") or "=" in name or name in result:
            raise LaunchContextError("ambiguous launch arguments")
        if name == "--headless":
            result[name] = True
            i += 1
        else:
            if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
                raise LaunchContextError("missing launch option value")
            result[name] = argv[i + 1]
            i += 2
    return result


def validate_launch_args(body: tuple[str, ...], robot: tuple[str, ...],
                         media: tuple[str, ...], *, state_dir: Path,
                         rl_dir: Path, oem_dir: Path, world_case: str) -> dict:
    """Pure consistency check; filesystem/process ownership is checked below."""
    if world_case not in SCENES or body[1:3] != ("-m", MODULE):
        raise LaunchContextError("wrong body module or requested world")
    b, r, m = _options(body[3:]), _options(robot[1:]), _options(media[1:])
    if set(b) - {"--port", "--ducks", "--keyframe", "--headless",
                 "--scene", "--cameras", "--frame-port", "--camera-fps"}:
        raise LaunchContextError("unsupported body options")
    if (b.get("--ducks") != "1" or b.get("--cameras") != "a"
            or b.get("--camera-fps") != "30"
            or b.get("--keyframe") not in ("HOME", "SIT")):
        raise LaunchContextError("unsupported body configuration")
    scene_root = rl_dir / "src/mjlab_microduck/robot/microduck"
    scene = b.get("--scene", str(scene_root / "scene.xml"))
    if scene != str(scene_root / SCENES[world_case]):
        raise LaunchContextError("requested world differs from body scene")
    if world_case == "ball" and b["--keyframe"] != "HOME":
        raise LaunchContextError("ball scene has no SIT keyframe")
    ports = (b.get("--port"), b.get("--frame-port"))
    if any(type(p) is not str or not p.isascii() or not p.isdigit()
           or not 1024 <= int(p) <= 65535 for p in ports) or ports[0] == ports[1]:
        raise LaunchContextError("invalid or overlapping body ports")
    if (not body or body[0] != str(rl_dir / ".venv/bin/python")
            or not robot or robot[0] != str(oem_dir / "target/debug/robotd")
            or not media or media[0] != str(oem_dir / "target/debug/mediad")):
        raise LaunchContextError("unexpected launcher executable path")
    expected_robot = {
        "--sim": "127.0.0.1:" + ports[0],
        "--params": str(state_dir / "robotd-duck-a.toml"),
        "--socket": str(state_dir / "duck-a.sock"),
    }
    if r != expected_robot:
        raise LaunchContextError("robotd is not linked to this body")
    expected_media = {
        "--sim-camera": "127.0.0.1:" + ports[1],
        "--config": str(state_dir / "mediad-duck-a.toml"),
        "--robot-socket": str(state_dir / "duck-a.sock"),
        "--tof-socket": str(state_dir / "duck-a-tof.sock"),
        "--config-socket": str(state_dir / "duck-a-config.sock"),
        "--updater-socket": str(state_dir / "duck-a-updater.sock"),
        "--token": str(state_dir / "duck-a/hf-token"),
        "--frame-socket": str(state_dir / "duck-a-frame.sock"),
        "--port": "8443", "--web-port": "8080",
    }
    if m != expected_media:
        raise LaunchContextError("mediad is not linked to this body and socket")
    return {"scene": SCENES[world_case], "initial_keyframe": b["--keyframe"],
            "body_port": int(ports[0]), "camera_port": int(ports[1])}


def _process(state_dir: Path, name: str) -> tuple[int, str, tuple[str, ...]]:
    pidfile = state_dir / (name + ".pid")
    if not stat.S_ISREG(pidfile.lstat().st_mode):
        raise LaunchContextError("pidfile is not a regular file")
    raw = _read(pidfile, 32).strip()
    if not raw.isdigit() or not 1 < int(raw) < 2 ** 31:
        raise LaunchContextError("invalid pidfile")
    pid = int(raw)
    proc = Path("/proc") / str(pid)
    # Start ticks distinguish a recycled PID across the two series boundaries.
    before = _read(proc / "stat").rsplit(b")", 1)[1].split()[19]
    argv = tuple(_read(proc / "cmdline").decode("utf-8").rstrip("\0").split("\0"))
    if not argv or not Path(argv[0]).is_absolute():
        raise LaunchContextError("process has no absolute executable path")
    if (proc / "exe").resolve(strict=True) != Path(argv[0]).resolve(strict=True):
        raise LaunchContextError("executable differs from process argv")
    after = _read(proc / "stat").rsplit(b")", 1)[1].split()[19]
    if before != after or not before.isdigit():
        raise LaunchContextError("process changed while inspecting it")
    return pid, before.decode("ascii"), argv


def _peer(path: Path, expected_pid: int) -> tuple[int, int]:
    before = path.lstat()
    if not stat.S_ISSOCK(before.st_mode):
        raise LaunchContextError("expected OEM Unix socket")
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(0.75)
        client.connect(str(path))
        pid, uid, _ = struct.unpack("3i", client.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
    after = path.lstat()
    if (pid != expected_pid or uid != os.getuid()
            or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)):
        raise LaunchContextError("socket peer or inode differs from launch")
    return before.st_dev, before.st_ino


def _listeners(pid: int, ports: tuple[int, int]) -> None:
    proc = Path("/proc") / str(pid)
    owned = set()
    for fd in (proc / "fd").iterdir():
        try:
            owned.add(os.readlink(fd))
        except FileNotFoundError:
            continue  # A short-lived connection closed; required listeners remain checked.
    found = set()
    for line in _read(proc / "net/tcp", 1024 * 1024).decode("ascii").splitlines()[1:]:
        fields = line.split()
        address, port_hex = fields[1].split(":")
        if (fields[3] == "0A" and address in ("0100007F", "00000000")
                and "socket:[" + fields[9] + "]" in owned):
            found.add(int(port_hex, 16))
    if not set(ports) <= found:
        raise LaunchContextError("body does not own both expected listeners")


def _pin(root: Path, expected: str) -> None:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, timeout=3, env=env).stdout.strip()
    if (git("rev-parse", "HEAD").decode("ascii") != expected
            or git("status", "--porcelain", "--untracked-files=no")):
        raise LaunchContextError("OEM source pin or tracked files changed")


def verify_launch_context(state_dir: Path, world_case: str) -> dict:
    """Fail closed; call before AND after the bounded acquisition series.

    Launch provenance is not proof of loaded in-memory scene state, camera
    visibility, exact simulation time, source authentication or motor effect.
    """
    try:
        root = Path(__file__).resolve().parents[1]
        rl, oem = root / "upstream/microduck_rl", root / "upstream/microduck"
        _pin(rl, RL_PIN)
        _pin(oem, OEM_PIN)
        body, robot, media = (_process(state_dir, n) for n in
                              ("body", "duck-a", "duck-a-media"))
        context = validate_launch_args(body[2], robot[2], media[2],
                                       state_dir=state_dir, rl_dir=rl,
                                       oem_dir=oem, world_case=world_case)
        sockets = [_peer(state_dir / "duck-a.sock", robot[0]),
                   _peer(state_dir / "duck-a-frame.sock", media[0])]
        _listeners(body[0], (context["body_port"], context["camera_port"]))
        scene = rl / "src/mjlab_microduck/robot/microduck" / context["scene"]
        xml = _read(scene)
        contains_ball = b'<include file="ball.xml"' in xml
        if contains_ball != (world_case == "ball"):
            raise LaunchContextError("pinned scene does not match requested world")
        context.update({
            "source": "linux_process_launch_context_not_pixel_gt",
            "oem_pin": OEM_PIN, "rl_pin": RL_PIN,
            "scene_sha256": hashlib.sha256(xml).hexdigest(),
            "launch_scene_contains_ball_xml": contains_ball,
            "processes": [[p[0], p[1]] for p in (body, robot, media)],
            "socket_inodes": [list(p) for p in sockets],
            "actual_camera_pose_verified": False,
            "same_mujoco_step_verified": False,
            "sensor_source_authenticated": False,
        })
        return context
    except (OSError, ValueError, IndexError, KeyError, AttributeError,
            subprocess.SubprocessError) as exc:
        raise LaunchContextError("active launch context could not be verified") from exc
