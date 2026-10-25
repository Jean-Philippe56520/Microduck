"""P0h: audit the pinned OEM policy slots and their declared training lineage.

Ordinary robotd Mode::Walk defaults to velstand and no standing network.
Official duck-sim overrides those defaults with the legacy alpha pair.
Independent CPU ONNX probes are synthetic; no movement or OEM edit occurs.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys
import tomllib

from .sim_flat_zone import GroundTruthError, RL_COMMIT, verify_body_process
from .sim_policy_contract import (
    OEM_COMMIT, MAX_MODEL_BYTES, EXPECTED_POLICY_SOURCE,
    _sha256_file, _source, independent_probe, inspect_session,
    policy_paths, verify_oem_sources,
)

MODEL_NAMES = {
    "alpha_walk": "alpha_walking.onnx",
    "alpha_stand": "alpha_stand.onnx",
    "velstand": "velstand.onnx",
}
TEST_VELOCITIES_M_S = (0.0, 0.05, 0.06, 0.12)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise GroundTruthError("P0h: " + message)


def match(pattern: str, source: str, name: str) -> re.Match:
    result = re.search(pattern, source, re.M | re.S)
    require(result is not None, "pinned source changed: " + name)
    assert result is not None
    return result


def selection_contract(
    params: str, duck_sim: str, policy: str, control: str,
    obs: str, seeder: str, lineage: str,
) -> dict:
    """Read the source selection and lineage claims; no runtime inference."""
    match(r'Mode::Walk\s*=>\s*\(\s*"velstand\.onnx"\s*,\s*None\s*,',
          params, "default walk and stand paths")
    match(r'walk:\s*path\(&self\.walk,\s*Some\(walk_default\)\)', params,
          "default walk path resolver")
    match(r'stand:\s*path\(&self\.stand,\s*stand\)', params,
          "default standing path resolver")
    match(r'impl Default for PolicyParams\s*\{.*?mode:\s*Mode::Walk,'
          r'.*?walk:\s*None,\s*stand:\s*None,', params,
          "default walk mode")
    require('walk = "$POLICIES/alpha_walking.onnx"' in duck_sim and
            'stand = "$POLICIES/alpha_stand.onnx"' in duck_sim,
            "duck-sim no longer forces the alpha pair")
    require('POLICIES="$STATE/policies/current"' in duck_sim and
            'scripts/seed-policies.sh' in duck_sim,
            "duck-sim policy seeding changed")
    match(r'^POLICY_REPO="[^\n]*pollen-robotics/microduck-policies[^\n]*"$',
          seeder, "policy seeder repo")
    match(r'^POLICY_VERSION="[^\n]*v8[^\n]*"$', seeder,
          "policy seeder version")
    match(r'pub fn twist_magnitude\(&self\)\s*->\s*f64\s*\{\s*'
          r'self\.twist\.iter\(\)\.map\(\|v\| v \* v\)\.sum::<f64>\(\)\.sqrt\(\)',
          obs, "twist norm")
    threshold = float(match(
        r'pub const DEFAULT_STANDING_THRESHOLD:\s*f64\s*=\s*(0\.\d+);',
        policy, "standing threshold",
    ).group(1))
    require(threshold == 0.05, "standing threshold no longer matches P0h")
    match(r'pub fn will_stand\(&self,\s*twist_magnitude:\s*f64\)\s*->\s*bool'
          r'\s*\{\s*self\.stand\.is_some\(\)\s*&&\s*!self\.standing_disabled'
          r'\s*&&\s*twist_magnitude\s*<=\s*self\.standing_threshold',
          policy, "stand selector and disabled flag")
    match(r'let standing\s*=\s*self\.policy\.will_stand'
          r'\(c\.twist_magnitude\(\)\)\s*\|\|\s*'
          r'\(body_active && self\.policy\.has_standing\(\)\);'
          r'\s*if standing\s*\{\s*\(Net::Stand, c, "stand"\.into\(\)\)'
          r'\s*\}\s*else\s*\{\s*\(Net::Walk, c, "walk"\.into\(\)\)',
          control, "controller net selection")

    teacher_walk = match(
        r'^\| walk teacher \| \x60([a-z0-9]+)\x60 @ (\d+) \|[^\n]*'
        r'\x60alpha_walking\.onnx\x60',
        lineage, "walk teacher provenance",
    )
    teacher_stand = match(
        r'^\| stand teacher \| \x60([a-z0-9]+)\x60 @ (\d+) \|[^\n]*'
        r'\x60alpha_stand\.onnx\x60',
        lineage, "stand teacher provenance",
    )
    produced_velstand = match(
        r'Current policy:\s*wandb \x60pollen-robotics/mjlab_microduck/'
        r'([a-z0-9]+)\x60 @ \x60model_(\d+)\.pt\x60'
        r'[^\n]*\x60velstand\.onnx\x60[^\n]*tag \*\*(v\d+)\*\*',
        lineage, "velstand release provenance",
    )
    require(produced_velstand.group(3) == EXPECTED_POLICY_SOURCE[1],
            "lineage document and downloaded version differ")

    return {
        "ordinary_robotd_defaults": {
            "mode": "walk", "walk_slot": MODEL_NAMES["velstand"],
            "stand_slot": None,
        },
        "duck_sim_explicit_slots": {
            "mode": "walk", "walk_slot": MODEL_NAMES["alpha_walk"],
            "stand_slot": MODEL_NAMES["alpha_stand"],
        },
        "standing_threshold_twist_norm": threshold,
        "source_predicted_up_no_body_command": [
            {
                "vx_m_s": vx,
                "ordinary_robotd_model": MODEL_NAMES["velstand"],
                "duck_sim_model": (
                    MODEL_NAMES["alpha_stand"] if vx <= threshold
                    else MODEL_NAMES["alpha_walk"]
                ),
            } for vx in TEST_VELOCITIES_M_S
        ],
        "documented_lineage_not_cryptographic_proof": {
            "alpha_walk": {
                "wandb_run": teacher_walk.group(1),
                "checkpoint": "model_" + teacher_walk.group(2) + ".pt",
            },
            "alpha_stand": {
                "wandb_run": teacher_stand.group(1),
                "checkpoint": "model_" + teacher_stand.group(2) + ".pt",
            },
            "velstand": {
                "wandb_run": produced_velstand.group(1),
                "checkpoint": "model_" + produced_velstand.group(2) + ".pt",
                "hub_tag": produced_velstand.group(3),
            },
        },
        "default_and_simulator_policy_selection_differ": True,
        "not_an_observed_robotd_tick": True,
    }


def read_sources(robot_root: Path, rl_root: Path) -> dict:
    return selection_contract(
        _source(robot_root, "robotd-params/src/lib.rs"),
        _source(robot_root, "scripts/duck-sim"),
        _source(robot_root, "duck-control/src/policy.rs"),
        _source(robot_root, "robotd/src/control.rs"),
        _source(robot_root, "duck-control/src/obs.rs"),
        _source(robot_root, "scripts/seed-policies.sh"),
        _source(rl_root, "docs/velstand_policy.md"),
    )


def verify_installed_models(state_dir: Path) -> tuple[dict[str, Path], dict]:
    """Validate actual seeded files; local .source/manifest are UNSIGNED."""
    alpha, source = policy_paths(state_dir)
    try:
        policy = tomllib.loads((state_dir / "robotd.toml").read_text(
            encoding="utf-8"))["policy"]
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise GroundTruthError("P0h: cannot read simulator policy config") from exc
    require("mode" not in policy, "duck-sim changed the default mode")
    release_dir = alpha["walk"].parent
    require(alpha["stand"].parent == release_dir,
            "the two alpha files do not share a policy release")
    extra = state_dir / "policies" / "current" / MODEL_NAMES["velstand"]
    try:
        extra = extra.resolve(strict=True)
    except OSError as exc:
        raise GroundTruthError("P0h: velstand is not installed") from exc
    require(extra.parent == release_dir and extra.is_file(),
            "velstand file is outside official release")
    require(1000 < extra.stat().st_size <= MAX_MODEL_BYTES,
            "unexpected velstand size")

    manifest_path = state_dir / "policies" / "current" / "manifest.json"
    try:
        require(manifest_path.resolve(strict=True).parent == release_dir,
                "manifest belongs to another policy set")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise GroundTruthError("P0h: official manifest unreadable") from exc
    require(isinstance(manifest, dict) and
            isinstance(manifest.get("policies"), list),
            "manifest is not a policy listing")
    entries = manifest["policies"]
    require(all(isinstance(p, dict) and isinstance(p.get("file"), str)
                for p in entries), "manifest has malformed entries")
    files = [p["file"] for p in entries]
    require(len(set(files)) == len(files), "manifest lists duplicate files")
    require(all(name in files for name in MODEL_NAMES.values()),
            "manifest does not list all compared policies")
    require((source["repo"], source["version"]) == EXPECTED_POLICY_SOURCE,
            "installed policy record is not the pinned v8 release")
    return {
        "alpha_walk": alpha["walk"],
        "alpha_stand": alpha["stand"],
        "velstand": extra,
    }, {
        "source_record": source,
        "manifest_entries": len(files),
        "manifest_lists_all_three": True,
        "unsigned_manifest_and_source_do_not_prove_training_checkpoint": True,
    }


def difference_norm(a: list[float], b: list[float]) -> float:
    require(len(a) == 14 and len(b) == 14, "action vector must be 14D")
    require(all(math.isfinite(v) for v in a + b), "non-finite ONNX output")
    return math.sqrt(sum((x - y)**2 for x, y in zip(a, b)))


def audit_policy_lineage(
    robot_root: Path, rl_root: Path, state_dir: Path, *,
    ort=None, check_process: bool = True,
) -> dict:
    verify_oem_sources(robot_root, rl_root)
    if check_process:
        verify_body_process(state_dir, rl_root, 17801)
    slots = read_sources(robot_root, rl_root)
    paths, claim = verify_installed_models(state_dir)
    if ort is None:
        import onnxruntime as ort

    outputs = {}
    models = {}
    for role, path in paths.items():
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        contract = inspect_session(session)
        observations = {
            "zero_twist": independent_probe(session, contract, 0.0),
            "vx_0_12": independent_probe(session, contract, 0.12),
        }
        outputs[role] = observations
        models[role] = {
            "file": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
            "contract": contract,
            "synthetic_raw_actions": observations,
            "runtime_inference_captured": False,
        }
    return {
        "schema_version": 1,
        "source": "pinned_OEM_offline_CPU_ONNX_comparison",
        "revisions": {"microduck": OEM_COMMIT, "microduck_rl": RL_COMMIT},
        "slot_selection": slots,
        "policy_bundle": claim,
        "models": models,
        "independent_synthetic_comparison": {
            "zero_twist_velstand_vs_alpha_stand_l2":
                difference_norm(outputs["velstand"]["zero_twist"],
                                outputs["alpha_stand"]["zero_twist"]),
            "forward_0_12_velstand_vs_alpha_walk_l2":
                difference_norm(outputs["velstand"]["vx_0_12"],
                                outputs["alpha_walk"]["vx_0_12"]),
            "not_a_gait_quality_comparison": True,
            "normalizers_history_filters_and_physics_not_equivalent": True,
        },
        "motor_commands_sent": 0,
        "changed_manufacturer_source": False,
        "observed_robotd_raw_inputs_or_actions": False,
        "gait_validated": False,
        "root_cause": "unproven",
        "limitations": (
            "duck-sim overrides ordinary robotd's default policy slots, "
            "but this source fact does not explain the 2.295 mm gait result. "
            "Independent CPU ONNX sessions use synthetic zero-history inputs, "
            "not live robotd frames. No joint targets, loads, dynamics, "
            "model provenance signature, physical measurements or movement "
            "outcomes are established here."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P0h passive OEM policy-slot and ONNX lineage audit")
    parser.add_argument("--robot-root", type=Path, required=True)
    parser.add_argument("--rl-root", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = audit_policy_lineage(
            args.robot_root.resolve(strict=True),
            args.rl_root.resolve(strict=True),
            args.state_dir.resolve(strict=True),
        )
        args.output.write_text(
            json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "policy_slot_difference_confirmed": True,
            "walk_default": report["slot_selection"]["ordinary_robotd_defaults"]["walk_slot"],
            "sim_walk": report["slot_selection"]["duck_sim_explicit_slots"]["walk_slot"],
            "sha256": {key: model["sha256"] for key, model in report["models"].items()},
            "motor_commands_sent": 0,
            "gait_validated": False,
            "root_cause": "unproven",
        }, sort_keys=True))
        return 0
    except (GroundTruthError, OSError, ValueError, TypeError, KeyError,
            RuntimeError, ImportError) as exc:
        print("P0h policy audit rejected: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
