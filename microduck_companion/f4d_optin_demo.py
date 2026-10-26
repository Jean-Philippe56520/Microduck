"""F4-D: two processes prove *fictional* opt-in association and revocation.

All key and token bytes below are PUBLIC, STATIC, INSECURE TEST FIXTURES.
NEVER reuse them with a person, child, pet, household tag, or physical
robot. The SQLite file stores only HMAC tags, opaque ref and generic class.
No camera, BLE/NFC, audio, tracker, LLM, speaker, motor or network.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .episodic_memory import ExperienceMemory
from .revocable_mock_identity import (
    MockOptInContext, MockTokenPresentation, RevocableMockAssociations,
)

TEST_KEY = bytes(range(32,64))
TEST_TOKEN = bytes(range(32))
TEST_WALL = 1_780_000_000.


def _opted_in() -> MockOptInContext:
    return MockOptInContext(
        operator_opt_in=True,supervised=True,privacy_reviewed=True,
        token_presented_voluntarily=True,
    )


def run_demo(path: Path, *, session: str) -> dict:
    if session not in {"first", "second"}:
        raise ValueError("unknown fictitious demo session")
    mem = ExperienceMemory(path)
    try:
        registry=RevocableMockAssociations(mem,key=TEST_KEY)
        denied=None
        if session=="first":
            denied=registry.enroll(
                token=TEST_TOKEN,kind="pet_dog",
                context=MockOptInContext(),now_wall_epoch_s=TEST_WALL)
            if denied is not None or registry.count(
                    now_wall_epoch_s=TEST_WALL):
                raise RuntimeError("mock registration without opt-in")
            handle=registry.enroll(
                token=TEST_TOKEN,kind="pet_dog",
                context=_opted_in(),now_wall_epoch_s=TEST_WALL)
            if handle is None:
                raise RuntimeError("fictional opt-in enrollment failed")
            result=registry.present(
                MockTokenPresentation(TEST_TOKEN,1,TEST_WALL),
                context=_opted_in(),now_wall_epoch_s=TEST_WALL)
            if (result.status!="mock_token_association_only"
                    or result.association_ref!=handle.association_ref
                    or result.kind!="pet_dog"):
                raise RuntimeError("fictional token association failed")
            revoked=False
        else:
            # Fresh Python process, using same disposable public mock values.
            # No private secret, person's name or real token crosses processes.
            result=registry.present(
                MockTokenPresentation(TEST_TOKEN,2,TEST_WALL+1),
                context=_opted_in(),now_wall_epoch_s=TEST_WALL+1)
            if result.status!="mock_token_association_only":
                raise RuntimeError("mock association not retained across restart")
            revoked=registry.revoke(
                association_ref=result.association_ref,token=TEST_TOKEN,
                context=_opted_in())
            if not revoked:
                raise RuntimeError("mock revoke did not delete pairing")
            after=registry.present(
                MockTokenPresentation(TEST_TOKEN,3,TEST_WALL+2),
                context=_opted_in(),now_wall_epoch_s=TEST_WALL+2)
            if after.status!="unknown":
                raise RuntimeError("revoked pairing must be unknown")
        if (result.real_identity_verified or result.real_guardian_verified
                or result.physical_actions_authorized
                or result.motor_commands_issued or result.speaker_commands_issued):
            raise RuntimeError("mock fixture must never authorize hardware")
        expected=1 if session=="first" else 0
        if registry.count(now_wall_epoch_s=TEST_WALL+2)!=expected:
            raise RuntimeError("mock association cardinality mismatch")
        return {
            "scenario":"fictional_voluntary_token_only",
            "session":session,
            "presented_mock_token_status":result.status,
            "returned_generic_class":result.kind,
            "mock_binding_count_after":expected,
            "revoked_in_this_process":revoked,
            "physical_identity_authenticated":False,
            "real_guardian_authenticated":False,
            "actual_hardware_token_readers":0,
            "real_biometric_templates":0,
            "camera_frames_saved":0,
            "voice_samples_saved":0,
            "speaker_commands_issued":0,
            "motor_commands_issued":0,
            "physical_robot_validated":False,
        }
    finally:
        mem.close()


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database",required=True,type=Path)
    p.add_argument("--session",required=True,choices=("first","second"))
    args=p.parse_args()
    print(json.dumps(run_demo(args.database,session=args.session),
                     sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
