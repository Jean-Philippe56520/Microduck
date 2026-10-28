"""Offline Cat-A2b blind-editor core tests; no Tk display or private media."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.cata2_bbox_eval import Box
from microduck_companion.cata2b_blind_review import _read_review
from microduck_companion.cata2b_blind_editor import (
    BlindAnnotationSession, BlindImage, empty_box_confirmation_prompt, main,
)
from microduck_companion.cata2b_private_low import LowDataset, LowSample
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError


class BlindEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "images").mkdir()
        # Provenance, original historical boxes, and class are deliberately
        # present in LowDataset, but cannot leak into BlindImage or JSON.
        self.samples = (
            LowSample(
                "s-0000000000000003", "g-0000000000000003",
                "g-0000000000000203", "test", 80, 120,
                (Box("dog", (1., 2., 50., 60.)),),
                ("full",), "a" * 64,
            ),
            LowSample(
                "s-0000000000000004", "g-0000000000000004",
                "g-0000000000000204", "test", 80, 120,
                (), (), "b" * 64,
            ),
        )
        self.dataset = LowDataset(self.root, (), self.samples, "0" * 64)
        self.editor = BlindAnnotationSession(self.dataset, role="first")

    def sid(self, i=0):
        return self.editor.images[i].sample_id

    def confirmed(self):
        self.editor.confirm_image(self.sid(0), all_targets_reviewed=True)
        self.editor.confirm_image(self.sid(1), all_targets_reviewed=True)

    def export(self):
        return self.editor.export(
            blind_to_model_predictions_declared=True,
            manual_independent_review_declared=True,
        )

    def test_projection_does_not_hold_historical_annotations(self):
        self.assertEqual(2, len(self.editor.images))
        self.assertIsInstance(self.editor.images[0], BlindImage)
        self.assertEqual(
            {"sample_id", "image_sha256", "width", "height"},
            set(vars(self.editor.images[0])),
        )
        self.assertNotIn("ground_truth", vars(self.editor))
        self.assertNotIn("dataset", vars(self.editor))
        self.assertEqual((), self.editor.boxes(self.sid()))
        self.assertNotIn("dog", repr(self.editor.images))
        self.assertEqual(0, self.editor.reviewed_count)

    def test_complete_review_exports_existing_118_schema_without_predictions(self):
        self.editor.add_box(
            self.sid(), category="chair", visibility="partial",
            xyxy=(10, 20, 35, 55),
        )
        self.confirmed()
        path = self.export()
        self.assertTrue(path.parent == self.root / "reviews")
        self.assertRegex(path.name, r"^r-[0-9a-f]{16}\.json$")
        data = json.loads(path.read_text("utf-8"))
        self.assertEqual("first", data["role"])
        self.assertEqual(2, len(data["samples"]))
        self.assertEqual("chair", data["samples"][0]["boxes"][0]["category"])
        self.assertEqual([], data["samples"][1]["boxes"])
        self.assertNotIn("dog", path.read_text("utf-8"))
        self.assertNotIn("person_name", path.read_text("utf-8"))
        self.assertEqual("g-", data["review_session_id"][:2])
        self.assertNotEqual("g-0000000000000003", data["review_session_id"])
        self.assertEqual(data["review_session_id"], _read_review(
            self.dataset, path, "first",
        )[0])
        self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
        self.assertEqual(0o700, stat.S_IMODE(path.parent.stat().st_mode))
        self.assertFalse(self.editor.is_uncertain(self.sid()))

    def test_incomplete_or_untruthful_declarations_cannot_export(self):
        with self.assertRaisesRegex(PermissionError, "declarations"):
            self.editor.export(
                blind_to_model_predictions_declared=False,
                manual_independent_review_declared=True,
            )
        with self.assertRaisesRegex(PermissionError, "declarations"):
            self.editor.export(
                blind_to_model_predictions_declared=True,
                manual_independent_review_declared=False,
            )
        with self.assertRaisesRegex(PhotoBaselineError, "individually"):
            self.export()
        self.editor.confirm_image(self.sid(0), all_targets_reviewed=True)
        with self.assertRaisesRegex(PhotoBaselineError, "individually"):
            self.export()
        self.assertFalse((self.root / "reviews").exists())

    def test_uncertain_image_is_not_a_confirmed_negative_prompt(self):
        title, question = empty_box_confirmation_prompt(True)
        self.assertEqual("Image incertaine", title)
        self.assertIn("INDETERMINEE", question)
        self.assertNotIn("confirmer l'absence de toutes les categories", question)
        title2, question2 = empty_box_confirmation_prompt(False)
        self.assertEqual("Relecture sans cible", title2)
        self.assertIn("confirmer l'absence de toutes les categories", question2)
        with self.assertRaises(PhotoBaselineError):
            empty_box_confirmation_prompt("yes")

    def test_negative_requires_explicit_image_confirmation(self):
        with self.assertRaisesRegex(PhotoBaselineError, "complete"):
            self.editor.confirm_image(self.sid(), all_targets_reviewed=False)
        self.confirmed()
        path = self.export()
        data = json.loads(path.read_text("utf-8"))
        self.assertEqual([[], []], [s["boxes"] for s in data["samples"]])
        self.assertTrue(all(s["all_targets_reviewed"] for s in data["samples"]))

    def test_malformed_bboxes_and_categories_refused(self):
        bad = (
            {"category": "", "visibility": "full", "xyxy": (1, 2, 3, 4)},
            {"category": "chair", "visibility": "", "xyxy": (1, 2, 3, 4)},
            {"category": "shoe", "visibility": "full", "xyxy": (1, 2, 3, 4)},
            {"category": "chair", "visibility": "invalid", "xyxy": (1, 2, 3, 4)},
            {"category": "chair", "visibility": "full", "xyxy": (-1, 2, 3, 4)},
            {"category": "chair", "visibility": "full", "xyxy": (1, 2, 81, 4)},
            {"category": "chair", "visibility": "full", "xyxy": (1, 2, 1, 4)},
            {"category": "chair", "visibility": "full", "xyxy": (1, 2, 3, 120.1)},
            {"category": "chair", "visibility": "full", "xyxy": (1, 2, True, 4)},
            {"category": "chair", "visibility": "full", "xyxy": [1, 2, 3, 4]},
        )
        for opts in bad:
            with self.subTest(opts=opts), self.assertRaises(PhotoBaselineError):
                self.editor.add_box(self.sid(), **opts)
        self.assertEqual((), self.editor.boxes(self.sid()))
        with self.assertRaises(PhotoBaselineError):
            self.editor.add_box("private-id-not-in-test",
                                category="chair", visibility="full",
                                xyxy=(1, 2, 3, 4))

    def test_max_boxes_and_copies_are_safe(self):
        for _ in range(40):
            self.editor.add_box(
                self.sid(), category="cat", visibility="full",
                xyxy=(1, 2, 3, 4),
            )
        with self.assertRaisesRegex(PhotoBaselineError, "limit"):
            self.editor.add_box(self.sid(), category="cat",
                                visibility="full", xyxy=(1, 2, 3, 4))
        box = self.editor.boxes(self.sid())[0]
        box["xyxy"][0] = 99
        self.assertEqual(1, self.editor.boxes(self.sid())[0]["xyxy"][0])
        self.editor.undo_last_box(self.sid())
        self.assertEqual(39, len(self.editor.boxes(self.sid())))

    def test_changing_a_confirmed_image_requires_reconfirmation(self):
        self.confirmed()
        self.assertEqual(2, self.editor.reviewed_count)
        self.editor.add_box(self.sid(), category="cat",
                            visibility="partial", xyxy=(5, 6, 30, 40))
        self.assertEqual(1, self.editor.reviewed_count)
        self.editor.confirm_image(self.sid(), all_targets_reviewed=True)
        self.editor.set_uncertain(self.sid(), True)
        self.assertFalse(self.editor.is_confirmed(self.sid()))
        self.assertTrue(self.editor.is_uncertain(self.sid()))
        self.editor.confirm_image(self.sid(), all_targets_reviewed=True)
        self.editor.undo_last_box(self.sid())
        self.assertFalse(self.editor.is_confirmed(self.sid()))

    def test_uncertainty_remains_uncertain_in_export(self):
        self.editor.set_uncertain(self.sid(), True)
        self.confirmed()
        path = self.export()
        row = json.loads(path.read_text("utf-8"))["samples"][0]
        self.assertTrue(row["uncertain"])
        self.assertTrue(self.editor.is_confirmed(self.sid(0)))
        self.assertFalse(self.editor.is_uncertain(self.sid(1)))

    def test_never_overwrite_export_or_old_review(self):
        self.confirmed()
        p = self.export()
        old = p.read_bytes()
        with self.assertRaisesRegex(PhotoBaselineError, "already exported"):
            self.export()
        with self.assertRaisesRegex(PhotoBaselineError, "already exported"):
            self.editor.undo_last_box(self.sid())
        self.assertEqual(old, p.read_bytes())
        self.assertEqual(1, len(list((self.root / "reviews").glob("*.json"))))

    def test_linked_review_directory_denied(self):
        other = self.root / "other"
        other.mkdir()
        (self.root / "reviews").symlink_to(other, target_is_directory=True)
        self.confirmed()
        with self.assertRaisesRegex(PhotoBaselineError, "linked"):
            self.export()
        self.assertFalse(list(other.iterdir()))

    def test_second_role_is_separate_and_valid(self):
        first = self.editor
        second = BlindAnnotationSession(self.dataset, role="second")
        self.assertNotEqual(first.review_session_id, second.review_session_id)
        for s in second.images:
            second.confirm_image(s.sample_id, all_targets_reviewed=True)
        p = second.export(
            blind_to_model_predictions_declared=True,
            manual_independent_review_declared=True,
        )
        self.assertEqual("second", json.loads(p.read_text("utf-8"))["role"])
        self.assertEqual(second.review_session_id,
                         _read_review(self.dataset, p, "second")[0])
        self.assertFalse(second.role == first.role)

    def test_local_jpeg_integrity_is_rechecked_before_display(self):
        from dataclasses import replace
        from PIL import Image
        buffer = BytesIO()
        Image.new("RGB", (80, 120), (22, 66, 88)).save(
            buffer, format="JPEG",
        )
        image_blob = buffer.getvalue()
        path = self.root / "images" / (self.sid() + ".jpg")
        path.write_bytes(image_blob)
        with_sha = replace(
            self.samples[0], image_sha256=sha256(image_blob).hexdigest(),
        )
        dataset = LowDataset(self.root, (), (with_sha,), "0" * 64)
        editor = BlindAnnotationSession(dataset, role="first")
        self.assertEqual(image_blob, editor.image_bytes(self.sid()))
        path.write_bytes(image_blob + b"mutated")
        with self.assertRaisesRegex(PhotoBaselineError, "changed"):
            editor.image_bytes(self.sid())

    def test_local_image_symlink_is_rejected(self):
        from dataclasses import replace
        from PIL import Image
        buffer = BytesIO()
        Image.new("RGB", (80, 120), (5, 6, 7)).save(
            buffer, format="JPEG",
        )
        image_blob = buffer.getvalue()
        original = self.root / "outside.jpg"
        original.write_bytes(image_blob)
        linked = self.root / "images" / (self.sid() + ".jpg")
        linked.symlink_to(original)
        dataset = LowDataset(
            self.root, (), (
                replace(self.samples[0],
                        image_sha256=sha256(image_blob).hexdigest()),
            ), "0" * 64,
        )
        editor = BlindAnnotationSession(dataset, role="first")
        with self.assertRaisesRegex(PhotoBaselineError, "linked"):
            editor.image_bytes(self.sid())

    def test_existing_private_review_name_is_never_overwritten(self):
        reviews = self.root / "reviews"
        reviews.mkdir(mode=0o700)
        old = reviews / ("r-" + "f" * 16 + ".json")
        old.write_bytes(b"existing private review")
        self.confirmed()
        with patch("microduck_companion.cata2b_blind_editor.secrets.token_hex",
                   return_value="f" * 16):
            with self.assertRaises(FileExistsError):
                self.export()
        self.assertEqual(b"existing private review", old.read_bytes())
        self.assertEqual(1, len(list(reviews.iterdir())))

    def test_no_network_sqlite_ollama_or_motor_path(self):
        self.confirmed()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("sqlite3.connect", side_effect=AssertionError("DB forbidden")):
            path = self.export()
        self.assertTrue(path.is_file())

    def test_main_requires_consent_and_uses_validated_loader(self):
        with patch("sys.stderr"), self.assertRaises(SystemExit) as ctx:
            main(["--manifest", str(self.root / "manifest.json"), "--role", "first"])
        self.assertEqual(2, ctx.exception.code)
        with patch("microduck_companion.cata2b_blind_editor.load_private_low_dataset",
                   return_value=self.dataset) as load, \
             patch("microduck_companion.cata2b_blind_editor.run_gui") as gui:
            self.assertEqual(0, main([
                "--manifest", str(self.root / "manifest.json"),
                "--role", "first", "--approved-private-local-media",
            ]))
            load.assert_called_once()
            gui.assert_called_once()
            self.assertIsInstance(gui.call_args.args[0], BlindAnnotationSession)


if __name__ == "__main__":
    unittest.main()
