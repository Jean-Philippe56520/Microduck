"""P0h: strictly fictitious source and installed-set fixtures; no motor RPC."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from microduck_companion.sim_flat_zone import GroundTruthError
from microduck_companion import sim_policy_lineage as p0h


PARAMS = """
impl Default for PolicyParams {
 fn default() -> Self {
   Self { mode: Mode::Walk, walk: None, stand: None, }
 }
}
let (walk_default, stand, sitstand, ground_pick) = match self.mode {
 Mode::Walk => ("velstand.onnx", None, Some("alpha_sitstand.onnx"), Some("alpha_ground_pick.onnx")),
};
let result = ResolvedPolicy {
 walk: path(&self.walk, Some(walk_default)),
 stand: path(&self.stand, stand),
};
"""
SIM = """
POLICIES="$STATE/policies/current"
sh "$REPO/scripts/seed-policies.sh" "$STATE/policies"
[policy]
walk = "$POLICIES/alpha_walking.onnx"
stand = "$POLICIES/alpha_stand.onnx"
"""
POLICY = """
pub const DEFAULT_STANDING_THRESHOLD: f64 = 0.05;
pub fn will_stand(&self, twist_magnitude: f64) -> bool {
 self.stand.is_some() && !self.standing_disabled
 && twist_magnitude <= self.standing_threshold
}
"""
CTRL = """
let standing = self.policy.will_stand(c.twist_magnitude())
 || (body_active && self.policy.has_standing());
if standing {
 (Net::Stand, c, "stand".into())
} else {
 (Net::Walk, c, "walk".into())
}
"""
OBS = """
pub fn twist_magnitude(&self) -> f64 {
 self.twist.iter().map(|v| v * v).sum::<f64>().sqrt()
}
"""
SEED = 'POLICY_REPO="pollen-robotics/microduck-policies"\nPOLICY_VERSION="v8"\n'
LINEAGE = """
# VelStand
**Current policy: wandb \x60pollen-robotics/mjlab_microduck/0045i2si\x60 @ \x60model_2749.pt\x60** —
\x60velstand.onnx\x60 in Hub \x60pollen-robotics/microduck-policies\x60, tag **v8** (2026-10-12).
| stage | run @ ckpt | code | what it added |
| walk teacher | \x60441tzs6d\x60 @ 3750 | velocity recipe | \x60alpha_walking.onnx\x60 — anchor |
| stand teacher | \x6069u48n8l\x60 @ 9750 | standup env | \x60alpha_stand.onnx\x60 — expert |
"""


def sources(**overrides):
    data = dict(params=PARAMS, duck_sim=SIM, policy=POLICY, control=CTRL,
                obs=OBS, seeder=SEED, lineage=LINEAGE)
    data.update(overrides)
    return p0h.selection_contract(**data)


class SelectionTests(unittest.TestCase):
    def test_source_selection_and_training_claims(self):
        result = sources()
        self.assertEqual("velstand.onnx",
                         result["ordinary_robotd_defaults"]["walk_slot"])
        self.assertIsNone(result["ordinary_robotd_defaults"]["stand_slot"])
        self.assertEqual("alpha_walking.onnx",
                         result["duck_sim_explicit_slots"]["walk_slot"])
        self.assertEqual(
            ["alpha_stand.onnx", "alpha_stand.onnx",
             "alpha_walking.onnx", "alpha_walking.onnx"],
            [x["duck_sim_model"] for x in
             result["source_predicted_up_no_body_command"]],
        )
        lineage = result["documented_lineage_not_cryptographic_proof"]
        self.assertEqual("441tzs6d", lineage["alpha_walk"]["wandb_run"])
        self.assertEqual("69u48n8l", lineage["alpha_stand"]["wandb_run"])
        self.assertEqual("0045i2si", lineage["velstand"]["wandb_run"])
        self.assertEqual("model_2749.pt", lineage["velstand"]["checkpoint"])
        self.assertTrue(result["not_an_observed_robotd_tick"])

    def test_changed_source_and_controller_contracts_fail_closed(self):
        cases = (
            {"params": PARAMS.replace('"velstand.onnx"', '"old.onnx"')},
            {"params": PARAMS.replace("stand: None,", 'stand: Some("old"),')},
            {"duck_sim": SIM.replace("alpha_walking.onnx", "velstand.onnx")},
            {"duck_sim": SIM.replace("alpha_stand.onnx", "none")},
            {"policy": POLICY.replace("0.05;", "0.10;")},
            {"policy": POLICY.replace("!self.standing_disabled", "self.standing_disabled")},
            {"control": CTRL.replace("Net::Walk", "Net::Stand")},
            {"obs": OBS.replace(".sqrt()", ".abs()")},
            {"seeder": SEED.replace("v8", "v7")},
            {"lineage": LINEAGE.replace("tag **v8**", "tag **v7**")},
            {"lineage": LINEAGE.replace("alpha_walking.onnx", "unknown.onnx")},
        )
        for n, change in enumerate(cases):
            with self.subTest(case=n):
                with self.assertRaises(GroundTruthError):
                    sources(**change)


class InstalledSetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        release = self.root / "policies/releases/seed-v8"
        release.mkdir(parents=True)
        (self.root / "policies/current").symlink_to("releases/seed-v8")
        (release / ".source").write_text(
            "repo=pollen-robotics/microduck-policies\nversion=v8\n")
        for name in p0h.MODEL_NAMES.values():
            (release / name).write_bytes(b"example-binary" * 100)
        self.manifest = release / "manifest.json"
        self.manifest.write_text(json.dumps({"policies": [
            {"file": name} for name in p0h.MODEL_NAMES.values()
        ]}))
        self.config = self.root / "robotd.toml"
        self.config.write_text(
            '[policy]\nenabled = true\n'
            + 'walk = "' + str(self.root / "policies/current/alpha_walking.onnx") + '"\n'
            + 'stand = "' + str(self.root / "policies/current/alpha_stand.onnx") + '"\n'
        )

    def test_local_manifest_three_files_and_unsigned_provenance(self):
        paths, claims = p0h.verify_installed_models(self.root)
        self.assertEqual(set(p0h.MODEL_NAMES), set(paths))
        self.assertEqual(3, claims["manifest_entries"])
        self.assertTrue(claims["unsigned_manifest_and_source_do_not_prove_training_checkpoint"])

    def test_missing_velstand_and_missing_manifest_rejected(self):
        model = self.root / "policies/current/velstand.onnx"
        model.unlink()
        with self.assertRaises(GroundTruthError):
            p0h.verify_installed_models(self.root)
        model.write_bytes(b"x" * 1500)
        self.manifest.unlink()
        with self.assertRaises(GroundTruthError):
            p0h.verify_installed_models(self.root)

    def test_malformed_manifest_and_wrong_source_rejected(self):
        original = self.manifest.read_text()
        for bad in ('{"policies":[]}', '{"policies":[{"file":"x"},{"file":"x"}]}',
                    '{"policies":[null]}', '{"invalid":true}'):
            self.manifest.write_text(bad)
            with self.subTest(manifest=bad):
                with self.assertRaises(GroundTruthError):
                    p0h.verify_installed_models(self.root)
        self.manifest.write_text(original)
        (self.root / "policies/current/.source").write_text(
            "repo=other\nversion=v8\n")
        with self.assertRaises(GroundTruthError):
            p0h.verify_installed_models(self.root)

    def test_wrong_mode_rejected_even_with_correct_model_files(self):
        self.config.write_text(self.config.read_text() + 'mode = "roller"\n')
        with self.assertRaises(GroundTruthError):
            p0h.verify_installed_models(self.root)


class AuditTests(unittest.TestCase):
    def test_revision_guard_precedes_model_loading(self):
        with patch.object(p0h, "verify_oem_sources",
                          side_effect=GroundTruthError("wrong revision")):
            with patch.object(p0h, "verify_installed_models") as files:
                with self.assertRaises(GroundTruthError):
                    p0h.audit_policy_lineage(
                        Path("/invalid"), Path("/invalid"), Path("/invalid"),
                        check_process=False)
                files.assert_not_called()

    def test_action_vector_comparison_rejects_nonfinite(self):
        self.assertEqual(0.0, p0h.difference_norm([0.] * 14, [0.] * 14))
        self.assertAlmostEqual(1.0, p0h.difference_norm(
            [0.] * 14, [.5] * 4 + [0.] * 10))
        for a, b in (([float("nan")] + [0.] * 13, [0.] * 14),
                     ([0.] * 14, [float("inf")] + [0.] * 13),
                     ([0.] * 13, [0.] * 14)):
            with self.assertRaises(GroundTruthError):
                p0h.difference_norm(a, b)

    def test_report_has_distinct_models_and_no_causality_or_motor(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = {}
            for role, name in p0h.MODEL_NAMES.items():
                path = root / name
                path.write_bytes(("test-model-" + role).encode() * 250)
                paths[role] = path
            class Meta:
                def __init__(self, name, shape):
                    self.name, self.shape, self.type = name, shape, "tensor(float)"
            class Session:
                def __init__(self, path):
                    self.path = Path(path)
                def get_inputs(self):
                    return [Meta("obs", [1, 61])]
                def get_outputs(self):
                    return [Meta("actions", [1, 14])]
            ort = types.SimpleNamespace(
                InferenceSession=lambda p, providers: Session(p))
            def probe(session, contract, vx):
                offset = {"alpha_walking.onnx": .1,
                          "alpha_stand.onnx": .2,
                          "velstand.onnx": .3}[session.path.name]
                return [offset + vx] * 14
            with patch.object(p0h, "verify_oem_sources"):
                with patch.object(p0h, "read_sources", return_value=sources()):
                    with patch.object(p0h, "verify_installed_models",
                                      return_value=(paths, {"fixture": True})):
                        with patch.object(p0h, "independent_probe", side_effect=probe):
                            report = p0h.audit_policy_lineage(
                                root, root, root, ort=ort, check_process=False)
            self.assertEqual(3, len(report["models"]))
            self.assertTrue(all(len(v["sha256"]) == 64
                                for v in report["models"].values()))
            self.assertGreater(
                report["independent_synthetic_comparison"]
                      ["zero_twist_velstand_vs_alpha_stand_l2"], 0)
            self.assertGreater(
                report["independent_synthetic_comparison"]
                      ["forward_0_12_velstand_vs_alpha_walk_l2"], 0)
            self.assertEqual(0, report["motor_commands_sent"])
            self.assertEqual("unproven", report["root_cause"])
            self.assertFalse(report["gait_validated"])
            self.assertFalse(report["observed_robotd_raw_inputs_or_actions"])


if __name__ == "__main__":
    unittest.main()
