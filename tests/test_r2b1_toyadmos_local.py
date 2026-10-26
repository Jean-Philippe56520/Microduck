"""R2-B+1 protocol-only tests: synthetic WAVs are NOT real audio evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import wave

from microduck_companion.r2b1_toyadmos_local import (
    DATASET_DOI, LICENSE, FAMILIES, prepare, main,
)
from microduck_companion.r2b_independent_capture_eval import (
    R2BEvidenceError, _audio_manifest, run_audio_manifest,
)


class DcaseToyPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.corpus = self.base / "unpacked-dcase"
        self.out = self.base / "private-clips"
        self.manifest = self.base / "private-manifest.json"
        for family_idx, (family, _, _) in enumerate(FAMILIES):
            for part_idx, partition in enumerate(("train", "test")):
                folder = self.corpus / "dev_data" / family / partition
                folder.mkdir(parents=True)
                for mid in range(1, 4):
                    filename = folder / f"normal_id_{mid:02d}_00000000.wav"
                    self._wav(
                        filename, value=200 + family_idx * 200
                        + mid * 20 + part_idx)

    @staticmethod
    def _wav(path: Path, *, value: int, channels: int = 1,
             hz: int = 16000, seconds: int = 6):
        with wave.open(str(path), "wb") as out:
            out.setnchannels(channels)
            out.setsampwidth(2)
            out.setframerate(hz)
            out.writeframes(struct.pack("<h", value) * hz * seconds * channels)

    def _prepare(self):
        return prepare(
            self.corpus, self.out, self.manifest,
            reviewed_noncommercial_rights=True,
            reviewed_individual_operations=True)

    def test_original_machine_ids_are_source_separated_and_runner_reused(self):
        result = self._prepare()
        self.assertEqual("preprocessed_not_evaluated", result["status"])
        self.assertEqual(10, result["derived_wav_files"])
        self.assertEqual(LICENSE, result["license"])
        self.assertFalse(result["real_audio_recognition_measured"])
        records = _audio_manifest(self.manifest.read_bytes())
        self.assertEqual(10, len(records))
        self.assertEqual(6, len({x["source_id"] for x in records}))
        self.assertEqual(10, len({x["session_id"] for x in records}))
        self.assertEqual(10, len({x["take_id"] for x in records}))
        self.assertEqual(10, len({x["sha256"] for x in records}))
        split_sources = {}
        for r in records:
            split_sources.setdefault(r["split"], set()).add(r["source_id"])
            sample = self.out / r["file"]
            self.assertTrue(sample.is_file())
            self.assertEqual(hashlib.sha256(sample.read_bytes()).hexdigest(),
                             r["sha256"])
            with wave.open(str(sample), "rb") as src:
                self.assertEqual(16000, src.getnframes())
                self.assertEqual(16000, src.getframerate())
                self.assertEqual(1, src.getnchannels())
        self.assertEqual(
            {"validation": 2, "validation_unknown": 1,
             "test_known": 2, "test_unknown": 1},
            {k: len(v) for k, v in split_sources.items()})
        self.assertEqual(
            6, len(set.union(*(set(x) for x in split_sources.values()))))
        audit = json.loads((self.out / "provenance-local.json").read_text())
        self.assertEqual(DATASET_DOI, audit["dataset"])
        self.assertFalse(audit["distinct_dates_or_capture_sessions_verified"])
        self.assertEqual(10, len(audit["source_files"]))
        report = run_audio_manifest(self.manifest, self.out)
        self.assertEqual(10, report["manifest_entries"])
        self.assertEqual(2, report["candidates"]["legacy"]["test"]["known_queries"])
        self.assertEqual(1, report["candidates"]["legacy"]["test"]["unknown_queries"])
        self.assertEqual("declared_not_authenticated",
                         report["rights_and_source_independence"])
        per_source = report["candidates"]["legacy"]["test"]["by_source_anonymous"]
        self.assertEqual(3, len(per_source))
        self.assertEqual(2, sum(x["enrolled"] for x in per_source))
        self.assertEqual(3, sum(x["queries"] for x in per_source))
        self.assertNotIn("s-car01", json.dumps(per_source))
        self.assertFalse(report["hardware_validated"])
        self.assertEqual(0, report["motor_commands"])

    def test_rights_and_operation_review_required(self):
        for rights, operations in ((False, False), (True, False), (False, True)):
            with self.subTest(rights=rights, operations=operations):
                with self.assertRaisesRegex(R2BEvidenceError, "review"):
                    prepare(
                        self.corpus, self.out, self.manifest,
                        reviewed_noncommercial_rights=rights,
                        reviewed_individual_operations=operations)
                self.assertFalse(self.out.exists())
                self.assertFalse(self.manifest.exists())

    def test_missing_machine_id_aborts_before_output(self):
        missing = (self.corpus / "dev_data" / "ToyCar" / "test" /
                   "normal_id_03_00000000.wav")
        missing.unlink()
        with self.assertRaisesRegex(R2BEvidenceError, "3 distinct"):
            self._prepare()
        self.assertFalse(self.out.exists())
        self.assertFalse(self.manifest.exists())

    def test_original_symlink_or_wrong_audio_format_fails_closed(self):
        target = (self.corpus / "dev_data" / "ToyConveyor" / "train" /
                  "normal_id_02_00000000.wav")
        target.unlink()
        target.symlink_to(self.corpus / "dev_data" / "ToyConveyor" /
                          "train" / "normal_id_01_00000000.wav")
        with self.assertRaisesRegex(R2BEvidenceError, "linked"):
            self._prepare()
        self.assertFalse(self.out.exists())
        target.unlink()
        self._wav(target, value=400, channels=2)
        with self.assertRaisesRegex(R2BEvidenceError, "mono"):
            self._prepare()
        self.assertFalse(self.manifest.exists())

    def test_identical_original_or_cropped_audio_is_not_independence(self):
        ref = (self.corpus / "dev_data" / "ToyCar" / "train" /
               "normal_id_01_00000000.wav")
        other = (self.corpus / "dev_data" / "ToyCar" / "test" /
                 "normal_id_01_00000000.wav")
        other.write_bytes(ref.read_bytes())
        with self.assertRaisesRegex(R2BEvidenceError, "duplicate"):
            self._prepare()
        self.assertFalse(self.out.exists())

    def test_no_writing_to_repo_or_overwriting_private_media(self):
        project = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(R2BEvidenceError, "outside Git"):
            prepare(self.corpus, project / "new-private-clips", self.manifest,
                    reviewed_noncommercial_rights=True,
                    reviewed_individual_operations=True)
        self.manifest.write_text("do-not-overwrite", encoding="utf-8")
        with self.assertRaisesRegex(R2BEvidenceError, "fresh private"):
            self._prepare()
        self.assertEqual("do-not-overwrite", self.manifest.read_text())
        self.assertFalse(self.out.exists())

    def test_cli_requires_explicit_review_and_local_paths(self):
        for args in (
            [], ["--dataset-root", str(self.corpus)],
            ["--dataset-root", str(self.corpus),
             "--audio-root", str(self.out),
             "--audio-manifest", str(self.manifest)],
        ):
            with self.subTest(args=args), self.assertRaises(SystemExit) as cm:
                main(args)
            self.assertEqual(2, cm.exception.code)


if __name__ == "__main__":
    unittest.main()
