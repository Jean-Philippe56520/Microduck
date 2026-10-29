"""MEM-2B: synthetic read-only candidate recall; no physical identity."""
import random
import tempfile
import unittest
from pathlib import Path
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.category_semantics import CategorySemantics
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_learning import PassiveLearning
from microduck_companion.multiview_pattern_memory import MultiviewPatternMemory, MultiviewLimits
from microduck_companion.memory_recall import recall_memory
from microduck_companion.compact_multimodal_memory import image_fingerprint

NOW=1780000000.
def square(y=3,x=4,offset=0):
    data=[30+offset]*1024
    for row in range(y,y+12):
        for col in range(x,x+12):
            data[row*32+col]=195+offset
    return bytes(data)
def unrelated(seed):
    rnd=random.Random(seed)
    tiles=[rnd.choice((8,90,240)) for _ in range(64)]
    return bytes(tiles[(y//4)*8+x//4] for y in range(32) for x in range(32))

class Memory2BTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"one.sqlite3"
        self.db=ExperienceMemory(self.path)
        self.addCleanup(self.db.close)
        PassiveObservationJournal(self.db)
        PassiveLearning(self.db)
        self.sem=CategorySemantics(self.db)
        self.views=MultiviewPatternMemory(self.db)
        self.a=self.views.observe_image(square(),now_wall_epoch_s=NOW,category="object")
        self.views.observe_image(square(16,16),now_wall_epoch_s=NOW+1,
                               category="object",group_hint=self.a.group_id,
                               synthetic_same_source_claim=True)
    def recall(self, image, enabled=True, category="unknown", now=NOW+2, views=None):
        extra=({"gray8":image,"multiview":views or self.views} if enabled else {})
        return recall_memory(self.db,self.sem,category=category,now_wall_epoch_s=now,**extra)
    def test_ablation_known_and_unknown_and_no_writes(self):
        before=self.db.conn.total_changes
        positive=[square(offset=10),square(16,16,offset=11)]
        negative=[unrelated(15),unrelated(16)]
        self.assertTrue(all(self.recall(x,False).multiview_hint is None for x in positive))
        for x in positive:
            r=self.recall(x)
            self.assertEqual("candidate_prior_group_unverified",r.multiview_hint.status)
            self.assertEqual(self.a.group_id,r.multiview_hint.group_id)
            self.assertFalse(r.same_physical_object_verified)
            self.assertFalse(r.multiview_hint.same_physical_source_verified)
            self.assertEqual(0,r.memory_writes)
            self.assertEqual(0,r.motor_commands_issued)
            self.assertEqual(0,r.qwen_requests)
        for x in negative:
            self.assertEqual("no_candidate_unverified",self.recall(x).multiview_hint.status)
        self.assertEqual(before,self.db.conn.total_changes)
    def test_impostor_collision_remains_unverified(self):
        hint=self.recall(square(offset=14)).multiview_hint
        self.assertEqual("candidate_prior_group_unverified",hint.status)
        self.assertEqual(1.0,hint.similarity)
        self.assertFalse(hint.same_physical_source_verified)
    def test_ambiguous_near_tied_groups_abstain(self):
        sig=image_fingerprint(square())
        changed=bytes([sig[0]+1])+sig[1:]
        with self.db.conn:
            cur=self.db.conn.execute("""INSERT INTO m1b_groups
                (modality,category,source,sightings,first_seen_epoch_s,last_seen_epoch_s)
                VALUES ('image','object','synthetic_fixture_claim',1,?,?)""",(NOW,NOW+1))
            self.db.conn.execute("""INSERT INTO m1b_signatures
                (group_id,modality,feature_version,fingerprint,sightings,last_seen_epoch_s)
                VALUES (?,'image',1,?,1,?)""",(cur.lastrowid,changed,NOW+1))
        before=self.db.conn.total_changes
        hint=self.recall(square()).multiview_hint
        self.assertEqual("ambiguous_unverified",hint.status)
        self.assertIsNone(hint.group_id)
        self.assertEqual(before,self.db.conn.total_changes)
    def test_category_conflict_rejects_candidate(self):
        hint=self.recall(square(),category="cat").multiview_hint
        self.assertEqual("ambiguous_unverified",hint.status)
        self.assertIsNone(hint.group_id)
    def test_budget_incomplete_abstains(self):
        limited=MultiviewPatternMemory(self.db,MultiviewLimits(
            max_groups=4,max_signatures=4,max_signatures_per_group=2,
            max_fingerprint_bytes=256,max_comparisons=1))
        before=self.db.conn.total_changes
        hint=self.recall(square(),views=limited).multiview_hint
        self.assertEqual("search_budget_exhausted",hint.status)
        self.assertIsNone(hint.group_id)
        self.assertEqual(before,self.db.conn.total_changes)
    def test_expired_and_future_do_not_match(self):
        for now in (NOW-1,NOW+self.views.limits.retention_s+40):
            hint=self.recall(square(),now=now).multiview_hint
            self.assertEqual("no_candidate_unverified",hint.status)
    def test_reject_invalid_and_wrong_database(self):
        for args in ({"multiview":self.views},{"gray8":square()},
                     {"multiview":object(),"gray8":square()},
                     {"multiview":self.views,"gray8":"private path"}):
            with self.assertRaises((ValueError,TypeError)):
                recall_memory(self.db,self.sem,category="unknown",
                              now_wall_epoch_s=NOW+2,**args)
        for cat in ("person","ball","chair"):
            with self.assertRaises(ValueError):
                self.recall(square(),category=cat)
        with self.assertRaises(ValueError):
            self.views.probe_image(bytes([1])*1024,now_wall_epoch_s=NOW+2)
        other=ExperienceMemory(":memory:")
        try:
            alien=MultiviewPatternMemory(other)
            with self.assertRaises(ValueError):
                self.recall(square(),views=alien)
        finally:
            other.close()
    def test_retracted_hypothesis_is_not_resurrected(self):
        h=self.sem.hypothesize(category="cat",property="texture",value="soft",
                               confidence=.65,now_wall_epoch_s=NOW+1)
        self.assertTrue(self.sem.retract_hypothesis(h,reason="source_retracted"))
        before=self.db.conn.total_changes
        r=self.recall(square(),category="cat")
        self.assertEqual((),r.category_history.property_hypotheses)
        self.assertEqual("ambiguous_unverified",r.multiview_hint.status)
        self.assertEqual(before,self.db.conn.total_changes)
    def test_reopen_persistent_candidates(self):
        self.db.close()
        other=ExperienceMemory(self.path)
        try:
            PassiveObservationJournal(other)
            PassiveLearning(other)
            sem=CategorySemantics(other)
            mv=MultiviewPatternMemory(other)
            before=other.conn.total_changes
            r=recall_memory(other,sem,category="unknown",now_wall_epoch_s=NOW+2,
                            multiview=mv,gray8=square(offset=10))
            self.assertEqual("candidate_prior_group_unverified",r.multiview_hint.status)
            self.assertEqual(before,other.conn.total_changes)
            self.assertFalse(r.same_physical_object_verified)
        finally:
            other.close()

if __name__=="__main__":
    unittest.main()
