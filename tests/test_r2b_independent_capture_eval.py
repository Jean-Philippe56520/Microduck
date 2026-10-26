"""R2-B offline protocol tests; intentionally NO public/private media download.

Any PNG/WAV files used here are deterministic generated fixtures. They are
NOT independent physical captures; these tests are not recognition results.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import random
import struct
import tempfile
import unittest
import wave
from unittest.mock import patch

from microduck_companion.r2b_independent_capture_eval import (
    ALL_POSES, COIL20_SOURCE, R2BEvidenceError,
    _audio_manifest, _capture_manifest, _coil_name, _image_samples,
    _predict, _read_wav_take, evaluate_captures, main, run_audio_manifest,
    run_coil20,
)

WAV_HZ = 16000


def fixture_manifest(ext="wav"):
    items = []
    layout = (
        ("validation", "s-valalpha", (("reference", 440), ("query", 441))),
        ("validation", "s-valbravo", (("reference", 900), ("query", 901))),
        ("validation_unknown", "s-valunknown", (("query", 1100),)),
        ("test_known", "s-testalpha", (("reference", 660), ("query", 661))),
        ("test_known", "s-testbravo", (("reference", 1200), ("query", 1201))),
        ("test_unknown", "s-testunknown", (("query", 1450),)),
    )
    for split, source, takes in layout:
        for idx, (role, freq) in enumerate(takes):
            name = f"{source[2:]}-{idx}.{ext}"
            items.append({
                "file": name, "source_id": source,
                "session_id": f"t-{source[2:]}-{idx}",
                "take_id": f"t-{source[2:]}-{idx}",
                "split": split, "role": role,
                "sha256": hashlib.sha256(name.encode()).hexdigest(),
            })
    return {
        "schema_version": 1,
        "rights_basis": "locally_reviewed_license",
        "source_evidence": "independent_takes_reviewed_locally",
        "recordings": items,
    }


def as_json(manifest):
    return json.dumps(manifest, sort_keys=True).encode()


def synthetic_captures(*, learned=False):
    """Invented descriptors used only for test correctness, never scored as real."""
    out = {}
    for obj in range(1, 21):
        rng = random.Random(obj * 11)
        base = bytes(rng.randrange(1, 255) for _ in range(64))
        for pose in ALL_POSES:
            changed = bytes(
                max(0, min(255, b + (1 if pose != 0 and
                           (i + pose) % 17 == 0 else 0)))
                for i, b in enumerate(base))
            record = {"legacy": changed}
            if learned:
                record["learned"] = tuple(
                    1. if i == obj - 1 else 0. for i in range(20))
            out[(obj, pose)] = record
    return out


class R2BCaptureProtocolTests(unittest.TestCase):
    def test_coil_source_shape_and_research_consent(self):
        self.assertIn("cs.columbia.edu", COIL20_SOURCE)
        self.assertEqual("coil-20-proc/obj1__0.png", _coil_name(1, 0))
        for obj, angle in ((0, 0), (21, 0), (1, 72), (True, 0)):
            with self.subTest(obj=obj, angle=angle), self.assertRaises(R2BEvidenceError):
                _coil_name(obj, angle)
        with self.assertRaisesRegex(R2BEvidenceError, "noncommercial"):
            run_coil20(Path("/none.zip"), expected_sha256="a"*64)
        with self.assertRaisesRegex(R2BEvidenceError, "SHA256"):
            _image_samples(Path("/none.zip"), expected_sha256="unknown")
        with self.assertRaises(R2BEvidenceError):
            _image_samples(Path("/none.zip"), expected_sha256="a"*64)

    def test_synthetic_open_set_evaluator_freezes_validation_threshold(self):
        data = evaluate_captures(synthetic_captures(learned=True),
                                 kinds=("legacy", "learned"))
        self.assertEqual(8, data["val_enrolled_sources"])
        self.assertEqual(2, data["val_unknown_sources"])
        self.assertEqual(6, data["test_enrolled_sources"])
        self.assertEqual(4, data["test_unseen_sources"])
        for name in ("legacy", "learned"):
            stats = data["candidates"][name]
            self.assertGreater(stats["validation_negative_pairs"], 1)
            self.assertEqual(48, stats["validation"]["known_queries"])
            self.assertEqual(12, stats["validation"]["unknown_queries"])
            self.assertEqual(36, stats["test"]["known_queries"])
            self.assertEqual(24, stats["test"]["unknown_queries"])
            self.assertEqual(36, stats["test"]["correct_known"])
            self.assertEqual(24, stats["test"]["unknown_rejected"])
            self.assertEqual(0, stats["test"]["cross_object_misidentifications"])
            self.assertEqual(0, stats["test"]["false_known_on_unknown"])
            self.assertTrue(0 <= stats["threshold_frozen_on_validation_only"] <= 1)
        self.assertFalse(data["hardware_validated"])
        self.assertFalse(data["image_or_audio_saved_to_sqlite"])

    def test_false_positives_and_unknown_abstention_counted_separately(self):
        captures = synthetic_captures()
        # Replace one unknown query with a perfect copy of an enrolled source.
        captures[(17, 9)] = {"legacy": captures[(11, 0)]["legacy"]}
        report = evaluate_captures(captures)
        self.assertGreaterEqual(report["candidates"]["legacy"]["test"][
            "false_known_on_unknown"], 1)
        self.assertLess(report["candidates"]["legacy"]["test"][
            "unknown_recall"], 1)

    def test_partial_roster_or_malformed_descriptor_is_rejected(self):
        captures = synthetic_captures()
        del captures[(20, 63)]
        with self.assertRaisesRegex(R2BEvidenceError, "exact COIL20 roster"):
            evaluate_captures(captures)
        with self.assertRaises(R2BEvidenceError):
            evaluate_captures(synthetic_captures(), kinds=("learned",))
        with self.assertRaises(R2BEvidenceError):
            evaluate_captures(synthetic_captures(), kinds=("legacy", "legacy"))
        with self.assertRaises(R2BEvidenceError):
            _predict({}, {"legacy": b" "*64}, kind="legacy", threshold=float("nan"))

    def test_audio_manifest_requires_distinct_sources_and_sessions(self):
        good = fixture_manifest()
        items = _audio_manifest(as_json(good))
        self.assertEqual(10, len(items))
        self.assertEqual(10, len({x["sha256"] for x in items}))
        self.assertEqual(10, len({x["session_id"] for x in items}))
        self.assertEqual(10, len(_capture_manifest(as_json(
            fixture_manifest("png")), media_ext="png")))

        for variant in ("duplicate_take", "duplicate_hash", "duplicate_session",
                        "source_leak", "reference_unknown", "private_text",
                        "wrong_ext", "wrong_rights", "bad_role", "bool_schema"):
            m = json.loads(as_json(good))
            rec = m["recordings"]
            if variant == "duplicate_take":
                rec[1]["take_id"] = rec[0]["take_id"]
            elif variant == "duplicate_hash":
                rec[1]["sha256"] = rec[0]["sha256"]
            elif variant == "duplicate_session":
                rec[1]["session_id"] = rec[0]["session_id"]
            elif variant == "source_leak":
                rec[-1]["source_id"] = rec[0]["source_id"]
            elif variant == "reference_unknown":
                rec[-1]["role"] = "reference"
            elif variant == "private_text":
                rec[0]["transcript"] = "not for GitHub"
            elif variant == "wrong_ext":
                rec[0]["file"] = "test.png"
            elif variant == "wrong_rights":
                m["rights_basis"] = "unknown"
            elif variant == "bad_role":
                rec[0]["role"] = "move_motor"
            elif variant == "bool_schema":
                m["schema_version"] = True
            with self.subTest(variant=variant), self.assertRaises(R2BEvidenceError):
                _audio_manifest(as_json(m))

    def test_path_and_metadata_restrictions(self):
        m = fixture_manifest()
        m["recordings"][0]["file"] = "../private.wav"
        with self.assertRaises(R2BEvidenceError):
            _audio_manifest(as_json(m))
        m = fixture_manifest()
        m["source_evidence"] = "same_clip_with_added_noise"
        with self.assertRaises(R2BEvidenceError):
            _audio_manifest(as_json(m))
        with self.assertRaises(R2BEvidenceError):
            _audio_manifest(b"x"*70000)
        with self.assertRaises(R2BEvidenceError):
            _capture_manifest(as_json(fixture_manifest()), media_ext="mp3")

    def test_real_wav_loader_contract_on_generated_tones_not_recognition(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = fixture_manifest()
            frequency = {
                "valalpha": 440, "valbravo": 900, "valunknown": 1100,
                "testalpha": 660, "testbravo": 1200,
                "testunknown": 1450,
            }
            for record in manifest["recordings"]:
                stem = record["source_id"][2:]
                take = 0 if record["role"] == "reference" else 1
                hz = frequency[stem] + take
                samples = tuple(round(6000 * math.sin(
                    2 * math.pi * hz * i / WAV_HZ))
                    for i in range(WAV_HZ))
                with wave.open(str(root / record["file"]), "wb") as out:
                    out.setnchannels(1)
                    out.setsampwidth(2)
                    out.setframerate(WAV_HZ)
                    out.writeframes(struct.pack("<16000h", *samples))
                record["sha256"] = hashlib.sha256(
                    (root / record["file"]).read_bytes()).hexdigest()
            path = root / "ledger.json"
            path.write_bytes(as_json(manifest))
            report = run_audio_manifest(path, root)
            self.assertEqual(10, report["manifest_entries"])
            self.assertEqual(1, report["candidates"]["legacy"]["test"][
                "unknown_queries"])
            self.assertEqual(2, report["candidates"]["legacy"]["test"][
                "known_queries"])
            self.assertFalse(report["hardware_validated"])
            self.assertFalse(report["raw_audio_committed_or_saved_to_sqlite"])
            self.assertEqual(0, report["motor_commands"])
            record = manifest["recordings"][0]
            with self.assertRaisesRegex(R2BEvidenceError, "checksum"):
                _read_wav_take(root, record["file"], "0"*64)
            bad_file = root / "shadow.wav"
            bad_file.symlink_to(root / record["file"])
            with self.assertRaisesRegex(R2BEvidenceError, "symlink"):
                _read_wav_take(root, "shadow.wav", record["sha256"])
            with patch("microduck_companion.r2b_independent_capture_eval._read_wav_take",
                       side_effect=AssertionError("no reading when manifest invalid")):
                broken = json.loads(path.read_text())
                broken["recordings"][0]["sha256"] = broken["recordings"][1]["sha256"]
                path.write_bytes(as_json(broken))
                with self.assertRaises(R2BEvidenceError):
                    run_audio_manifest(path, root)

    def test_command_line_requires_opt_in_and_all_parameters(self):
        for argv in (
            [],
            ["--audio-manifest", "/bad.json"],
            ["--locally-approved-research", "--coil20-zip", "/bad.zip",
             "--coil20-reviewed-sha256", "a"*64],
            ["--locally-approved-research", "--image-model", "/bad.onnx"],
            ["--locally-approved-research", "--image-manifest", "/bad.json"],
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as ctx:
                main(argv)
            self.assertEqual(2, ctx.exception.code)


if __name__ == "__main__":
    unittest.main()
