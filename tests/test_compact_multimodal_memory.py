"""M1-A tests: synthetic pixel/PCM recognition hints, not animal/voice IDs.

All payloads are generated in RAM, contain NO personal photos or recordings,
never touch the network, OEM sockets, motors, speaker or real Microduck.
"""
from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path
import random
import struct
import tempfile
import unittest

from microduck_companion.compact_multimodal_memory import (
    AMBIGUITY_GAP,
    AUDIO_FEATURES,
    IMAGE_FEATURES,
    MAX_PATTERNS,
    RETENTION_S,
    CompactEncounter,
    CompactPatternMemory,
    audio_fingerprint,
    image_fingerprint,
)
from microduck_companion.episodic_memory import ExperienceMemory

T0 = 1_780_000_000.


def image_square(row: int = 4, col: int = 4, *, offset: int = 0) -> bytes:
    gray = [30 + offset] * (32 * 32)
    for y in range(row, row + 12):
        for x in range(col, col + 12):
            gray[y * 32 + x] = 205 + offset
    return bytes(gray)


def arbitrary_checker(seed: int) -> bytes:
    rnd = random.Random(seed)
    tiles = [rnd.choice((20, 60, 220)) for _ in range(8 * 8)]
    return bytes(tiles[(y // 4) * 8 + (x // 4)]
                 for y in range(32) for x in range(32))


def sound_tone(hz: float = 440., *, amplitude: float = 6000.,
               phase: float = 0., samples: int = 1024) -> bytes:
    ints = [
        round(amplitude * math.sin(2 * math.pi * hz * i / 8000 + phase))
        for i in range(samples)
    ]
    return struct.pack("<" + str(samples) + "h", *ints)


class SignatureTests(unittest.TestCase):
    def test_image_is_exactly_64_compact_bytes_without_raw_pixels(self):
        original = image_square()
        signature = image_fingerprint(original)
        self.assertEqual(1024, len(original))
        self.assertEqual(IMAGE_FEATURES, len(signature))
        self.assertNotEqual(original[:64], signature)
        self.assertEqual(signature, image_fingerprint(image_square(offset=20)))

    def test_image_rejects_uniform_bad_length_and_wrong_type(self):
        for bad in (
            b"", b"\x80" * 1024, b"\x12" * 1023,
            bytearray(image_square()), "test", None,
        ):
            with self.subTest(bad_type=type(bad).__name__,
                              size=len(bad) if hasattr(bad, "__len__") else -1):
                with self.assertRaises(ValueError):
                    image_fingerprint(bad)

    def test_audio_compresses_pcm_into_16_bytes_and_normalizes_amplitude(self):
        a = audio_fingerprint(sound_tone())
        b = audio_fingerprint(sound_tone(amplitude=10000., phase=.4))
        self.assertEqual(AUDIO_FEATURES, len(a))
        self.assertLessEqual(
            sum(abs(x-y) for x,y in zip(a,b)) / (16 * 255.), .07,
        )
        self.assertNotEqual(a, audio_fingerprint(sound_tone(900.)))

    def test_audio_rejects_silence_dc_and_corruption(self):
        for sample in (
            b"", b"\x00" * 2048,
            struct.pack("<1024h", *([2000] * 1024)),
            sound_tone()[:1019],
            sound_tone() + b"\x00" * 8192,
            bytearray(sound_tone()),
        ):
            with self.subTest(length=len(sample)):
                with self.assertRaises(ValueError):
                    audio_fingerprint(sample)
        with self.assertRaises(ValueError):
            audio_fingerprint(sound_tone(), sample_rate_hz=16000)
        with self.assertRaises(ValueError):
            audio_fingerprint(sound_tone(), sample_rate_hz=True)

    def test_audio_two_nearby_amplitudes_do_not_claim_speech_understanding(self):
        self.assertEqual(
            audio_fingerprint(sound_tone(440., amplitude=6500)),
            audio_fingerprint(sound_tone(440., amplitude=6500)),
        )
        self.assertNotEqual(
            audio_fingerprint(sound_tone(440.)),
            audio_fingerprint(sound_tone(850.)),
        )


class SqlitePatternTests(unittest.TestCase):
    def setUp(self):
        self.db = ExperienceMemory()
        self.addCleanup(self.db.close)
        self.memory = CompactPatternMemory(self.db)

    def test_first_unfamiliar_then_nine_returns_without_ten_images(self):
        first = self.memory.observe_image(
            image_square(), now_wall_epoch_s=T0,
            category="object", pc_opt_in=True, interest=.9,
        )
        self.assertEqual("new_pattern_unverified", first.status)
        self.assertEqual(1, first.sightings)
        self.assertTrue(first.pc_review_suggested)
        self.assertFalse(first.category_verified)
        self.assertFalse(first.same_individual_verified)
        self.assertEqual(0, first.raw_media_stored_bytes)
        for i in range(1, 10):
            got = self.memory.observe_image(
                image_square(offset=20),
                now_wall_epoch_s=T0+i,
                pc_opt_in=True, interest=1.,
            )
            self.assertEqual("similar_pattern_unverified", got.status)
            self.assertEqual(first.pattern_id, got.pattern_id)
            self.assertEqual(i+1, got.sightings)
            self.assertFalse(got.pc_review_suggested)
            self.assertGreaterEqual(got.similarity, .94)
        self.assertEqual(1, self.memory.count())
        self.assertEqual(64, self.memory.signature_storage_bytes())
        self.assertEqual(0, self.db.experience_count())

    def test_two_acoustic_encounters_keep_one_16_byte_fingerprint(self):
        a = self.memory.observe_audio(
            sound_tone(), now_wall_epoch_s=T0, category="knock",
        )
        b = self.memory.observe_audio(
            sound_tone(amplitude=8500., phase=.4),
            now_wall_epoch_s=T0+10,
        )
        self.assertEqual("new_pattern_unverified", a.status)
        self.assertEqual("similar_pattern_unverified", b.status)
        self.assertEqual(a.pattern_id, b.pattern_id)
        self.assertEqual(2, b.sightings)
        self.assertEqual(16, self.memory.signature_storage_bytes())
        self.assertEqual(0, b.network_requests)

    def test_distinct_visual_shapes_are_not_forced_into_one_object(self):
        first = self.memory.observe_image(image_square(),
                                           now_wall_epoch_s=T0)
        second = self.memory.observe_image(image_square(row=16,col=16),
                                            now_wall_epoch_s=T0+1)
        self.assertEqual("new_pattern_unverified", second.status)
        self.assertNotEqual(first.pattern_id, second.pattern_id)
        self.assertEqual(2, self.memory.count())

    def test_distinct_synthetic_frequencies_create_separate_sound_patterns(self):
        a = self.memory.observe_audio(sound_tone(440),now_wall_epoch_s=T0)
        b = self.memory.observe_audio(sound_tone(900),now_wall_epoch_s=T0+1)
        self.assertEqual("new_pattern_unverified", b.status)
        self.assertNotEqual(a.pattern_id, b.pattern_id)

    def test_person_faces_and_speech_signatures_are_not_persisted(self):
        with self.assertRaises(ValueError):
            self.memory.observe_image(
                image_square(),category="person",now_wall_epoch_s=T0,
            )
        with self.assertRaises(ValueError):
            self.memory.observe_audio(
                sound_tone(),category="speech",now_wall_epoch_s=T0,
            )
        self.assertEqual(0,self.memory.count())

    def test_conflicting_anonymous_categories_remain_ambiguous(self):
        first = self.memory.observe_image(
            image_square(),category="dog",now_wall_epoch_s=T0,
        )
        second = self.memory.observe_image(
            image_square(),category="cat",now_wall_epoch_s=T0+1,
        )
        self.assertEqual("ambiguous_unverified",second.status)
        self.assertIsNone(second.pattern_id)
        self.assertEqual(0,second.sightings)
        self.assertFalse(second.category_verified)
        self.assertEqual(1,self.memory.count())
        stored=self.db.conn.execute(
            "SELECT category,sightings FROM m1a_compact_patterns",
        ).fetchone()
        self.assertEqual(("dog",1),(stored["category"],stored["sightings"]))

    def test_near_equal_candidates_do_not_merge_guess(self):
        signature = image_fingerprint(image_square())
        shifted = bytes(min(255, x+4) for x in signature)
        with self.db.conn:
            for index,blob in enumerate((signature,shifted)):
                self.db.conn.execute("""
                    INSERT INTO m1a_compact_patterns(
                        modality,category,source,feature_version,fingerprint,
                        sightings,first_seen_epoch_s,last_seen_epoch_s)
                    VALUES ('image','unknown','synthetic_fixture_claim',1,
                            ?,1,?,?)
                """,(blob,T0+index,T0+index))
        ambiguous = self.memory.observe_image(
            image_square(),now_wall_epoch_s=T0+3,
            pc_opt_in=True,interest=.9,
        )
        self.assertEqual("ambiguous_unverified",ambiguous.status)
        self.assertIsNone(ambiguous.pattern_id)
        self.assertTrue(ambiguous.pc_review_suggested)
        self.assertEqual(2,self.memory.count())

    def test_pc_suggestion_is_non_executing_and_requires_opt_in_interest(self):
        inputs=(
            (False,1.,False),
            (True,.69,False),
            (True,.7,True),
        )
        for index,(opt_in,interest,expected) in enumerate(inputs):
            with self.subTest(opt_in=opt_in,interest=interest):
                sample=arbitrary_checker(index+10)
                result=self.memory.observe_image(
                    sample,now_wall_epoch_s=T0+index,
                    pc_opt_in=opt_in,interest=interest,
                )
                self.assertEqual(expected,result.pc_review_suggested)
                self.assertEqual(0,result.network_requests)
                self.assertEqual(0,result.motor_commands_issued)
                self.assertFalse(result.category_verified)

    def test_invalid_categories_claims_and_metadata_are_rejected(self):
        invalid=(
            ("doggo","image"),
            ("Kitty","image"),
            ("Malo","image"),
            ("unknown_label","audio"),
            ("human_voice","audio"),
        )
        for category,kind in invalid:
            with self.subTest(category=category):
                with self.assertRaises(ValueError):
                    if kind=="image":
                        self.memory.observe_image(
                            image_square(),now_wall_epoch_s=T0,
                            category=category,
                        )
                    else:
                        self.memory.observe_audio(
                            sound_tone(),now_wall_epoch_s=T0,
                            category=category,
                        )
        for bad in (float("nan"),float("inf"),-1,True):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.memory.observe_image(image_square(),now_wall_epoch_s=bad)
        for bad in (float("nan"),float("inf"),-1,True,1.01):
            with self.subTest(interest=bad),self.assertRaises(ValueError):
                self.memory.observe_image(
                    image_square(),now_wall_epoch_s=T0,interest=bad,
                )
        with self.assertRaises(ValueError):
            self.memory.observe_image(image_square(),now_wall_epoch_s=T0,
                                      pc_opt_in=1)

    def test_clock_rollback_never_regresses_last_seen_or_forgets(self):
        a=self.memory.observe_image(image_square(),now_wall_epoch_s=T0)
        with self.assertRaises(ValueError):
            self.memory.observe_audio(
                sound_tone(),now_wall_epoch_s=T0-120,
            )
        self.assertEqual(1,self.memory.count())
        b=self.memory.observe_image(image_square(),
                                    now_wall_epoch_s=T0+1)
        self.assertEqual(a.pattern_id,b.pattern_id)
        self.assertEqual(2,b.sightings)

    def test_data_retention_expires_stale_unknowns(self):
        first=self.memory.observe_image(image_square(),now_wall_epoch_s=T0)
        self.memory.prune(now_wall_epoch_s=T0+RETENTION_S+1)
        self.assertEqual(0,self.memory.count())
        next_item=self.memory.observe_image(
            image_square(), now_wall_epoch_s=T0+RETENTION_S+2,
        )
        self.assertEqual("new_pattern_unverified",next_item.status)
        self.assertNotEqual(first.pattern_id,next_item.pattern_id)

    def test_global_cap_bounds_live_rows_and_fingerprint_bytes(self):
        for i in range(MAX_PATTERNS+8):
            self.memory.observe_image(
                arbitrary_checker(i),now_wall_epoch_s=T0+i,
            )
        self.assertEqual(MAX_PATTERNS,self.memory.count())
        self.assertLessEqual(
            self.memory.signature_storage_bytes(),MAX_PATTERNS*64,
        )

    def test_raw_media_never_persisted_and_source_is_only_a_fixture(self):
        frame=image_square()
        sample=sound_tone()
        self.memory.observe_image(frame,now_wall_epoch_s=T0)
        self.memory.observe_audio(sample,now_wall_epoch_s=T0+1)
        rows=self.db.conn.execute(
            "SELECT source,modality,category,fingerprint FROM m1a_compact_patterns",
        ).fetchall()
        self.assertEqual(2,len(rows))
        self.assertEqual({"synthetic_fixture_claim"},
                         {r["source"] for r in rows})
        for row in rows:
            self.assertIn(len(row["fingerprint"]),(16,64))
            self.assertNotIn(row["fingerprint"],(frame,sample))
        self.assertEqual(80,self.memory.signature_storage_bytes())

    def test_database_reopened_via_existing_experience_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"mock.sqlite3"
            one=ExperienceMemory(file)
            try:
                a=CompactPatternMemory(one).observe_audio(
                    sound_tone(),now_wall_epoch_s=T0,
                )
            finally:
                one.close()
            two=ExperienceMemory(file)
            try:
                m=CompactPatternMemory(two)
                b=m.observe_audio(
                    sound_tone(),now_wall_epoch_s=T0+2,
                )
                self.assertEqual(a.pattern_id,b.pattern_id)
                self.assertEqual(2,b.sightings)
                self.assertEqual(1,m.count())
            finally:
                two.close()

    def test_result_flags_cannot_be_promoted_into_hardware_claims(self):
        result=self.memory.observe_audio(
            sound_tone(),now_wall_epoch_s=T0,
        )
        for flags in (
            {"category_verified":True},
            {"same_individual_verified":True},
            {"physical_robot_validated":True},
            {"raw_media_stored_bytes":1},
            {"network_requests":1},
            {"motor_commands_issued":1},
        ):
            with self.subTest(flags=flags),self.assertRaises(ValueError):
                replace(result,**flags)


if __name__ == "__main__":
    unittest.main()
