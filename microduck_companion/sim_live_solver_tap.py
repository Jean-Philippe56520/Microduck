"""P0d opt-in observation of ORIGINAL live MuJoCo solver states.

The pinned OEM body_server calls mujoco.mj_step inside World.step's lock. A
sitecustomize import (only in the exact headless body process, only on the CI
experiment branch) wraps that call without touching the OEM source. Every
fourth successful step, one immutable snapshot is sent to a bounded,
non-blocking queue serviced by a daemon writer.

The ORIGINAL mj_step is called once and its return value preserved. This
module never advances the simulator, changes controls, or opens robotd IPC.
Failures and dropped frames invalidate the diagnostic; they NEVER turn into
motor commands or silently certified walking evidence.

This monkeypatch DOES add CPU/GIL load. Compare the measured cost and robotd
health before treating results as representative of uninstrumented MuJoCo.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from queue import Full, Queue
import threading
import time

JOINT_NAMES = (
    "left_hip_yaw", "left_hip_roll", "left_hip_pitch", "left_knee",
    "left_ankle", "neck_pitch", "head_pitch", "head_yaw", "head_roll",
    "right_hip_yaw", "right_hip_roll", "right_hip_pitch", "right_knee",
    "right_ankle",
)
EVERY_N_STEPS = 4
MAX_QUEUED_FRAMES = 512
EXPECTED_TIMESTEP_S = 0.005
EXPECTED_BODY_ARGS = (
    "-m", "mjlab_microduck.sim.body_server",
    "--port", "17801", "--ducks", "1",
    "--keyframe", "SIT", "--headless",
)


class TapError(RuntimeError):
    """Invalid or unusable live simulator instrumentation."""


def matching_body_argv(argv: list[str], expected_python: Path) -> bool:
    """The exact official process, not a second simulated/physical controller."""
    if len(argv) != len(EXPECTED_BODY_ARGS) + 1:
        return False
    try:
        binary = Path(argv[0]).resolve(strict=True)
        expected = expected_python.resolve(strict=True)
    except (OSError, ValueError):
        return False
    return binary == expected and tuple(argv[1:]) == EXPECTED_BODY_ARGS


def _finite(value: object, label: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise TapError(f"nonfinite live {label}")
    return value


def _resolve_names(model, mj) -> dict:
    def ident(kind, name):
        result = int(mj.mj_name2id(model, kind, name))
        if result < 0:
            raise TapError(f"pinned simulator lacks {name}")
        return result
    floor = ident(mj.mjtObj.mjOBJ_GEOM, "floor")
    feet = {
        "left": ident(mj.mjtObj.mjOBJ_GEOM, "left_foot_collision"),
        "right": ident(mj.mjtObj.mjOBJ_GEOM, "right_foot_collision"),
    }
    sites = {
        "left": ident(mj.mjtObj.mjOBJ_SITE, "left_foot"),
        "right": ident(mj.mjtObj.mjOBJ_SITE, "right_foot"),
    }
    root = ident(mj.mjtObj.mjOBJ_JOINT, "trunk_base_freejoint")
    actuators = {}
    for name in JOINT_NAMES:
        joint = ident(mj.mjtObj.mjOBJ_JOINT, name)
        actuator = ident(mj.mjtObj.mjOBJ_ACTUATOR, name)
        if int(model.actuator_trnid[actuator][0]) != joint:
            raise TapError(f"unexpected actuator->joint mapping: {name}")
        actuators[name] = {
            "actuator": actuator,
            "qpos": int(model.jnt_qposadr[joint]),
        }
    if abs(_finite(model.opt.timestep, "timestep") - EXPECTED_TIMESTEP_S) > 1e-8:
        raise TapError("unexpected live OEM MuJoCo timestep")
    return {
        "floor": floor, "feet": feet, "sites": sites,
        "root": int(model.jnt_qposadr[root]),
        "actuators": actuators,
    }


def _contact_summary(model, data, mj, names: dict) -> dict:
    import numpy as np

    result = {
        side: {
            "pair_count": 0,
            "normal_force_n": 0.0,
            "tangent_force_norm_n": 0.0,
            "min_signed_distance_m": None,
        }
        for side in ("left", "right")
    }
    for i in range(int(data.ncon)):
        contact = data.contact[i]
        pair = {int(contact.geom1), int(contact.geom2)}
        for side, foot in names["feet"].items():
            if pair != {names["floor"], foot}:
                continue
            force = np.zeros(6, dtype=float)
            mj.mj_contactForce(model, data, i, force)
            distance = _finite(contact.dist, "contact distance")
            normal = _finite(force[0], "normal contact force")
            tangent = math.hypot(
                _finite(force[1], "tangential force 1"),
                _finite(force[2], "tangential force 2"),
            )
            entry = result[side]
            entry["pair_count"] += 1
            entry["normal_force_n"] += normal
            entry["tangent_force_norm_n"] += tangent
            minimum = entry["min_signed_distance_m"]
            entry["min_signed_distance_m"] = (
                distance if minimum is None else min(minimum, distance)
            )
    return result


def capture_solver_step(model, data, mj, names: dict, step: int) -> dict:
    """Copy genuine data immediately AFTER a single OEM mj_step.

    Contacts and mj_contactForce are from that solver step. qpos is the
    post-integration pose, while MuJoCo's contact/kinematic caches may refer
    to the pre-integration state: do not assert exact simultaneity of all
    pose components or reconstruct a continuous time series between samples.
    """
    root = names["root"]
    trunk = [_finite(data.qpos[root + i], "trunk qpos") for i in range(3)]
    controls = {}
    angles = {}
    efforts = {}
    for name, idx in names["actuators"].items():
        a = idx["actuator"]
        controls[name] = _finite(data.ctrl[a], f"{name} actuator control")
        angles[name] = _finite(data.qpos[idx["qpos"]], f"{name} qpos")
        efforts[name] = _finite(data.actuator_force[a], f"{name} actuator force")
    return {
        "kind": "frame",
        "step": step,
        "sim_time_s": _finite(data.time, "simulation time"),
        "trunk_xyz_after_integration_m": trunk,
        "foot_sites_solver_cache_xyz_m": {
            side: [_finite(v, f"{side} foot site") for v in data.site_xpos[site]]
            for side, site in names["sites"].items()
        },
        "contacts_original_solver": _contact_summary(model, data, mj, names),
        "actuator_position_controls_rad": controls,
        "joint_angles_post_integration_rad": angles,
        "actuator_force_simulated_nm": efforts,
        "live_solver_source": True,
    }


class NonBlockingWriter:
    """A small bounded channel; file I/O NEVER executes on the solver thread."""

    def __init__(self, path: Path):
        self.path = path
        self.queue: Queue[dict] = Queue(maxsize=MAX_QUEUED_FRAMES)
        self.writer_error: str | None = None
        self._thread = threading.Thread(target=self._run, name="microduck-p0d-writer",
                                        daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8", buffering=1) as file:
                while True:
                    row = self.queue.get()
                    file.write(json.dumps(row, allow_nan=False, separators=(",", ":"))
                               + "\n")
        except (OSError, ValueError, TypeError) as exc:
            self.writer_error = f"{type(exc).__name__}: {exc}"

    def submit(self, record: dict) -> None:
        if self.writer_error is not None:
            raise TapError(f"solver writer failed: {self.writer_error}")
        try:
            self.queue.put_nowait(record)
        except Full as exc:
            raise TapError("solver writer queue full; diagnostic incomplete") from exc


class SolverTap:
    def __init__(self, mj, writer: NonBlockingWriter):
        self.mj = mj
        self.writer = writer
        self.count = 0
        self.names = None
        self.model = None
        self.disabled = False

    def after_step(self, model, data) -> None:
        if self.disabled:
            return
        self.count += 1
        if self.count % EVERY_N_STEPS:
            return
        started = time.perf_counter_ns()
        try:
            if self.names is None:
                self.names = _resolve_names(model, self.mj)
                self.model = model
                from .sim_flat_zone import RL_COMMIT, FLAT_SCENE_BLOB
                self.writer.submit({
                    "kind": "header",
                    "schema_version": 1,
                    "source": "live_pinned_oem_mujoco_mj_step_tap",
                    "rl_commit": RL_COMMIT,
                    "flat_scene_git_blob": FLAT_SCENE_BLOB,
                    "sample_every_n_physics_steps": EVERY_N_STEPS,
                    "model_timestep_s": EXPECTED_TIMESTEP_S,
                    "capture_is_not_actuator_authority": True,
                })
            if model is not self.model:
                raise TapError("more than one MuJoCo model under instrumented server")
            frame = capture_solver_step(model, data, self.mj, self.names, self.count)
            frame["capture_us"] = (
                time.perf_counter_ns() - started
            ) / 1000.0
            self.writer.submit(frame)
        except (TapError, OSError, ValueError, TypeError, IndexError) as exc:
            self.disabled = True
            try:
                self.writer.submit({"kind": "error", "reason": str(exc),
                                    "step": self.count})
            except TapError:
                pass  # the offline analyzer fails on missing/gapped frames too


def install_solver_tap(output: Path, *, mj=None,
                       writer: NonBlockingWriter | None = None) -> SolverTap:
    """Patch ONLY mj_step; original method remains the entire physics authority."""
    if mj is None:
        import mujoco as mj
    if writer is None:
        writer = NonBlockingWriter(output)
    original = mj.mj_step
    if getattr(original, "_microduck_p0d_wrapped", False):
        raise TapError("MuJoCo solver tap already installed")
    tap = SolverTap(mj, writer)

    def wrapped(model, data, *args, **kwargs):
        result = original(model, data, *args, **kwargs)
        if args or kwargs:
            # Official body_server invokes exactly mj_step(model, data).
            # An unknown invocation must never be given false diagnostics.
            tap.disabled = True
        else:
            tap.after_step(model, data)
        return result

    wrapped._microduck_p0d_wrapped = True
    mj.mj_step = wrapped
    return tap


def activate_if_exact_body_server() -> bool:
    """Only install when sitecustomize runs within the pinned official body."""
    if os.environ.get("MICRODUCK_SIM_SOLVER_TRACE") != "YES":
        return False
    root = Path(os.environ["DUCK_SIM_RL"]).resolve()
    state = Path(os.environ["DUCK_SIM_STATE"]).resolve()
    try:
        argv = [
            os.fsdecode(a) for a in
            Path("/proc/self/cmdline").read_bytes().rstrip(b"\0").split(b"\0")
        ]
    except OSError:
        return False
    if not matching_body_argv(argv, root / ".venv/bin/python"):
        return False
    from .sim_flat_zone import verify_flat_scene
    verify_flat_scene(root)
    output = state / "solver-tap.jsonl"
    # File belongs to a temporary CI state directory, never a tracked source.
    install_solver_tap(output)
    return True
