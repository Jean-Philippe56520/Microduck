"""P0j: OFFLINE load-transfer analysis of the exact archived OEM MuJoCo P0e trace.

No motor adapter, sockets or simulator process is used. The OEM solver reports
contact force magnitudes, NOT signed world-XY traction. Cached foot site travel
is NOT contact-patch slip; 10 Hz phase labels only bracket 50 Hz samples.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import statistics
import sys


class OfflineTraceError(ValueError):
    """Incomplete or inconsistent archived simulation evidence."""


SOURCE_RUN = 40193139617
SOURCE_URL = f"https://github.com/Jean-Philippe56520/Microduck/actions/runs/{SOURCE_RUN}"
RL_COMMIT = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
SCENE_BLOB = "a3848be52113a50138d54921748733f09488d496"
EXPECTED_SHA256 = {
    "solver-tap.jsonl": "7606cf8f06a944d7905b29b2a4b144eed304a05bbbf7bbb30d022f61965f8e39",
    "solver-analysis.json": "1be478752366e295f23ce37e970bb3ea994dcfbb5589985681d6399ef7013929",
    "walk-comparison.json": "e5dfc4a86039002e9cf75f62b0bbb9fb22cbde597df5dd2c2f1d849b3c56bb5a",
}
EXPECTED_FRAMES = 888
EXPECTED_WINDOWS = {"stand": 79, "walk": 127}
MAX_INPUT_BYTES = 9_000_000
SAMPLE_INTERVAL_S = 0.02
LOADED_N = 0.1  # Strict diagnostic cutoff, not a safety guarantee.


def demand(ok: bool, reason: str) -> None:
    if not ok:
        raise OfflineTraceError(reason)


def number(value: object, field: str, *, nonnegative: bool = False) -> float:
    demand(type(value) in (int, float) and math.isfinite(value),
           "nonfinite or invalid " + field)
    x = float(value)
    demand(not nonnegative or x >= 0, "negative " + field)
    return x


def _read_exact(path: Path) -> bytes:
    demand(path.name in EXPECTED_SHA256, "unrecognized source name")
    try:
        demand(path.stat().st_size <= MAX_INPUT_BYTES, "oversized input")
        raw = path.read_bytes()
    except OSError as exc:
        raise OfflineTraceError("source file unreadable") from exc
    demand(sha256(raw).hexdigest() == EXPECTED_SHA256[path.name],
           "source digest mismatch: " + path.name)
    return raw


def _strict_json(raw: str) -> object:
    def no_dupes(pairs: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            demand(key not in result, "duplicate JSON property")
            result[key] = value
        return result

    try:
        return json.loads(
            raw, object_pairs_hook=no_dupes,
            parse_constant=lambda _: (_ for _ in ()).throw(
                OfflineTraceError("nonfinite JSON literal")),
        )
    except (ValueError, UnicodeError, TypeError) as exc:
        raise OfflineTraceError("invalid JSON diagnostic") from exc


def _vector_3(obj: object, field: str) -> tuple[float, float, float]:
    demand(isinstance(obj, list) and len(obj) == 3, "invalid " + field)
    values = tuple(number(x, field) for x in obj)
    return values  # type: ignore[return-value]


def _verified_frames(content: bytes) -> list[dict]:
    try:
        lines = content.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise OfflineTraceError("invalid solver UTF-8") from exc
    demand(len(lines) == EXPECTED_FRAMES + 1, "incomplete solver frame stream")
    header = _strict_json(lines[0])
    demand(isinstance(header, dict)
           and header.get("kind") == "header"
           and header.get("schema_version") == 1
           and header.get("source") == "live_pinned_oem_mujoco_mj_step_tap"
           and header.get("rl_commit") == RL_COMMIT
           and header.get("flat_scene_git_blob") == SCENE_BLOB
           and header.get("sample_every_n_physics_steps") == 4
           and header.get("model_timestep_s") == 0.005
           and header.get("capture_is_not_actuator_authority") is True
           and header.get("p0e_active_gain_pre_step") is True,
           "unverified solver header provenance")
    frames = []
    last_time: float | None = None
    last_step = 0
    for line in lines[1:]:
        frame = _strict_json(line)
        demand(isinstance(frame, dict) and frame.get("kind") == "frame"
               and frame.get("live_solver_source") is True,
               "missing original solver frame")
        step = frame.get("step")
        demand(type(step) is int and step == last_step + 4,
               "duplicated or missing physics sample")
        t = number(frame.get("sim_time_s"), "sim_time_s")
        demand(abs(t - step * 0.005) < 1e-5, "inconsistent simulation time")
        if last_time is not None:
            demand(abs(t-last_time-SAMPLE_INTERVAL_S) < 1e-5,
                   "noncontiguous solver clock")
        _vector_3(frame.get("trunk_xyz_after_integration_m"), "trunk")
        contacts = frame.get("contacts_original_solver")
        sites = frame.get("foot_sites_solver_cache_xyz_m")
        demand(isinstance(contacts, dict) and isinstance(sites, dict),
               "solver foot tables missing")
        for foot in ("left", "right"):
            contact = contacts.get(foot)
            demand(isinstance(contact, dict), "missing original contact")
            demand(type(contact.get("pair_count")) is int
                   and contact["pair_count"] >= 0, "invalid contact count")
            number(contact.get("normal_force_n"), "normal_N", nonnegative=True)
            number(contact.get("tangent_force_norm_n"), "tangent_N", nonnegative=True)
            _vector_3(sites.get(foot), foot + "_site")
        last_step, last_time = step, t
        frames.append(frame)
    demand(len(frames) == EXPECTED_FRAMES, "incomplete solver frame stream")
    return frames


def _windows(analysis: dict, comparison: dict) -> dict[str, tuple[float, float]]:
    demand(analysis.get("source") == "original_live_pinned_oem_mujoco_solver"
           and analysis.get("schema_version") == 1
           and analysis.get("original_p0b_stop_confirmed") is True
           and analysis.get("gait_validated") is False
           and analysis.get("locomotion_root_cause") == "unknown",
           "P0e solver analysis is not a verified negative trial")
    provenance = analysis.get("provenance")
    demand(isinstance(provenance, dict)
           and provenance.get("rl_commit") == RL_COMMIT
           and provenance.get("flat_scene_git_blob") == SCENE_BLOB
           and provenance.get("full_stream_validated") is True
           and provenance.get("same_world_as_official_robotd") is True,
           "P0e source provenance invalid")
    demand(comparison.get("environment") == "pinned_official_mujoco_only"
           and comparison.get("stop_confirmed") is True
           and comparison.get("motion_commands_sent_by_existing_j2e_trial") == 24
           and comparison.get("requested_walk_speed_mps") == 0.12
           and comparison.get("gait_validated") is False
           and comparison.get("motion_memory_outcome") == "no_progress_observed",
           "P0e walking comparison not safely completed")
    distance = number(comparison.get("measured_walk_displacement_m"),
                      "final_distance", nonnegative=True)
    demand(distance < 0.01, "unexpected P0e final translation outcome")
    source = analysis.get("phase_windows_from_p0b_10hz")
    demand(isinstance(source, dict) and set(source) == set(EXPECTED_WINDOWS),
           "missing 10 Hz reference windows")
    result = {}
    for phase in ("stand", "walk"):
        interval = source[phase]
        demand(isinstance(interval, list) and len(interval) == 2,
               "invalid phase window")
        lo, hi = (number(x, "phase time", nonnegative=True) for x in interval)
        demand(hi > lo, "nonprogressing phase time")
        result[phase] = (lo, hi)
    demand(result["stand"][1] < result["walk"][0],
           "overlapping phase windows")
    return result


def summarize_window(frames: list[dict]) -> dict:
    """Descriptive 50 Hz load share and cached-site motion; never gait proof."""
    demand(isinstance(frames, list) and len(frames) >= 2, "too few frames")
    normal: dict[str, list[float]] = {"left": [], "right": []}
    tangent: dict[str, list[float]] = {"left": [], "right": []}
    sites: dict[str, list[tuple[float, float, float]]] = {"left": [], "right": []}
    trunk: list[tuple[float, float, float]] = []
    times: list[float] = []
    classes = {"both": 0, "left_only": 0, "right_only": 0, "neither": 0}
    shares = []
    for frame in frames:
        demand(isinstance(frame, dict), "malformed frame")
        times.append(number(frame.get("sim_time_s"), "time"))
        trunk.append(_vector_3(frame.get("trunk_xyz_after_integration_m"), "trunk"))
        contacts = frame.get("contacts_original_solver")
        site_table = frame.get("foot_sites_solver_cache_xyz_m")
        demand(isinstance(contacts, dict) and isinstance(site_table, dict),
               "contact or site table missing")
        for foot in ("left", "right"):
            c = contacts.get(foot)
            demand(isinstance(c, dict), "contact absent")
            n = number(c.get("normal_force_n"), "force", nonnegative=True)
            tan = number(c.get("tangent_force_norm_n"), "tangent", nonnegative=True)
            demand(type(c.get("pair_count")) is int and c["pair_count"] >= 0,
                   "contact count invalid")
            demand(c["pair_count"] > 0 or n == 0, "force without contact pair")
            normal[foot].append(n)
            tangent[foot].append(tan)
            sites[foot].append(_vector_3(site_table.get(foot), "site"))
        left, right = normal["left"][-1], normal["right"][-1]
        l, r = left > LOADED_N, right > LOADED_N
        classes[("both" if l and r else "left_only" if l else
                 "right_only" if r else "neither")] += 1
        demand(left + right > 0, "no total normal force; share undefined")
        shares.append(left / (left + right))
    for a,b in zip(times,times[1:]):
        demand(abs(b-a-SAMPLE_INTERVAL_S) < 1e-5,
               "phase sample gap or clock reset")

    def xy_dist(a: tuple, b: tuple) -> float:
        return math.hypot(b[0]-a[0], b[1]-a[1])

    def foot_stats(foot: str) -> dict:
        positions = sites[foot]
        path = sum(xy_dist(a,b) for a,b in zip(positions,positions[1:]))
        return {
            "normal_mean_n": statistics.fmean(normal[foot]),
            "normal_min_n": min(normal[foot]),
            "normal_max_n": max(normal[foot]),
            "tangent_norm_max_n": max(tangent[foot]),
            "site_cached_world_xy_path_m": path,
            "site_cached_world_xy_net_m": xy_dist(positions[0],positions[-1]),
        }

    return {
        "frames": len(frames),
        "window_sim_start_s": times[0],
        "window_sim_end_s": times[-1],
        "window_sampled_duration_s": times[-1]-times[0],
        "contact_load_0_1n": classes,
        "left_share_mean": statistics.fmean(shares),
        "left_share_min": min(shares),
        "left_share_max": max(shares),
        "left_share_population_sd": statistics.pstdev(shares),
        "left_share_above_half_samples": sum(x > .5 for x in shares),
        "right_share_above_half_samples": sum(x < .5 for x in shares),
        "left_share_crosses_half_between_adjacent_samples": sum(
            (a-.5)*(b-.5) < 0 for a,b in zip(shares,shares[1:])),
        "feet": {name: foot_stats(name) for name in ("left", "right")},
        "trunk_world_xy_path_m": sum(
            xy_dist(a,b) for a,b in zip(trunk,trunk[1:])),
        "trunk_world_xy_net_m": xy_dist(trunk[0],trunk[-1]),
        "trunk_world_delta_x_m": trunk[-1][0]-trunk[0][0],
        "trunk_world_delta_y_m": trunk[-1][1]-trunk[0][1],
    }


def audit_files(solver_tap: Path, solver_analysis: Path,
                walk_comparison: Path) -> dict:
    """Require the exact immutable P0e CI artifact; no online or motor calls."""
    frames = _verified_frames(_read_exact(solver_tap))
    analysis = _strict_json(_read_exact(solver_analysis).decode("utf-8"))
    comparison = _strict_json(_read_exact(walk_comparison).decode("utf-8"))
    demand(isinstance(analysis, dict) and isinstance(comparison, dict),
           "invalid source document")
    windows = _windows(analysis, comparison)
    result: dict = {}
    for phase, (lo, hi) in windows.items():
        subset = [f for f in frames if lo <= f["sim_time_s"] <= hi]
        demand(len(subset) == EXPECTED_WINDOWS[phase],
               "incomplete P0e solver window: " + phase)
        original = analysis.get(phase)
        demand(isinstance(original, dict)
               and original.get("frames") == len(subset),
               "archived solver phase frame count mismatch")
        result[phase] = summarize_window(subset)
        loaded = result[phase]["contact_load_0_1n"]
        demand(loaded["both"] ==
               original.get("both_feet_with_force_gt_0_1n_frames"),
               "double-foot load disagrees with P0e original audit")
        demand(loaded["left_only"] + loaded["right_only"] ==
               original.get("exactly_one_foot_with_force_gt_0_1n_frames"),
               "single-foot count disagrees with P0e original audit")
    return {
        "schema_version": 1,
        "source_run": SOURCE_URL,
        "source_files_sha256": dict(EXPECTED_SHA256),
        "rl_commit": RL_COMMIT,
        "scene_git_blob": SCENE_BLOB,
        "analysis": "offline_read_only_from_archived_P0e_solver_not_P0i",
        "phase_label_source": "P0b_10hz_windows_not_exact_50hz_policy_ID",
        "solver_sample_hz": 50,
        "no_new_motor_commands": True,
        "source_stop_confirmed": True,
        "source_existing_motor_commands": 24,
        "source_final_net_xy_m": comparison["measured_walk_displacement_m"],
        "phase_window_metrics_are_not_final_trial_distance": True,
        "phases": result,
        "left_share_mean_walk_minus_stand": (
            result["walk"]["left_share_mean"] - result["stand"]["left_share_mean"]),
        "observed_unilateral_load_0_1n_during_walk": (
            result["walk"]["contact_load_0_1n"]["left_only"]
            + result["walk"]["contact_load_0_1n"]["right_only"]),
        "signed_horizontal_traction_available": False,
        "cached_site_motion_is_patch_slip": False,
        "gait_validated": False,
        "root_cause_proven": False,
        "physical_robot_tested": False,
        "limitations": (
            "Normal and tangent contact forces are aggregated magnitudes, not signed "
            "horizontal impulse. Cached foot site travel is NOT contact patch slip. "
            "The P0b policy label was sampled at 10 Hz while MuJoCo loads were "
            "sampled at about 50 Hz. This single archived trial was instrumented "
            "and is NOT the P0i A/B run or evidence of a causal explanation."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="P0j: offline-only P0e load transfer")
    p.add_argument("--solver-tap", type=Path, required=True)
    p.add_argument("--solver-analysis", type=Path, required=True)
    p.add_argument("--walk-comparison", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        report = audit_files(args.solver_tap, args.solver_analysis,
                             args.walk_comparison)
        args.output.write_text(json.dumps(
            report, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8")
        print(json.dumps({
            "source_run": report["source_run"],
            "stand_samples": report["phases"]["stand"]["frames"],
            "walk_samples": report["phases"]["walk"]["frames"],
            "walk_left_share_mean": report["phases"]["walk"]["left_share_mean"],
            "walk_both_loaded": report["phases"]["walk"]["contact_load_0_1n"]["both"],
            "unilateral_loaded": report["observed_unilateral_load_0_1n_during_walk"],
            "causal_root_cause_proven": False,
            "gait_validated": False,
            "new_motor_commands": 0,
        }, allow_nan=False, sort_keys=True))
    except (OfflineTraceError, OSError, UnicodeError) as exc:
        print(f"P0j refuses incomplete evidence: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
