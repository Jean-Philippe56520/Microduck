"""P0f fail-closed contract audit; only fabricated local data in unit tests."""
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from microduck_companion.sim_flat_zone import GroundTruthError
from microduck_companion.sim_policy_contract import (
    JOINTS_WITH_MOUTH, OBS_WIDTH, ACTION_WIDTH,
    _read_home_runtime, _read_home_training, _tensor_matrix,
    compare_pinned_source_contract, inspect_session, policy_paths,
    audit_policy_contract, verify_oem_sources,
)


class ModelMeta:
    def __init__(self, name, shape, dtype="tensor(float)"):
        self.name = name
        self.shape = shape
        self.type = dtype


class ModelSession:
    def __init__(self, recurrent=False, *, bad_shape=False):
        self._inputs = [ModelMeta("obs", [1, 60 if bad_shape else 61])]
        self._outputs = [ModelMeta("actions", [1, 14])]
        if recurrent:
            self._inputs += [
                ModelMeta("h_in", [1, 1, 64]), ModelMeta("c_in", [1, 1, 64]),
            ]
            self._outputs += [
                ModelMeta("h_out", [1, 1, 64]),
                ModelMeta("c_out", [1, 1, 64]),
            ]

    def get_inputs(self):
        return self._inputs

    def get_outputs(self):
        return self._outputs


class P0fUnitTests(unittest.TestCase):
    def test_onnx_feedforward_and_recurrent_contracts(self):
        self.assertEqual((OBS_WIDTH, ACTION_WIDTH), (61, 14))
        a = inspect_session(ModelSession())
        self.assertFalse(a["recurrent"])
        self.assertEqual("actions", a["action_name"])
        b = inspect_session(ModelSession(recurrent=True))
        self.assertTrue(b["recurrent"])
        self.assertEqual([1, 1, 64], b["state_shape"])

    def test_bad_input_shapes_and_state_types_are_rejected(self):
        with self.assertRaises(GroundTruthError):
            inspect_session(ModelSession(bad_shape=True))
        model = ModelSession(recurrent=True)
        model._inputs[1].shape = [1, 1, 0]
        with self.assertRaises(GroundTruthError):
            inspect_session(model)
        model = ModelSession()
        model._outputs[0].type = "tensor(double)"
        with self.assertRaises(GroundTruthError):
            inspect_session(model)

    def test_home_runtime_parser_preserves_joint_order_and_mouth(self):
        vals = [
            0., -.0873, -.4579, -.0049, .4530, .3491, .3491,
            0., 0., 0., 0., .0873, .4579, .0049, -.4530,
        ]
        text = "pub const DEFAULT_POSITION: [f64; NUM_JOINTS] = [\n"
        for v, name in zip(vals, JOINTS_WITH_MOUTH):
            text += f"    {v}, // {name}\n"
        text += "];\n"
        parsed = _read_home_runtime(text)
        self.assertEqual(list(parsed), list(JOINTS_WITH_MOUTH))
        self.assertAlmostEqual(parsed["left_hip_pitch"], -.4579)
        self.assertAlmostEqual(parsed["right_ankle"], -.4530)
        with self.assertRaises(GroundTruthError):
            _read_home_runtime(text.replace(" // mouth", " // missing_mouth"))

    def test_training_home_regex_and_missing_rule(self):
        rules = [
            (r".*hip_yaw.*", 0.), (r".*left_hip_roll.*", -.0873),
            (r".*right_hip_roll.*", .0873),
            (r".*left_hip_pitch.*", -.4579),
            (r".*right_hip_pitch.*", .4579),
            (r".*left_knee.*", -.0049), (r".*right_knee.*", .0049),
            (r".*left_ankle.*", .4530), (r".*right_ankle.*", -.4530),
            (r".*neck_pitch.*", .3491), (r".*head_pitch.*", .3491),
            (r".*head_yaw.*", 0.), (r".*head_roll.*", 0.),
        ]
        src = 'HOME_FRAME = EntityCfg.InitialStateCfg(\n    joint_pos={\n'
        for pattern, value in rules:
            src += f'        r"{pattern}": {value},\n'
        src += '    },\n    joint_vel={".*": 0.0},\n)\n'
        home = _read_home_training(src)
        self.assertEqual(len(home), 14)
        self.assertEqual(home["left_hip_pitch"], -.4579)
        with self.assertRaises(GroundTruthError):
            _read_home_training(src.replace('r".*right_knee.*"', 'r"does_not_exist"'))

    def test_policy_paths_rejects_missing_wrong_and_changed_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            release = state / "policies" / "releases" / "seed-v8"
            release.mkdir(parents=True)
            (release / ".source").write_text(
                "repo=pollen-robotics/microduck-policies\nversion=v8\n")
            (state / "policies" / "current").symlink_to("releases/seed-v8")
            for name in ("alpha_walking.onnx", "alpha_stand.onnx"):
                (release / name).write_bytes(b"fabricated test data" * 80)
            conf = (state / "robotd.toml")
            conf.write_text(
                f'[policy]\nenabled = true\n'
                f'walk = "{state}/policies/current/alpha_walking.onnx"\n'
                f'stand = "{state}/policies/current/alpha_stand.onnx"\n'
            )
            models, source = policy_paths(state)
            self.assertEqual(source["version"], "v8")
            self.assertTrue(models["walk"].is_file())
            conf.write_text(
                conf.read_text() + "action_scale = 9.0\n"
            )
            with self.assertRaises(GroundTruthError):
                policy_paths(state)
            conf.write_text(conf.read_text().replace("action_scale = 9.0\n", ""))
            conf.write_text(conf.read_text().replace('enabled = true', 'enabled = false'))
            with self.assertRaises(GroundTruthError):
                policy_paths(state)
            conf.write_text(conf.read_text().replace('enabled = false', 'enabled = true'))
            (release / ".source").write_text("repo=other\nversion=v8\n")
            with self.assertRaises(GroundTruthError):
                policy_paths(state)

    def test_official_revision_mismatch_fails_without_a_motor_probe(self):
        with patch("microduck_companion.sim_policy_contract.verify_flat_scene"):
            with patch("microduck_companion.sim_policy_contract.subprocess.run") as call:
                call.return_value = types.SimpleNamespace(stdout="wrong revision\n")
                with self.assertRaises(GroundTruthError):
                    verify_oem_sources(Path("/does-not-exist"), Path("/not-used"))
                # Both read-only Git queries are executed before evaluating
                # the combined revision/dirty-tree safety gate.
                self.assertEqual(2, call.call_count)
                command = call.call_args_list[0].args[0]
                self.assertEqual("rev-parse", command[3])

    def test_audit_never_loads_model_when_provenance_not_verified(self):
        with patch("microduck_companion.sim_policy_contract.verify_oem_sources",
                   side_effect=GroundTruthError("changed source")):
            with patch("microduck_companion.sim_policy_contract.policy_paths") as paths:
                with self.assertRaises(GroundTruthError):
                    audit_policy_contract(
                        Path("/wrong"), Path("/wrong"), Path("/wrong"),
                        check_process=False,
                    )
                paths.assert_not_called()

    def test_incompatible_train_pose_is_not_silent(self):
        # Strictly check source mismatch in the self-contained pose reader.
        src = """HOME_FRAME = EntityCfg.InitialStateCfg(
            joint_pos={r".*hip_yaw.*": 0.0},
            joint_vel={".*": 0.0},
        )"""
        with self.assertRaises(GroundTruthError):
            _read_home_training(src)


if __name__ == "__main__":
    unittest.main()
