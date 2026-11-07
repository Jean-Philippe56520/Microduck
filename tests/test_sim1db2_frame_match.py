"""B2 exact-frame GT: no camera, inference, OEM process or robot required."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.sim1db2_frame_match import B2GTError, match_frame, read_sidecar

FRAME_A = b"\0" * (640 * 360 * 2)
FRAME_B = b"\1" * (640 * 360 * 2)


def row(frame=FRAME_A, *, case="ball", sequence=1, t=0.06):
    positive = case == "ball"
    return {
        "schema": 1, "case": case, "render_seq": sequence,
        "sim_time_s": t, "uyvy_sha256": hashlib.sha256(frame).hexdigest(),
        "width": 640, "height": 360, "rotation_degrees": 90,
        "ball_geom_id": 42 if positive else None,
        "ball_visible_pixels": 100 if positive else 0,
        "ball_bbox_upright_xyxy": [10, 20, 20, 30] if positive else None,
        "qpos_sha256": "d" * 64, "camera_pos_xyz": [0.0, 0.1, 0.2],
        "camera_mat9": [1., 0., 0., 0., 1., 0., 0., 0., 1.],
        "render_ms": 21.0,
    }


class ExactFrameGTTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "sidecar.ndjson"

    def _write(self, *rows):
        self.file.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return self.file

    def test_positive_unique_exact_frame_and_separate_empty_negative(self):
        self._write(row(), row(FRAME_B, sequence=2, t=0.12))
        records = read_sidecar(self.file, case="ball")
        self.assertEqual(match_frame(records, FRAME_B, case="ball")["ball_visible_pixels"], 100)
        self._write(row(case="empty"))
        self.assertEqual(match_frame(read_sidecar(self.file, case="empty"),
                                     FRAME_A, case="empty")["ball_visible_pixels"], 0)

    def test_missing_torn_and_invalid_sidecars_fail_closed(self):
        with self.assertRaises((FileNotFoundError, B2GTError)):
            read_sidecar(self.file, case="ball")
        for invalid in (b"not-json\n", b"{}", b"[]\n", b"\xff\n",
                        (json.dumps(row()) + "  ").encode(),
                        (json.dumps(row()) + "\n\x00").encode()):
            with self.subTest(invalid=invalid[:18]):
                self.file.write_bytes(invalid)
                with self.assertRaises(B2GTError):
                    read_sidecar(self.file, case="ball")

    def test_positive_and_negative_mutations_refused(self):
        cases = (
            ("wrong_case", {"case": "empty"}),
            ("bad_schema", {"schema": True}),
            ("bad_width", {"width": 360}),
            ("bad_rotate", {"rotation_degrees": 0}),
            ("invalid_hash", {"uyvy_sha256": "g" * 64}),
            ("no_mask", {"ball_geom_id": None}),
            ("invalid_box", {"ball_bbox_upright_xyxy": [0, 0, 999, 999]}),
            ("zero_pixels_mispaired", {"ball_visible_pixels": 0}),
            ("huge_pixels", {"ball_visible_pixels": 999999}),
            ("invalid_pose", {"camera_pos_xyz": [0., None, 0.]}),
            ("bad_matrix", {"camera_mat9": [0.] * 8}),
            ("bad_runtime", {"render_ms": -1.0}),
            ("bad_seq", {"render_seq": False}),
        )
        for name, changes in cases:
            with self.subTest(name=name):
                specimen = dict(row(), **changes)
                self._write(specimen)
                with self.assertRaises(B2GTError):
                    read_sidecar(self.file, case="ball")
        for changes in ({"ball_geom_id": 42}, {"ball_visible_pixels": 1},
                        {"ball_bbox_upright_xyxy": [1, 2, 4, 7]}):
            with self.subTest(empty_changes=changes):
                self._write(dict(row(case="empty"), **changes))
                with self.assertRaises(B2GTError):
                    read_sidecar(self.file, case="empty")

    def test_duplicate_hash_nonmonotonic_time_or_seq_refused(self):
        duplicate = row(FRAME_A, sequence=2, t=0.12)
        wrong_time = row(FRAME_B, sequence=2, t=0.01)
        wrong_seq = row(FRAME_B, sequence=1, t=0.12)
        for specimen in (duplicate, wrong_time, wrong_seq):
            with self.subTest(specimen=specimen["render_seq"]):
                self._write(row(), specimen)
                with self.assertRaises(B2GTError):
                    read_sidecar(self.file, case="ball")

    def test_wrong_payload_and_invalid_length_never_match(self):
        self._write(row())
        rows = read_sidecar(self.file, case="ball")
        for pixels in (FRAME_B, b"", b"invalid"):
            with self.subTest(length=len(pixels)):
                with self.assertRaises(B2GTError):
                    match_frame(rows, pixels, case="ball")

    def test_extra_duplicate_keys_bad_numbers_and_symlink_refused(self):
        self.file.write_text(json.dumps(row())[:-1] + ',"schema":1}\n')
        with self.assertRaises(B2GTError):
            read_sidecar(self.file, case="ball")
        self.file.write_text(json.dumps(row())[:-1] + ',"new_field":1}\n')
        with self.assertRaises(B2GTError):
            read_sidecar(self.file, case="ball")
        self.file.write_text(json.dumps(row()).replace('"render_ms": 21.0', '"render_ms": NaN')+"\n")
        with self.assertRaises(B2GTError):
            read_sidecar(self.file, case="ball")
        self._write(row())
        link = Path(self.temp.name) / "link"
        link.symlink_to(self.file)
        with self.assertRaises(B2GTError):
            read_sidecar(link, case="ball")


if __name__ == "__main__":
    unittest.main()
