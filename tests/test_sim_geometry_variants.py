"""P0g compiled static contact tests; never invoke mj_step."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from microduck_companion.sim_flat_zone import GroundTruthError
from microduck_companion.sim_geometry_variants import (
    VARIANTS, isolated_scene, contact_mask_allows, _compiled_summary,
    compare_variants,
)

SOURCE_SCENE = (
    '<mujoco model="scene">\n'
    '  <include file="robot_groundcontact.xml" />\n'
    '  <worldbody><geom name="floor" size="0 0 .05" type="plane"/></worldbody>\n'
    '  <keyframe><key name="STAND" qpos="dummy"/></keyframe>\n'
    '</mujoco>'
)


class Model:
    nbody, nv, nq, nu, ngeom = 7, 20, 21, 14, 3
    geom_type = [0, 4, 4]
    geom_group = [0, 3, 3]
    geom_contype = [1, 1, 1]
    geom_conaffinity = [1, 1, 1]
    geom_condim = [3, 3, 3]
    geom_priority = [0, 0, 0]
    geom_friction = [[1, .005, .001]] * 3
    geom_solref = [[.02, 1.]] * 3
    geom_solimp = [[.9, .95, .001, .5, 2.]] * 3
    body_mass = [0., .1, .2, .1, .2, .1, .1]


class Data:
    def __init__(self, model):
        self.qpos = [0., 0., .12, 1., 0., 0., 0.] + [0.] * 14
        self.ncon = 2
        self.contact = [
            SimpleNamespace(geom1=0, geom2=1, dist=-.0003),
            SimpleNamespace(geom1=2, geom2=0, dist=-.0004),
        ]


class FakeMJ:
    mjtObj = SimpleNamespace(mjOBJ_GEOM="geom", mjOBJ_KEY="key")
    MjData = Data
    compiled_paths = []
    forwarded = 0

    @staticmethod
    def mj_name2id(model, kind, name):
        if kind == "key":
            return 0 if name == "STAND" else -1
        return {"floor": 0, "left_foot_collision": 1,
                "right_foot_collision": 2}.get(name, -1)

    @staticmethod
    def mj_id2name(model, kind, idx):
        return ("floor", "left_foot_collision", "right_foot_collision")[idx]

    class MjModel:
        @staticmethod
        def from_xml_path(path):
            FakeMJ.compiled_paths.append(Path(path))
            xml = Path(path).read_text()
            if not any(v in xml for v in VARIANTS):
                raise AssertionError("missing pinned geometry include")
            return Model()

    @staticmethod
    def mj_resetDataKeyframe(model, data, key):
        assert key == 0

    @staticmethod
    def mj_forward(model, data):
        FakeMJ.forwarded += 1

    @staticmethod
    def mj_step(model, data):
        raise AssertionError("P0g must never advance physics")


class GeometryVariantTests(unittest.TestCase):
    def test_replaces_one_include_only(self):
        xml = isolated_scene(SOURCE_SCENE, "robot_walk.xml")
        self.assertIn('<include file="robot_walk.xml" />', xml)
        self.assertIn('<geom name="floor"', xml)
        self.assertEqual(1, xml.count('key name="STAND"'))
        self.assertIn('robot_groundcontact.xml', SOURCE_SCENE)
        with self.assertRaises(GroundTruthError):
            isolated_scene(SOURCE_SCENE, "../../bad.xml")
        with self.assertRaises(GroundTruthError):
            isolated_scene(SOURCE_SCENE.replace(
                '<include file="robot_groundcontact.xml" />', ''), "robot_walk.xml")

    def test_commented_out_old_stand_key_is_not_an_active_key(self):
        pinned = SOURCE_SCENE.replace(
            '<keyframe><key name="STAND"',
            '<keyframe><!-- <key name="STAND" qpos="old"/> -->'
            '<key name="STAND"'
        )
        rewritten = isolated_scene(pinned, "robot_allcollisions.xml")
        self.assertIn('include file="robot_allcollisions.xml"', rewritten)
        # XML parsers ignore the commented key; the active key is preserved.
        self.assertEqual(2, rewritten.count('key name="STAND"'))

    def test_floor_mask_is_not_proof_of_true_collision(self):
        self.assertTrue(contact_mask_allows(1, 1, 1, 1))
        self.assertTrue(contact_mask_allows(0, 2, 2, 0))
        self.assertFalse(contact_mask_allows(0, 0, 0, 0))
        self.assertFalse(contact_mask_allows(1, 1, 2, 2))

    def test_static_contact_candidates_not_live_forces(self):
        result = _compiled_summary(Model(), Data(Model()), FakeMJ,
                                   "robot_groundcontact.xml")
        self.assertEqual(2, result["static_contacts_with_floor"])
        self.assertEqual(1, result["static_foot_floor_contact_candidates"]
                         ["left_foot_collision"])
        self.assertEqual(0, result["physical_steps"])
        self.assertFalse(result["original_live_solver_contacts_measured"])
        self.assertEqual(2, result["floor_mask_eligible_geom_count"])

    def test_compares_three_independent_temp_worlds_without_motor_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "src/mjlab_microduck/robot/microduck"
            directory.mkdir(parents=True)
            (directory / "scene.xml").write_text(SOURCE_SCENE)
            (directory / "assets").mkdir()
            for variant in VARIANTS:
                (directory / variant).write_text("<mujoco model='fixture'/>")
            FakeMJ.compiled_paths = []
            FakeMJ.forwarded = 0
            with patch(
                "microduck_companion.sim_geometry_variants.verify_flat_scene"
            ) as provenance:
                result = compare_variants(root, mj=FakeMJ)
                provenance.assert_called_once()
            self.assertEqual(set(VARIANTS), set(result["variants"]))
            self.assertEqual(3, FakeMJ.forwarded)
            self.assertEqual(3, len(FakeMJ.compiled_paths))
            self.assertFalse(any(p.exists() for p in FakeMJ.compiled_paths))
            self.assertEqual(0, result["motor_commands_sent"])
            self.assertEqual(0, result["mj_step_calls"])
            self.assertFalse(result["gait_validated"])
            self.assertEqual("unknown", result["root_cause"])
            self.assertTrue(result["same_stand_pose"])
            self.assertIn('robot_groundcontact.xml',
                          (directory / "scene.xml").read_text())
            for variant in VARIANTS:
                self.assertEqual("<mujoco model='fixture'/>",
                                 (directory / variant).read_text())

    def test_unverified_checkout_fails_before_compiling_model(self):
        with patch(
            "microduck_companion.sim_geometry_variants.verify_flat_scene",
            side_effect=GroundTruthError("changed pinned git"),
        ), self.assertRaisesRegex(GroundTruthError, "changed pinned"):
            compare_variants(Path("/unverified"), mj=FakeMJ)

    def test_invalid_baseline_root_pose_rejected(self):
        wrong = Data(Model())
        wrong.qpos[2] = .08
        with self.assertRaisesRegex(GroundTruthError, "STAND pose"):
            _compiled_summary(Model(), wrong, FakeMJ, "robot_walk.xml")


if __name__ == "__main__":
    unittest.main()
