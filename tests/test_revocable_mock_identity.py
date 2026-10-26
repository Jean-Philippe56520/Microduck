"""F4-D: local, voluntary, fictional token association and revocation."""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.perception import PerceptionSnapshot
from microduck_companion.revocable_mock_identity import (
    DEFAULT_LIFETIME_S, MAX_ASSOCIATIONS, MAX_PRESENTATION_AGE_S,
    KINDS, MockAssociation, MockOptInContext, MockResolution,
    MockTokenPresentation, RevocableMockAssociations,
)

WALL = 1_780_000_000.
KEY = bytes(range(32,64))
TOKEN = bytes(range(32))
ALIEN_TOKEN = bytes(range(64,96))


def context(**overrides):
    value = dict(
        operator_opt_in=True,
        supervised=True,
        privacy_reviewed=True,
        token_presented_voluntarily=True,
        guardian_approved=False,
        child_assent_declared=False,
    )
    value.update(overrides)
    return MockOptInContext(**value)


def ticket(token=TOKEN, *, seq=1, stamp=WALL):
    return MockTokenPresentation(token,seq,stamp)


class OptInIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"mock-memory.sqlite3"
        self.mem=ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.ids=RevocableMockAssociations(self.mem,key=KEY)

    def enroll(self, *, token=TOKEN, kind="pet_cat", ctx=None, now=WALL,
               duration=DEFAULT_LIFETIME_S):
        return self.ids.enroll(
            token=token,kind=kind,context=ctx if ctx is not None else context(),
            now_wall_epoch_s=now,lifetime_s=duration)

    def present(self, *, token=TOKEN, seq=1, stamp=WALL,
                now=WALL,ctx=None):
        return self.ids.present(
            ticket(token,seq=seq,stamp=stamp),
            context=ctx if ctx is not None else context(),
            now_wall_epoch_s=now)

    def assert_no_hardware(self, result):
        self.assertFalse(result.real_identity_verified)
        self.assertFalse(result.real_guardian_verified)
        self.assertFalse(result.physical_actions_authorized)
        self.assertEqual(0,result.motor_commands_issued)
        self.assertEqual(0,result.speaker_commands_issued)

    def test_empty_database_has_no_known_individuals(self):
        self.assertEqual(0,self.ids.count(now_wall_epoch_s=WALL))
        got=self.present()
        self.assertEqual("unknown",got.status)
        self.assertIsNone(got.association_ref)
        self.assertIsNone(got.kind)
        self.assert_no_hardware(got)

    def test_default_opt_in_is_denied_and_does_not_store(self):
        ans=self.enroll(ctx=MockOptInContext())
        self.assertIsNone(ans)
        self.assertEqual(0,self.ids.count(now_wall_epoch_s=WALL))
        got=self.present(ctx=MockOptInContext())
        self.assertEqual("no_operator_permission",got.status)

    def test_every_operator_guard_necessary_for_enroll(self):
        for kw in (
            {"operator_opt_in":False},
            {"supervised":False},
            {"privacy_reviewed":False},
            {"token_presented_voluntarily":False},
        ):
            with self.subTest(kw=kw):
                self.assertIsNone(self.enroll(ctx=context(**kw)))
                self.assertEqual(0,self.ids.count(now_wall_epoch_s=WALL))

    def test_anonymous_cat_enrollment_is_not_verified_identity(self):
        obj=self.enroll()
        self.assertIsInstance(obj,MockAssociation)
        self.assertEqual("pet_cat",obj.kind)
        self.assertEqual(WALL+DEFAULT_LIFETIME_S,obj.expires_epoch_s)
        self.assertEqual(32,len(obj.association_ref))
        self.assert_no_hardware(obj)
        self.assertFalse(obj.camera_or_voice_used)
        self.assertEqual(1,self.ids.count(now_wall_epoch_s=WALL))
        self.assertEqual(0,self.mem.experience_count())

    def test_explicit_token_handoff_gives_only_mock_pseudonym(self):
        original=self.enroll()
        result=self.present()
        self.assertEqual("mock_token_association_only",result.status)
        self.assertEqual(original.association_ref,result.association_ref)
        self.assertEqual("pet_cat",result.kind)
        self.assertTrue(result.voluntary_fixture_only)
        self.assert_no_hardware(result)
        self.assertEqual(0,self.mem.intent_preference("robot","explore"))

    def test_unknown_token_does_not_guess_person_or_animal(self):
        self.enroll()
        other=self.present(token=ALIEN_TOKEN)
        self.assertEqual("unknown",other.status)
        self.assertIsNone(other.kind)
        self.assertIsNone(other.association_ref)

    def test_replay_same_or_lower_sequence_refused(self):
        self.enroll()
        self.assertEqual("mock_token_association_only",
                         self.present(seq=5).status)
        for seq in (5,4,1):
            with self.subTest(seq=seq):
                got=self.present(seq=seq)
                self.assertEqual("replayed_presentation",got.status)
                self.assertIsNone(got.association_ref)
        self.assertEqual("mock_token_association_only",
                         self.present(seq=6).status)

    def test_stale_and_future_presentations_never_reveal_ref(self):
        original=self.enroll()
        for stamp,now in ((WALL,WALL+MAX_PRESENTATION_AGE_S+.01),
                          (WALL+1,WALL)):
            with self.subTest(stamp=stamp,now=now):
                got=self.present(stamp=stamp,now=now)
                self.assertEqual("stale_or_future",got.status)
                self.assertIsNone(got.association_ref)
        self.assertEqual("mock_token_association_only",
                         self.present().status)
        self.assertEqual(original.association_ref,
                         self.ids.present(
                            ticket(seq=2,stamp=WALL+1),
                            context=context(),
                            now_wall_epoch_s=WALL+1).association_ref)

    def test_same_token_cannot_be_enrolled_twice_or_reclassified(self):
        first=self.enroll(kind="pet_cat")
        self.assertIsNone(self.enroll(kind="pet_dog"))
        self.assertEqual(1,self.ids.count(now_wall_epoch_s=WALL))
        self.assertEqual(first.association_ref,
                         self.present().association_ref)
        self.assertEqual("pet_cat",self.present(seq=2).kind)

    def test_child_requires_explicit_guardian_and_assent(self):
        for kw in (
            {"guardian_approved":False,"child_assent_declared":True},
            {"guardian_approved":True,"child_assent_declared":False},
            {"guardian_approved":False,"child_assent_declared":False},
        ):
            with self.subTest(kw=kw):
                self.assertIsNone(self.enroll(
                    kind="child",ctx=context(**kw)))
        child=self.enroll(
            kind="child",ctx=context(
                guardian_approved=True,child_assent_declared=True))
        self.assertIsNotNone(child)
        self.assertFalse(child.real_guardian_verified)

    def test_child_permission_is_rechecked_on_every_presentation(self):
        child_ctx=context(guardian_approved=True,child_assent_declared=True)
        child=self.enroll(kind="child",ctx=child_ctx)
        self.assertEqual("guardian_or_assent_missing",
                         self.present().status)
        self.assertEqual("guardian_or_assent_missing",
                         self.present(ctx=context(guardian_approved=True)).status)
        answer=self.present(ctx=child_ctx)
        self.assertEqual(child.association_ref,answer.association_ref)
        self.assertFalse(answer.real_guardian_verified)
        self.assertFalse(answer.real_identity_verified)

    def test_child_consent_revocation_blocks_even_valid_token(self):
        child_ctx=context(guardian_approved=True,child_assent_declared=True)
        self.enroll(kind="child",ctx=child_ctx)
        self.assertEqual("mock_token_association_only",
                         self.present(ctx=child_ctx).status)
        no_guardian=self.present(seq=2,stamp=WALL+1,now=WALL+1,
                               ctx=context(child_assent_declared=True))
        self.assertEqual("guardian_or_assent_missing",no_guardian.status)
        self.assertIsNone(no_guardian.association_ref)

    def test_refused_consent_does_not_consume_replay_sequence(self):
        self.enroll()
        self.assertEqual("no_operator_permission",
                         self.present(ctx=context(supervised=False)).status)
        self.assertEqual("mock_token_association_only",
                         self.present().status)

    def test_expiry_is_checked_even_with_valid_fixture_token(self):
        self.enroll(duration=60)
        self.assertEqual("unknown",self.present(
            now=WALL+60,stamp=WALL+60).status)
        self.assertEqual(0,self.ids.count(now_wall_epoch_s=WALL+60))
        self.assertEqual(0,self.ids.prune(now_wall_epoch_s=WALL+60))
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4d_mock_optin_associations").fetchone()[0])

    def test_prune_removes_expired_bindings_and_frees_capacity(self):
        self.enroll(duration=60)
        self.assertEqual(1,self.ids.prune(now_wall_epoch_s=WALL+61))
        self.assertEqual(0,self.ids.count(now_wall_epoch_s=WALL+61))
        self.assertEqual(0,self.ids.prune(now_wall_epoch_s=WALL+61))
        self.assertIsNotNone(self.enroll(
            token=ALIEN_TOKEN,now=WALL+61))

    def test_revocation_requires_both_correct_ref_and_token(self):
        obj=self.enroll()
        self.assertFalse(self.ids.revoke(
            association_ref=obj.association_ref,token=ALIEN_TOKEN,
            context=context()))
        self.assertFalse(self.ids.revoke(
            association_ref="a"*32,token=TOKEN,context=context()))
        self.assertEqual("mock_token_association_only",
                         self.present().status)
        self.assertTrue(self.ids.revoke(
            association_ref=obj.association_ref,token=TOKEN,
            context=context()))
        self.assertEqual("unknown",self.present(seq=2).status)
        self.assertEqual(0,self.ids.count(now_wall_epoch_s=WALL))
        self.assertFalse(self.ids.revoke(
            association_ref=obj.association_ref,token=TOKEN,
            context=context()))

    def test_revocation_does_not_require_child_to_assent_to_deletion(self):
        ctx=context(guardian_approved=True,child_assent_declared=True)
        obj=self.enroll(kind="child",ctx=ctx)
        self.assertTrue(self.ids.revoke(
            association_ref=obj.association_ref,token=TOKEN,
            context=context(token_presented_voluntarily=False)))
        self.assertEqual("unknown",self.present(ctx=ctx).status)

    def test_revoke_refused_without_operator_claim(self):
        obj=self.enroll()
        denied=self.ids.revoke(
            association_ref=obj.association_ref,token=TOKEN,
            context=MockOptInContext())
        self.assertFalse(denied)
        self.assertEqual(1,self.ids.count(now_wall_epoch_s=WALL))

    def test_forget_all_clears_even_child_with_operator_claim(self):
        ch=context(guardian_approved=True,child_assent_declared=True)
        self.enroll(kind="child",ctx=ch)
        self.enroll(token=ALIEN_TOKEN,kind="pet_dog")
        self.assertEqual(0,self.ids.forget_all(
            context=MockOptInContext()))
        self.assertEqual(2,self.ids.count(now_wall_epoch_s=WALL))
        self.assertEqual(2,self.ids.forget_all(
            context=context(token_presented_voluntarily=False)))
        self.assertEqual(0,self.ids.count(now_wall_epoch_s=WALL))
        self.assertEqual("unknown",self.present(ctx=ch).status)

    def test_reenroll_after_revoke_requires_fresh_explicit_opt_in(self):
        first=self.enroll()
        self.assertTrue(self.ids.revoke(
            association_ref=first.association_ref,token=TOKEN,
            context=context()))
        self.assertIsNone(self.enroll(ctx=MockOptInContext()))
        second=self.enroll()
        self.assertNotEqual(first.association_ref,second.association_ref)
        self.assertEqual(1,self.ids.count(now_wall_epoch_s=WALL))

    def test_wrong_key_does_not_match_or_delete_existing_binding(self):
        obj=self.enroll()
        other=RevocableMockAssociations(self.mem,key=bytes(range(96,128)))
        self.assertEqual("unknown",other.present(
            ticket(),context=context(),now_wall_epoch_s=WALL).status)
        self.assertFalse(other.revoke(
            association_ref=obj.association_ref,token=TOKEN,
            context=context()))
        self.assertEqual("mock_token_association_only",
                         self.present().status)

    def test_reopen_same_sqlite_and_key_persists_pseudonym_not_biometrics(self):
        obj=self.enroll(kind="pet_dog")
        first=self.present()
        self.assertEqual(obj.association_ref,first.association_ref)
        self.mem.close()
        mem2=ExperienceMemory(self.path)
        try:
            later=RevocableMockAssociations(mem2,key=KEY)
            ans=later.present(
                ticket(seq=2,stamp=WALL+1),context=context(),
                now_wall_epoch_s=WALL+1)
            self.assertEqual(obj.association_ref,ans.association_ref)
            self.assertEqual("pet_dog",ans.kind)
            self.assert_no_hardware(ans)
        finally:
            mem2.close()

    def test_no_raw_token_key_voice_names_or_locations_persisted(self):
        self.enroll()
        columns={r["name"] for r in self.mem.conn.execute("""
            PRAGMA table_info(f4d_mock_optin_associations)
        """).fetchall()}
        self.assertEqual({
            "association_ref","token_tag","kind","enrolled_epoch_s",
            "expires_epoch_s","last_sequence","last_presented_epoch_s",
            "source",
        },columns)
        stored=self.mem.conn.execute(
            "SELECT token_tag,kind FROM f4d_mock_optin_associations"
        ).fetchone()
        self.assertEqual("pet_cat",stored["kind"])
        self.assertEqual(64,len(stored["token_tag"]))
        self.assertNotEqual(TOKEN.hex(),stored["token_tag"])
        self.assertNotEqual(KEY.hex(),stored["token_tag"])
        self.assertNotIn("face",str(columns))
        self.assertNotIn("voice",str(columns))
        self.assertNotIn("name",str(columns))

    def test_public_fictitious_tokens_are_not_authenticated_sensors(self):
        self.enroll()
        answer=self.present()
        self.assertTrue(answer.voluntary_fixture_only)
        self.assertFalse(answer.real_identity_verified)
        self.assertFalse(answer.physical_actions_authorized)
        self.assertEqual("fictional_voluntary_token_only",answer.source)
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM objects").fetchone()[0])

    def test_no_social_output_even_on_association(self):
        from microduck_companion.mock_social_cues import (
            MockSocialComposer, MockSocialContext)
        from microduck_companion.passive_memory import PassiveObservationJournal
        self.enroll()
        self.assertEqual("mock_token_association_only",
                         self.present().status)
        composer=MockSocialComposer(
            AutonomyBrain(self.mem),PassiveObservationJournal(self.mem))
        self.assertEqual(0,composer.count_proposals())
        self.assertEqual(0,self.mem.experience_count())
        self.assertEqual("halt",AutonomyBrain(self.mem).choose_from_snapshot(
            PerceptionSnapshot("mock",(),100.),now=100.1).intention)

    def test_max_associations_bounded_without_evicting_active_entries(self):
        for i in range(MAX_ASSOCIATIONS):
            token=bytes(((j+i)%256 for j in range(32)))
            item=self.enroll(token=token)
            self.assertIsNotNone(item)
        self.assertEqual(MAX_ASSOCIATIONS,
                         self.ids.count(now_wall_epoch_s=WALL))
        extra=bytes(((j+90)%256 for j in range(32)))
        self.assertIsNone(self.enroll(token=extra))
        self.assertEqual(MAX_ASSOCIATIONS,
                         self.ids.count(now_wall_epoch_s=WALL))

    def test_invalid_key_token_type_or_weak_data_are_rejected(self):
        for bad in (b"",b"a"*32,b"abc",b"0"*31,
                    "any-text-not-a-token",bytearray(TOKEN),True):
            with self.subTest(bad_type=type(bad)),self.assertRaises(ValueError):
                RevocableMockAssociations(self.mem,key=bad)
            with self.assertRaises(ValueError):
                self.enroll(token=bad)
        with self.assertRaises(ValueError):
            ticket(b"0"*32)

    def test_strict_presentation_source_sequence_and_timestamp(self):
        for seq in (True,0,-1,2**63,"1"):
            with self.subTest(seq=seq),self.assertRaises(ValueError):
                ticket(seq=seq)
        for stamp in (True,-1,float("nan"),float("inf")):
            with self.assertRaises(ValueError):
                ticket(stamp=stamp)
        with self.assertRaises(ValueError):
            MockTokenPresentation(TOKEN,1,WALL,source="camera")
        with self.assertRaises(TypeError):
            self.ids.present(
                {"token":TOKEN},context=context(),now_wall_epoch_s=WALL)

    def test_invalid_classes_and_ttl_fail_without_sql_writes(self):
        for kind in ("person","kitten","unknown","","secret","pet_other",1):
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                self.enroll(kind=kind)
        for ttl in (0,59,True,-1,31*24*3600,float("inf"),float("nan"),"8"):
            with self.subTest(ttl=ttl),self.assertRaises(ValueError):
                self.enroll(duration=ttl)
        self.assertEqual({"pet_cat","pet_dog","child","adult"},KINDS)
        self.assertEqual(0,self.ids.count(now_wall_epoch_s=WALL))

    def test_invalid_claim_types_and_refs_are_rejected(self):
        for kw in ({"supervised":1},
                   {"guardian_approved":"true"},
                   {"child_assent_declared":None}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                context(**kw)
        self.enroll()
        for ref in (0,True,"", "A"*32,"g"*32,"x"*33):
            with self.assertRaises(ValueError):
                self.ids.revoke(
                    association_ref=ref,token=TOKEN,context=context())

    def test_resolution_type_forbids_forged_verified_identity_or_motors(self):
        for changes in (
            {"real_identity_verified":True},
            {"real_guardian_verified":True},
            {"motor_commands_issued":1},
            {"speaker_commands_issued":1},
            {"physical_actions_authorized":True},
            {"voluntary_fixture_only":False},
            {"source":"sensor"},
        ):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                MockResolution("unknown",**changes)
        with self.assertRaises(ValueError):
            MockResolution("unknown",association_ref="a"*32,kind="child")
        with self.assertRaises(ValueError):
            MockResolution("mock_token_association_only")

    def test_public_token_never_appears_in_presentation_repr(self):
        private=MockTokenPresentation(TOKEN,1,WALL)
        self.assertNotIn(repr(TOKEN),repr(private))
        self.assertNotIn(TOKEN.hex(),repr(private))
        self.assertIn("MockTokenPresentation",repr(private))

    def test_association_dataclass_rejects_forged_verified_identity(self):
        good=self.enroll()
        for kw in (
            {"real_identity_verified":True},
            {"real_guardian_verified":True},
            {"camera_or_voice_used":True},
            {"physical_actions_authorized":True},
            {"motor_commands_issued":1},
            {"speaker_commands_issued":1},
            {"source":"robot"},
            {"kind":"named-person"},
            {"association_ref":"some-name"},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                fields=dict(association_ref=good.association_ref,
                            kind=good.kind,
                            expires_epoch_s=good.expires_epoch_s)
                fields.update(kw)
                MockAssociation(**fields)

    def test_closed_database_fails_closed(self):
        self.mem.close()
        self.assertEqual("history_unavailable",
                         self.present().status)
        with self.assertRaises(sqlite3.Error):
            self.enroll()
        with self.assertRaises(sqlite3.Error):
            self.ids.count(now_wall_epoch_s=WALL)


if __name__=="__main__":
    unittest.main()
