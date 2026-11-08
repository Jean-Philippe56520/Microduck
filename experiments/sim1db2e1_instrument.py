"""SIM-1D/B2-E1: one OEM RGB render, pose snapshot and UYVY SHA only.

Host/CI simulator instrumentation, NOT a camera backend for a physical robot.
The only camera is the pinned OEM Camera and its original FrameServer.
NO segmentation, second renderer, GT or motor command during robotd operation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import time

from experiments.sim1db2e1_frame_match import validate_record


def install() -> None:
    if os.environ.get("KWIPI_B2E1_INSTRUMENT") != "1":
        return
    from mjlab_microduck.sim import camera as oem
    import mujoco

    if (oem.WIDTH, oem.HEIGHT) != (640, 360):
        raise RuntimeError("STOP_E1_CAMERA_GEOMETRY_DRIFT")
    case = os.environ["KWIPI_B2E1_CASE"]
    if case not in ("ball", "empty"):
        raise RuntimeError("STOP_E1_BAD_WORLD")
    arm = Path(os.environ["KWIPI_B2E1_ARM"])
    sidecar = Path(os.environ["KWIPI_B2E1_SIDECAR"])
    if (not arm.is_absolute() or not sidecar.is_absolute()
            or arm == sidecar or arm.is_symlink() or sidecar.is_symlink()
            or not arm.parent.is_dir() or not sidecar.parent.is_dir()):
        raise RuntimeError("STOP_E1_UNSAFE_PATH")
    original = oem.Camera.render
    seq = 0

    def render_one(self, world) -> None:
        nonlocal seq
        try:
            armed = arm.lstat()
        except FileNotFoundError:
            return original(self, world)
        if not stat.S_ISREG(armed.st_mode) or armed.st_size != 0:
            raise RuntimeError("STOP_E1_INVALID_ARM")
        start = time.perf_counter()
        # Identical to OEM's scene update lock; NEVER render under the lock.
        with world.lock:
            self.renderer.update_scene(world.data, camera=self.camera)
            qpos = world.data.qpos.copy()
            qvel = world.data.qvel.copy()
            sim_time = float(world.data.time)
            pos = [float(x) for x in world.data.cam_xpos[self.camera]]
            mat = [float(x) for x in world.data.cam_xmat[self.camera].reshape(9)]
            gid = int(mujoco.mj_name2id(
                world.model, mujoco.mjtObj.mjOBJ_GEOM, "ball_geom"))
        # Exactly ONE RGB render as in pinned OEM camera.py.
        packed = oem.to_uyvy(self.renderer.render())
        if type(packed) is not bytes or len(packed) != 640 * 360 * 2:
            raise RuntimeError("STOP_E1_UYVY_FRAME_INVALID")
        seq += 1
        record = {
            "schema": 2, "case": case,
            "scene_xml": "scene_ball.xml" if case == "ball" else "scene.xml",
            "render_seq": seq, "sim_time_s": sim_time,
            "uyvy_sha256": hashlib.sha256(packed).hexdigest(),
            "width": 640, "height": 360, "rotation_degrees": 90,
            "ball_geom_id": gid if gid >= 0 else None,
            "qpos": [float(x) for x in qpos],
            "qvel": [float(x) for x in qvel],
            "qpos_sha256": hashlib.sha256(qpos.tobytes()).hexdigest(),
            "camera_pos_xyz": pos, "camera_mat9": mat,
            "render_ms": round((time.perf_counter() - start) * 1000, 3),
        }
        validate_record(record, case)
        line = (json.dumps(record, separators=(",", ":"), allow_nan=False)
                + "\n").encode("ascii")
        if len(line) > 8192:
            raise RuntimeError("STOP_E1_STATE_ROW_OVERSIZE")
        fd = os.open(sidecar, os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW,
                     0o600)
        try:
            if os.fstat(fd).st_size > 1_400_000:
                raise RuntimeError("STOP_E1_SIDECAR_SIZE")
            if os.write(fd, line) != len(line):
                raise RuntimeError("STOP_E1_INCOMPLETE_SIDECAR_WRITE")
        finally:
            os.close(fd)
        with self.lock:
            self.latest = packed

    oem.Camera.render = render_one
