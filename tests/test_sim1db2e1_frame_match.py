"""SIM-1D/B2-E1: adversarial SHA+pose gate tests, offline fixtures only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.sim1db2e1_frame_match import B2GTError, match_frame, read_sidecar

PAYLOAD_A = bytes(640 * 360 * 2)
PAYLOAD_B = b"\x01" * (640 * 360 * 2)


def row(payload=PAYLOAD_A, *, case="ball", seq=1, t=0.06):
    return {
        "schema": 2, "case": case,
        "scene_xml": "scene_ball.xml" if case == "ball" else "scene.xml",
        "render_seq": seq, "sim_time_s": t,
        "uyvy_sha256": hashlib.sha256(payload).hexdigest(),
        "width": 640, "height": 360, "rotation_degrees": 90,
        "ball_geom_id": 17 if case == "ball" else None,
        "qpos": [0.0, 0.125, 0.0, 1.0],
        "qvel": [0.0, 0.0, 0.0],
        "qpos_sha256": "a" * 64,
        "camera_pos_xyz": [0.1, 0.2, 0.3],
        "camera_mat9": [1., 0., 0., 0., 1., 0., 0., 0., 1.],
        "render_ms": 12.0,
    }


class DeferredFrameGateTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.file = Path(self.d.name) / "pose.ndjson"

    def write(self, *rows):
        self.file.write_text("".join(json.dumps(x) + "\n" for x in rows))
        return self.file

    def test_ball_and_empty_exact_uyvy_matches_are_independent_of_gt(self):
        rows = read_sidecar(self.write(row(), row(PAYLOAD_B, seq=2, t=0.12)),
                            case="ball")
        self.assertEqual(match_frame(rows, PAYLOAD_B, case="ball")["ball_geom_id"], 17)
        rows = read_sidecar(self.write(row(case="empty")), case="empty")
        self.assertIsNone(match_frame(rows, PAYLOAD_A, case="empty")["ball_geom_id"])

    def test_wrong_missing_or_duplicate_payload_fails(self):
        rows = read_sidecar(self.write(row()), case="ball")
        for payload in (PAYLOAD_B, b"", b"invalid"):
            with self.subTest(n=len(payload)), self.assertRaises(B2GTError):
                match_frame(rows, payload, case="ball")
        with self.assertRaises(B2GTError):
            read_sidecar(self.write(row(), row(seq=2, t=0.12)), case="ball")

    def test_non_monotonic_sequence_or_simulation_time_fails(self):
        for specimen in (row(PAYLOAD_B, seq=1, t=0.12),
                         row(PAYLOAD_B, seq=2, t=0.01)):
            with self.subTest(specimen=specimen), self.assertRaises(B2GTError):
                read_sidecar(self.write(row(), specimen), case="ball")

    def test_invalid_schema_and_kinematic_state_are_refused(self):
        mutations = [
            {"schema": True}, {"case": "empty"}, {"scene_xml": "scene.xml"},
            {"render_seq": False}, {"sim_time_s": -1},
            {"width": True}, {"height": 40}, {"rotation_degrees": 0},
            {"uyvy_sha256": "z" * 64}, {"qpos_sha256": "x" * 64},
            {"ball_geom_id": None}, {"qpos": [float("nan")]},
            {"qpos": []}, {"qpos": [0.] * 129}, {"qpos": False},
            {"qvel": [float("inf")]}, {"qvel": []},
            {"camera_pos_xyz": [1, None, 2]},
            {"camera_mat9": [0.] * 8}, {"camera_mat9": [2.] * 9},
            {"render_ms": -1},
        ]
        for change in mutations:
            with self.subTest(change=change), self.assertRaises(B2GTError):
                read_sidecar(self.write(dict(row(), **change)), case="ball")
        for change in ({"ball_geom_id": 12}, {"scene_xml": "scene_ball.xml"}):
            with self.subTest(change=change), self.assertRaises(B2GTError):
                read_sidecar(self.write(dict(row(case="empty"), **change)),
                             case="empty")

    def test_malformed_json_duplicate_fields_torn_file_and_symlink(self):
        examples = [
            b"not-json\n", b"{}\n", b"[]\n", b"\xff\n",
            (json.dumps(row()) + " ").encode(),
            (json.dumps(row())[:-1] + ',"schema":2}\n').encode(),
            (json.dumps(row())[:-1] + ',"surprise":0}\n').encode(),
        ]
        for source in examples:
            with self.subTest(source=source[:20]), self.assertRaises(B2GTError):
                self.file.write_bytes(source)
                read_sidecar(self.file, case="ball")
        self.write(row())
        link = Path(self.d.name) / "sym"
        link.symlink_to(self.file)
        with self.assertRaises(B2GTError):
            read_sidecar(link, case="ball")


if __name__ == "__main__":
    unittest.main()
