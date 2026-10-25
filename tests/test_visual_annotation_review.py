"""F3-E: only fictional reviewer votes, no images or legal sign-off."""
from __future__ import annotations
import json
import unittest
from microduck_companion.visual_annotation_review import (
    AnnotationReviewError, REVIEW_KIND, REVIEW_SCHEMA,
    MAX_REVIEW_BYTES, catalog_labels, empty_review_payload,
    summarize_catalog_reviews,
)


def vote(sample: str, reviewer: int, label="cat", *,
         seen=True, cc0=True, own=True) -> dict:
    return {
        "sample_id": sample,
        "reviewer_id": f"r-{reviewer:016x}",
        "visual_label": label,
        "image_review_claimed": seen,
        "cc0_page_claim_checked": cc0,
        "own_work_page_claim_checked": own,
    }


def bundle(records: list[dict]) -> bytes:
    return json.dumps({
        "schema_version":REVIEW_SCHEMA,"kind":REVIEW_KIND,
        "votes":records,
    },sort_keys=True).encode()


def counts(raw: bytes) -> dict:
    return dict(summarize_catalog_reviews(raw).counts)


class ReviewLedgerTests(unittest.TestCase):
    def setUp(self):
        self.catalog=catalog_labels()
        self.sid=next(iter(self.catalog))
        self.assertEqual("cat",self.catalog[self.sid])

    def test_all_48_real_public_sources_are_unreviewed_by_default(self):
        report=summarize_catalog_reviews(empty_review_payload())
        self.assertEqual(48,report.catalog_entries)
        self.assertEqual(0,report.declared_votes)
        self.assertEqual(48,dict(report.counts)["missing"])
        self.assertEqual(0,report.training_authorizations_granted)
        self.assertFalse(report.labels_independently_verified)
        self.assertFalse(report.licenses_legally_verified)
        self.assertFalse(report.identities_independently_verified)
        self.assertEqual(0,report.images_opened)
        self.assertEqual(0,report.motor_commands_issued)

    def test_ids_are_opaque_and_unique(self):
        self.assertEqual(48,len(self.catalog))
        self.assertTrue(all(s.startswith("s-") and len(s)==18
                            for s in self.catalog))
        self.assertTrue(all(s in ("cat","dog","unknown")
                            for s in self.catalog.values()))

    def test_only_one_vote_is_pending_second_reviewer(self):
        result=counts(bundle([vote(self.sid,1)]))
        self.assertEqual(1,result["needs_second_attestation"])
        self.assertEqual(47,result["missing"])

    def test_two_matching_fictional_votes_cannot_certify_rights(self):
        result=summarize_catalog_reviews(bundle([
            vote(self.sid,1),vote(self.sid,2)]))
        self.assertEqual(1,dict(result.counts)["attestation_consensus_only"])
        self.assertEqual(47,dict(result.counts)["missing"])
        self.assertEqual(2,result.declared_votes)
        self.assertEqual(0,result.training_authorizations_granted)
        self.assertFalse(result.labels_independently_verified)
        self.assertFalse(result.licenses_legally_verified)

    def test_disagreement_between_reviewers_is_not_silenced(self):
        r=counts(bundle([vote(self.sid,1),vote(self.sid,2,"dog")]))
        self.assertEqual(1,r["label_disagreement"])
        self.assertEqual(0,r["attestation_consensus_only"])

    def test_agreement_against_public_caption_requires_relabel_review(self):
        r=counts(bundle([vote(self.sid,1,"dog"),vote(self.sid,2,"dog")]))
        self.assertEqual(1,r["label_disagreement"])

    def test_missing_license_or_image_claim_holds_review(self):
        for key in ("seen","cc0","own"):
            kwargs={key:False}
            with self.subTest(key=key):
                r=counts(bundle([vote(self.sid,1,**kwargs),
                                 vote(self.sid,2)]))
                self.assertEqual(1,r["rights_claim_incomplete"])

    def test_same_reviewer_twice_is_rejected(self):
        with self.assertRaisesRegex(AnnotationReviewError,"twice"):
            summarize_catalog_reviews(bundle([
                vote(self.sid,1),vote(self.sid,1)]))

    def test_unknown_sample_or_plaintext_reviewer_identity_rejected(self):
        tests=[
            vote("s-"+"0"*16,1),
            dict(vote(self.sid,1),reviewer_id="Alice"),
            dict(vote(self.sid,1),sample_id="s-cat-filename"),
        ]
        for item in tests:
            with self.subTest(item=item),self.assertRaises(AnnotationReviewError):
                summarize_catalog_reviews(bundle([item]))

    def test_no_uncontrolled_url_media_or_personal_fields(self):
        for field in ("url","photo_path","raw_bytes","private_name",
                      "consent_form","frame","notes"):
            with self.subTest(field=field):
                row=vote(self.sid,1)
                row[field]="data"
                with self.assertRaises(AnnotationReviewError):
                    summarize_catalog_reviews(bundle([row]))

    def test_bools_cannot_be_numbers_and_categories_are_fixed(self):
        for field, bad in (
            ("image_review_claimed",1),
            ("cc0_page_claim_checked","yes"),
            ("own_work_page_claim_checked",0),
            ("visual_label","person_identity"),
        ):
            row=vote(self.sid,1)
            row[field]=bad
            with self.subTest(field=field),self.assertRaises(AnnotationReviewError):
                summarize_catalog_reviews(bundle([row]))

    def test_duplicate_json_keys_and_invalid_version_fail_closed(self):
        payloads=(
            b'{"schema_version":1,"schema_version":1,"kind":"x","votes":[]}',
            b'{"schema_version":NaN,"kind":"x","votes":[]}',
            b'{"schema_version":2,"kind":"x","votes":[]}',
            b'{"schema_version":1,"kind":"wrong","votes":[]}',
            b'[]',
            b'{"schema_version":true,"kind":"x","votes":[]}',
            b'not json',
            b"",
        )
        for data in payloads:
            with self.subTest(data=data[:32]),self.assertRaises(AnnotationReviewError):
                summarize_catalog_reviews(data)

    def test_binary_upload_and_large_payload_rejected(self):
        for data in (b"\xff",b"x"*(MAX_REVIEW_BYTES+1)):
            with self.assertRaises(AnnotationReviewError):
                summarize_catalog_reviews(data)
        with self.assertRaises(AnnotationReviewError):
            summarize_catalog_reviews("not bytes")

    def test_all_public_catalog_consensus_still_not_a_license_proof(self):
        all_votes=[]
        for sid,label in self.catalog.items():
            all_votes.extend((vote(sid,1,label),vote(sid,2,label)))
        report=summarize_catalog_reviews(bundle(all_votes))
        self.assertEqual(96,report.declared_votes)
        self.assertEqual(48,dict(report.counts)["attestation_consensus_only"])
        self.assertEqual(0,report.training_authorizations_granted)

    def test_more_than_96_votes_rejected(self):
        many=[vote(self.sid,idx) for idx in range(97)]
        with self.assertRaises(AnnotationReviewError):
            summarize_catalog_reviews(bundle(many))


if __name__=="__main__":
    unittest.main()
