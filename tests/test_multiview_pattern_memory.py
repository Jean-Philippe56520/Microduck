"""M1-B: false-match, global-budget and multiview fixture regression tests.

All pixels/tones are deterministic artificial arrays. A manually linked
group proves ONLY that synthetic fixture author asserted same source.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import math
import random
import struct
import tempfile
import unittest

from microduck_companion.compact_multimodal_memory import (
    MAX_PATTERNS,CompactPatternMemory, image_fingerprint,
)
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.multiview_pattern_memory import (
    MultiviewLimits,MultiviewPatternMemory,MultiviewEncounter,
)

START=1_780_000_000.


def square(top=3,left=4, *, offset=0) -> bytes:
    frame=[30+offset]*1024
    for y in range(top,top+12):
        for x in range(left,left+12):
            frame[y*32+x]=195+offset
    return bytes(frame)


def random_tiles(seed: int) -> bytes:
    rnd=random.Random(seed)
    data=[rnd.choice((8,90,240)) for _ in range(64)]
    return bytes(data[(y//4)*8+(x//4)]
                 for y in range(32) for x in range(32))


def tone(hz=440,vol=6500) -> bytes:
    values=[round(vol*math.sin(2*math.pi*hz*n/8000))
            for n in range(1024)]
    return struct.pack("<1024h",*values)


class LegacyGlobalLimitFix(unittest.TestCase):
    def test_256_images_then_one_audio_never_grows_to_257(self):
        db=ExperienceMemory()
        try:
            memory=CompactPatternMemory(db)
            for i in range(MAX_PATTERNS):
                memory.observe_image(random_tiles(i),now_wall_epoch_s=START+i)
            self.assertEqual(MAX_PATTERNS,memory.count())
            memory.observe_audio(
                tone(),now_wall_epoch_s=START+MAX_PATTERNS,
            )
            self.assertEqual(MAX_PATTERNS,memory.count())
            counts=dict(db.conn.execute(
                "SELECT modality,COUNT(*) FROM m1a_compact_patterns "
                "GROUP BY modality"
            ).fetchall())
            self.assertEqual(1,counts["audio"])
            self.assertEqual(255,counts["image"])
            self.assertEqual(255*64+16,memory.signature_storage_bytes())
        finally:
            db.close()


class PolicyValidation(unittest.TestCase):
    def test_default_is_configurable_study_not_256_limit(self):
        limits=MultiviewLimits()
        self.assertEqual(4096,limits.max_signatures)
        self.assertEqual(1024,limits.max_groups)
        self.assertEqual(6,limits.max_signatures_per_group)
        self.assertEqual(262144,limits.max_fingerprint_bytes)
        self.assertEqual(4096,limits.max_comparisons)

    def test_invalid_policy_rejected_before_sqlite(self):
        cases=(
            {"max_groups":0},{"max_groups":True},
            {"max_signatures":0},{"max_signatures":1.5},
            {"max_signatures_per_group":0},
            {"max_signatures_per_group":65},
            {"max_signatures_per_group":5,"max_signatures":3},
            {"max_groups":4,"max_signatures":3},
            {"max_fingerprint_bytes":63},
            {"max_fingerprint_bytes":10**10000},
            {"max_comparisons":0},
            {"retention_s":-1},
        )
        for bad in cases:
            with self.subTest(bad=str(bad)[:80]),self.assertRaises(ValueError):
                MultiviewLimits(**bad)
        db=ExperienceMemory()
        self.addCleanup(db.close)
        with self.assertRaises(TypeError):
            MultiviewPatternMemory(db,limits="unbounded")
        with self.assertRaises(TypeError):
            MultiviewPatternMemory(object())


class GroupedMemoryTests(unittest.TestCase):
    def setUp(self):
        self.db=ExperienceMemory()
        self.addCleanup(self.db.close)
        self.store=MultiviewPatternMemory(self.db)

    def test_one_view_ten_encounters_one_group_one_signature(self):
        first=self.store.observe_image(
            square(),now_wall_epoch_s=START,category="object",
            interest=.9,pc_opt_in=True,
        )
        self.assertEqual("new_group_unverified",first.status)
        self.assertTrue(first.pc_review_suggested)
        for i in range(1,10):
            current=self.store.observe_image(
                square(offset=14),now_wall_epoch_s=START+i,
                interest=1.,pc_opt_in=True,
            )
            self.assertEqual("similar_group_unverified",current.status)
            self.assertEqual(first.group_id,current.group_id)
            self.assertFalse(current.pc_review_suggested)
            self.assertEqual(i+1,current.group_sightings)
            self.assertEqual(1,current.exemplar_count)
            self.assertFalse(current.same_physical_source_verified)
        self.assertEqual(1,self.store.stats()["groups"])
        self.assertEqual(1,self.store.stats()["signatures"])
        self.assertEqual(64,self.store.stats()["fingerprint_bytes"])
        self.assertEqual(0,self.db.experience_count())

    def test_different_view_unlinked_stays_separate_until_explicit_fixture_claim(self):
        first=self.store.observe_image(
            square(),now_wall_epoch_s=START,category="object",
        )
        second=self.store.observe_image(
            square(top=16,left=16),
            now_wall_epoch_s=START+1,category="object",
        )
        self.assertNotEqual(first.group_id,second.group_id)
        self.assertEqual("new_group_unverified",second.status)
        self.assertEqual(2,self.store.stats()["groups"])

    def test_same_synthetic_object_multiple_very_different_views_can_be_linked(self):
        first=self.store.observe_image(square(),now_wall_epoch_s=START,
                                       category="object")
        linked=self.store.observe_image(
            square(top=16,left=16),
            now_wall_epoch_s=START+1,category="object",
            group_hint=first.group_id,synthetic_same_source_claim=True,
        )
        self.assertEqual("linked_exemplar_fixture_claim",linked.status)
        self.assertEqual(first.group_id,linked.group_id)
        self.assertEqual(2,linked.group_sightings)
        self.assertEqual(2,linked.exemplar_count)
        self.assertFalse(linked.same_physical_source_verified)
        seen=self.store.observe_image(
            square(top=16,left=16,offset=20),
            now_wall_epoch_s=START+2,category="unknown",
        )
        self.assertEqual("similar_group_unverified",seen.status)
        self.assertEqual(first.group_id,seen.group_id)
        self.assertEqual(3,seen.group_sightings)
        self.assertEqual(2,self.store.stats()["signatures"])
        self.assertEqual(128,self.store.stats()["fingerprint_bytes"])

    def test_two_acoustic_variants_in_one_declared_event_group(self):
        first=self.store.observe_audio(
            tone(440),category="ambient",now_wall_epoch_s=START,
        )
        linked=self.store.observe_audio(
            tone(900),category="ambient",now_wall_epoch_s=START+1,
            group_hint=first.group_id,synthetic_same_source_claim=True,
        )
        self.assertEqual("linked_exemplar_fixture_claim",linked.status)
        self.assertEqual(2,linked.exemplar_count)
        follow=self.store.observe_audio(
            tone(900,vol=9000),category="unknown",
            now_wall_epoch_s=START+2,
        )
        self.assertEqual("similar_group_unverified",follow.status)
        self.assertEqual(first.group_id,follow.group_id)
        self.assertEqual(32,self.store.stats()["fingerprint_bytes"])

    def test_neither_label_nor_text_automatically_identifies_an_individual(self):
        for cat in ("Kitty","Nessquick","Malo","person","speech"):
            with self.subTest(cat=cat),self.assertRaises(ValueError):
                if cat=="speech":
                    self.store.observe_audio(
                        tone(),now_wall_epoch_s=START,category=cat,
                    )
                else:
                    self.store.observe_image(
                        square(),now_wall_epoch_s=START,category=cat,
                    )
        self.assertEqual(0,self.store.stats()["signatures"])

    def test_explicit_group_hint_cannot_cross_modalities_or_conflict_categories(self):
        first=self.store.observe_image(square(),category="dog",
                                       now_wall_epoch_s=START)
        with self.assertRaises(ValueError):
            self.store.observe_audio(
                tone(),now_wall_epoch_s=START+1,
                group_hint=first.group_id,synthetic_same_source_claim=True,
            )
        conflicting=self.store.observe_image(
            square(top=16,left=16),now_wall_epoch_s=START+2,
            category="cat",group_hint=first.group_id,
            synthetic_same_source_claim=True,
        )
        self.assertEqual("ambiguous_unverified",conflicting.status)
        self.assertEqual(1,self.store.stats()["signatures"])
        self.assertEqual(1,self.store.stats()["groups"])

    def test_unknown_validates_explicit_hint_flag_and_invalid_clock(self):
        for kwargs in (
            {"group_hint":1},
            {"synthetic_same_source_claim":True},
            {"group_hint":True,"synthetic_same_source_claim":True},
            {"group_hint":0,"synthetic_same_source_claim":True},
            {"group_hint":1,"synthetic_same_source_claim":1},
            {"pc_opt_in":"yes"},
            {"interest":10**10000},
            {"now_wall_epoch_s":float("nan")},
        ):
            with self.subTest(kwargs=str(kwargs)[:80]),self.assertRaises(ValueError):
                self.store.observe_image(
                    square(),
                    **({"now_wall_epoch_s":START,**kwargs}),
                )
        self.assertEqual(0,self.store.stats()["signatures"])

    def test_conflicting_label_never_upgrades_fixture_to_truth(self):
        first=self.store.observe_audio(
            tone(440),now_wall_epoch_s=START,category="bark",
        )
        conflict=self.store.observe_audio(
            tone(440),now_wall_epoch_s=START+1,category="meow",
        )
        self.assertEqual("ambiguous_unverified",conflict.status)
        stored=self.db.conn.execute(
            "SELECT category,sightings FROM m1b_groups WHERE id=?",
            (first.group_id,),
        ).fetchone()
        self.assertEqual(("bark",1),
                         (stored["category"],stored["sightings"]))

    def test_limit_per_group_replaces_weak_exemplar_not_group(self):
        limits=MultiviewLimits(max_groups=3,max_signatures=4,
                               max_signatures_per_group=2,
                               max_fingerprint_bytes=256)
        m=MultiviewPatternMemory(self.db,limits)
        first=m.observe_image(square(),now_wall_epoch_s=START)
        m.observe_image(square(top=16,left=16),now_wall_epoch_s=START+1,
                        group_hint=first.group_id,synthetic_same_source_claim=True)
        third=m.observe_image(random_tiles(100),now_wall_epoch_s=START+2,
                             group_hint=first.group_id,synthetic_same_source_claim=True)
        self.assertEqual(first.group_id,third.group_id)
        self.assertEqual(3,third.group_sightings)
        self.assertEqual(2,third.exemplar_count)
        self.assertEqual(1,m.stats()["groups"])
        self.assertEqual(2,m.stats()["signatures"])

    def test_group_cap_eviction_is_atomic_and_does_not_orphan(self):
        m=MultiviewPatternMemory(self.db,MultiviewLimits(
            max_groups=2,max_signatures=3,
            max_signatures_per_group=2,max_fingerprint_bytes=192,
        ))
        first=m.observe_image(square(),now_wall_epoch_s=START)
        second=m.observe_image(square(top=16,left=16),now_wall_epoch_s=START+1)
        third=m.observe_image(random_tiles(9),now_wall_epoch_s=START+2)
        self.assertEqual(2,m.stats()["groups"])
        self.assertEqual(2,m.stats()["signatures"])
        self.assertNotEqual(first.group_id,third.group_id)
        self.assertIsNone(self.db.conn.execute(
            "SELECT 1 FROM m1b_groups WHERE id=?",(first.group_id,),
        ).fetchone())
        self.assertEqual(
            0,self.db.conn.execute("""
                SELECT COUNT(*) FROM m1b_signatures s
                LEFT JOIN m1b_groups g ON g.id=s.group_id
                WHERE g.id IS NULL
            """).fetchone()[0],
        )
        self.assertIsNotNone(self.db.conn.execute(
            "SELECT 1 FROM m1b_groups WHERE id=?",(second.group_id,),
        ).fetchone())

    def test_global_feature_bytes_across_image_and_audio_not_row_number(self):
        m=MultiviewPatternMemory(self.db,MultiviewLimits(
            max_groups=4,max_signatures=4,
            max_signatures_per_group=2,
            max_fingerprint_bytes=128,
        ))
        first=m.observe_image(square(),now_wall_epoch_s=START)
        second=m.observe_audio(tone(),now_wall_epoch_s=START+1)
        third=m.observe_image(square(top=16,left=16),now_wall_epoch_s=START+2)
        self.assertEqual(2,m.stats()["signatures"])
        # 64 + 16 + 64 exceeded the 128-byte budget, so the oldest
        # 64-byte image is dropped. Live fields total 16 + 64 = 80 bytes.
        self.assertEqual(80,m.stats()["fingerprint_bytes"])
        self.assertEqual(2,m.stats()["groups"])
        self.assertIsNone(self.db.conn.execute(
            "SELECT 1 FROM m1b_groups WHERE id=?",(first.group_id,),
        ).fetchone())
        self.assertIsNotNone(self.db.conn.execute(
            "SELECT 1 FROM m1b_groups WHERE id=?",(third.group_id,),
        ).fetchone())

    def test_comparison_budget_refuses_untested_familiarity_and_novelty(self):
        m=MultiviewPatternMemory(self.db,MultiviewLimits(
            max_groups=5,max_signatures=5,
            max_signatures_per_group=2,
            max_fingerprint_bytes=320,max_comparisons=1,
        ))
        m.observe_image(square(),now_wall_epoch_s=START)
        m.observe_image(square(top=16,left=16),now_wall_epoch_s=START+1)
        before=m.stats()
        refused=m.observe_image(square(),now_wall_epoch_s=START+2,
                                interest=1.,pc_opt_in=True)
        self.assertEqual("search_budget_exhausted",refused.status)
        self.assertEqual(1,refused.comparisons)
        self.assertIsNone(refused.group_id)
        self.assertFalse(refused.pc_review_suggested)
        self.assertEqual(before,m.stats())

    def test_prune_expired_groups_and_reject_wall_clock_rollback(self):
        m=MultiviewPatternMemory(self.db,MultiviewLimits(
            max_groups=4,max_signatures=4,
            max_signatures_per_group=2,
            max_fingerprint_bytes=256,retention_s=100,
        ))
        first=m.observe_image(square(),now_wall_epoch_s=START)
        with self.assertRaises(ValueError):
            m.observe_audio(tone(),now_wall_epoch_s=START-120)
        self.assertEqual(1,m.stats()["groups"])
        m.prune(now_wall_epoch_s=START+101)
        self.assertEqual(0,m.stats()["groups"])
        nextone=m.observe_image(square(),now_wall_epoch_s=START+102)
        self.assertNotEqual(first.group_id,nextone.group_id)

    def test_m1a_not_automatically_migrated_into_m1b(self):
        legacy=CompactPatternMemory(self.db)
        legacy.observe_image(square(),now_wall_epoch_s=START)
        self.assertEqual(1,legacy.count())
        self.assertEqual(0,self.store.stats()["groups"])

    def test_sqlite_is_shared_across_separate_connection_reopens(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"test-only.sqlite3"
            firstdb=ExperienceMemory(path)
            try:
                firststore=MultiviewPatternMemory(firstdb)
                one=firststore.observe_audio(tone(),now_wall_epoch_s=START)
                firststore.observe_audio(
                    tone(900),now_wall_epoch_s=START+1,
                    group_hint=one.group_id,synthetic_same_source_claim=True,
                )
            finally:
                firstdb.close()
            seconddb=ExperienceMemory(path)
            try:
                again=MultiviewPatternMemory(seconddb)
                result=again.observe_audio(
                    tone(900),now_wall_epoch_s=START+2,
                )
                self.assertEqual(one.group_id,result.group_id)
                self.assertEqual(3,result.group_sightings)
                self.assertEqual(2,result.exemplar_count)
            finally:
                seconddb.close()

    def test_all_safety_claims_remain_false_even_when_repeated(self):
        one=self.store.observe_image(square(),now_wall_epoch_s=START)
        for field,value in (
            ("category_verified",True),
            ("same_physical_source_verified",True),
            ("robot_hardware_validated",True),
            ("real_sensor_reads",1),
            ("network_requests",1),
            ("motor_commands_issued",1),
            ("media_files_stored",1),
        ):
            with self.subTest(field=field),self.assertRaises(ValueError):
                replace(one,**{field:value})


if __name__=="__main__":
    unittest.main()
