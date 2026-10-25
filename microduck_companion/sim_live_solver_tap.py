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
            "qvel": int(model.jnt_dofadr[joint]),
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


def capture_actuators_before_step(model, data, names: dict) -> dict:
    """P0e: copy the *input* that the original next mj_step will consume.

    OEM World.step already serializes physics and joint writes using its own
    lock. This function never assigns to model/data. All floating point
    values are checked before being written to the diagnostic queue.

    The pinned MJCF uses position actuators with gear 1. The qpos/qvel and
    ctrl entries copied here PRECEDE the physics integration; the measured
    actuator_force captured AFTER step is therefore not compared with a
    future/post-integration angle.
    """
    actual = {}
    for name, joint in names["actuators"].items():
        a, qpos, dof = joint["actuator"], joint["qpos"], joint["qvel"]
        limited = bool(model.actuator_forcelimited[a])
        low, high = model.actuator_forcerange[a]
        actual[name] = {
            "control_rad": _finite(data.ctrl[a], f"{name} pre ctrl"),
            "position_rad": _finite(data.qpos[qpos], f"{name} pre qpos"),
            "velocity_rad_s": _finite(data.qvel[dof], f"{name} pre qvel"),
            "gain_p_nm_per_rad": _finite(
                model.actuator_gainprm[a, 0], f"{name} active gain"),
            "bias_position_nm_per_rad": _finite(
                model.actuator_biasprm[a, 1], f"{name} active position bias"),
            "bias_velocity_nm_s_per_rad": _finite(
                model.actuator_biasprm[a, 2], f"{name} active velocity bias"),
            "gear": _finite(model.actuator_gear[a, 0], f"{name} gear"),
            "force_limited": limited,
            "force_min_nm": _finite(low, f"{name} force lower"),
            "force_max_nm": _finite(high, f"{name} force upper"),
            "joint_damping_nm_s": _finite(
                model.dof_damping[dof], f"{name} damping"),
            "joint_frictionloss_nm": _finite(
                model.dof_frictionloss[dof], f"{name} frictionloss"),
        }
    return {
        "time_before_step_s": _finite(data.time, "pre step clock"),
        "actuators": actual,
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
        except Exception as exc:
            # The writer is optional diagnostic work: never affect OEM physics.
            self.writer_error = f"{type(exc).__name__}: {exc}"

    def submit(self, record: dict) -> None:
        if self.writer_error is not None:
            raise TapError(f"solver writer failed: {self.writer_error}")
        try:
            self.queue.put_nowait(record)
        except Full as exc:
            raise TapError("solver writer queue full; diagnostic incomplete") from exc


class SolverTap:
    def __init__(self, mj, writer: NonBlockingWriter, *, audit: bool = False):
        self.audit = audit
        self.mj = mj
        self.writer = writer
        self.count = 0
        self.names = None
        self.model = None
        self.disabled = False

    def _disable(self, exc: Exception, step: int) -> None:
        self.disabled = True
        try:
            self.writer.submit({
                "kind": "error", "reason": f"{type(exc).__name__}: {exc}",
                "step": step,
            })
        except Exception:
            pass  # An incomplete or gapped stream fails offline validation.

    def before_step(self, model, data) -> dict | None:
        """Capture only every fourth *future* step; never obstruct OEM physics."""
        if not self.audit or self.disabled or (self.count + 1) % EVERY_N_STEPS:
            return None
        try:
            if self.names is None:
                self.names = _resolve_names(model, self.mj)
                self.model = model
            if model is not self.model:
                raise TapError("more than one MuJoCo model under audit")
            return capture_actuators_before_step(model, data, self.names)
        except Exception as exc:
            self._disable(exc, self.count + 1)
            return None

    def after_step(self, model, data, *, pre_step: dict | None = None) -> None:
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
                    "p0e_active_gain_pre_step": self.audit,
                })
            if model is not self.model:
                raise TapError("more than one MuJoCo model under instrumented server")
            frame = capture_solver_step(model, data, self.mj, self.names, self.count)
            if self.audit:
                if pre_step is None:
                    raise TapError("pre-step audit frame unavailable")
                # Only data, never a control output. Pre-step and force-cache
                # epochs can now be evaluated without a post-step offset.
                frame["pre_step_actuators"] = pre_step
            frame["capture_us"] = (
                time.perf_counter_ns() - started
            ) / 1000.0
            self.writer.submit(frame)
        except Exception as exc:
            # A broken optional diagnostic must NEVER interrupt mj_step or
            # change the manufacturer's real-time controller behaviour.
            self._disable(exc, self.count)


def install_solver_tap(output: Path, *, mj=None,
                       writer: NonBlockingWriter | None = None,
                       audit: bool = False) -> SolverTap:
    """Patch ONLY mj_step; original method remains the entire physics authority."""
    if mj is None:
        import mujoco as mj
    if writer is None:
        writer = NonBlockingWriter(output)
    original = mj.mj_step
    if getattr(original, "_microduck_p0d_wrapped", False):
        raise TapError("MuJoCo solver tap already installed")
    tap = SolverTap(mj, writer, audit=audit)

    def wrapped(model, data, *args, **kwargs):
        # Even an unexpected Python read error cannot suppress mj_step.
        pre_step = (tap.before_step(model, data)
                    if not args and not kwargs else None)
        result = original(model, data, *args, **kwargs)
        if args or kwargs:
            # Official body_server invokes exactly mj_step(model, data).
            # An unknown invocation must never be given false diagnostics.
            tap.disabled = True
        else:
            tap.after_step(model, data, pre_step=pre_step)
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
    install_solver_tap(
        output, audit=os.environ.get("MICRODUCK_SIM_ACTUATOR_AUDIT") == "YES")
    return True
