"""SIM-1D/B2: OPTIONAL, CI-ONLY instrumented replacement of OEM Camera.render.

This is NOT an OEM camera implementation nor deployable robot code.
Invoked exclusively by an explicit sitecustomize opt-in for the pinned
MuJoCo body process. It keeps ONE OEM Camera and ONE UYVY producer while
producing ephemeral geom-ID sidecar evidence; never feeds GT to F2.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import time

from experiments.sim1db2_frame_match import validate_record


def install() -> None:
    if os.getenv("KWIPI_B2_INSTRUMENT") != "1":
        return
    import mujoco
    import numpy as np
    from mjlab_microduck.sim import camera as oem

    if (oem.WIDTH, oem.HEIGHT) != (640, 360):
        raise RuntimeError("STOP_B2_CAMERA_GEOMETRY_DRIFT")
    case = os.environ["KWIPI_B2_CASE"]
    if case not in ("ball", "empty"):
        raise RuntimeError("STOP_B2_UNKNOWN_WORLD")
    arm = Path(os.environ["KWIPI_B2_ARM"])
    sidecar = Path(os.environ["KWIPI_B2_SIDECAR"])
    if (not arm.is_absolute() or not sidecar.is_absolute()
            or arm == sidecar or arm.is_symlink() or sidecar.is_symlink()
            or not arm.parent.is_dir() or not sidecar.parent.is_dir()):
        raise RuntimeError("STOP_B2_INVALID_PATHS")
    original = oem.Camera.render
    seq = 0

    def instrumented_render(self, world) -> None:
        nonlocal seq
        try:
            meta = arm.lstat()
        except FileNotFoundError:
            return original(self, world)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size:
            raise RuntimeError("STOP_B2_ARM_NOT_EMPTY_REGULAR_FILE")
        started = time.perf_counter()
        # Stronger than the unmodified OEM's short scene-update lock.
        # Two renders under this same lock are costly; the independent CI
        # health/latency gate MUST STOP if this interferes with 50 Hz robotd.
        with world.lock:
            data = world.data
            before_time = float(data.time)
            before_qpos = hashlib.sha256(data.qpos.tobytes()).hexdigest()
            self.renderer.update_scene(data, camera=self.camera)
            rgb = self.renderer.render().copy()
            self.renderer.enable_segmentation_rendering()
            try:
                self.renderer.update_scene(data, camera=self.camera)
                segmentation = self.renderer.render().copy()
            finally:
                self.renderer.disable_segmentation_rendering()
            if (float(data.time) != before_time
                    or hashlib.sha256(data.qpos.tobytes()).hexdigest() != before_qpos):
                raise RuntimeError("STOP_B2_SCENE_CHANGED_BETWEEN_RENDERS")
            pos = [float(x) for x in data.cam_xpos[self.camera]]
            mat = [float(x) for x in data.cam_xmat[self.camera].reshape(9)]
            gid = int(mujoco.mj_name2id(
                world.model, mujoco.mjtObj.mjOBJ_GEOM, "ball_geom"))
        if (rgb.shape != (360, 640, 3) or rgb.dtype != np.uint8
                or segmentation.shape != (360, 640, 2)
                or not np.issubdtype(segmentation.dtype, np.integer)):
            raise RuntimeError("STOP_B2_RENDERED_ARRAY_CONTRACT")
        if (case == "ball" and gid < 0) or (case == "empty" and gid >= 0):
            raise RuntimeError("STOP_B2_MISMATCHED_SCENE_GEOM")
        upright = np.rot90(segmentation, k=3)
        if gid >= 0:
            mask = ((upright[:, :, 0] == gid)
                    & (upright[:, :, 1] == int(mujoco.mjtObj.mjOBJ_GEOM)))
            ys, xs = np.where(mask)
            pixels = int(xs.size)
            bbox = ([int(xs.min()), int(ys.min()),
                     int(xs.max()) + 1, int(ys.max()) + 1]
                    if pixels else None)
        else:
            pixels, bbox = 0, None
        packed = oem.to_uyvy(rgb)
        if type(packed) is not bytes or len(packed) != 640 * 360 * 2:
            raise RuntimeError("STOP_B2_UYVY_INVALID")
        seq += 1
        record = {
            "schema": 1, "case": case, "render_seq": seq,
            "sim_time_s": before_time,
            "uyvy_sha256": hashlib.sha256(packed).hexdigest(),
            "width": 640, "height": 360, "rotation_degrees": 90,
            "ball_geom_id": gid if gid >= 0 else None,
            "ball_visible_pixels": pixels, "ball_bbox_upright_xyxy": bbox,
            "qpos_sha256": before_qpos,
            "camera_pos_xyz": pos, "camera_mat9": mat,
            "render_ms": round((time.perf_counter() - started) * 1000, 3),
        }
        validate_record(record, case)
        line = (json.dumps(record, separators=(",", ":"), allow_nan=False)
                + "\n").encode("ascii")
        # One camera renderer is the ONLY writer. Append record BEFORE
        # publishing the corresponding latest UYVY to the OEM FrameServer.
        fd = os.open(sidecar, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            if os.write(fd, line) != len(line):
                raise RuntimeError("STOP_B2_TORN_SIDECAR_WRITE")
        finally:
            os.close(fd)
        with self.lock:
            self.latest = packed

    oem.Camera.render = instrumented_render
