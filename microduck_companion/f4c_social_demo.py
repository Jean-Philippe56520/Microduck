"""F4-C: two *independent* Python processes, social cues MOCK only.

One SQLite database stores generic proposals and suppresses a repeat after
restart. Opt-in flags are fake scenario claims, not real consent or permission
to activate speaker/camera/neck. All plans are descriptive, non-executable.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .mock_social_cues import MockSocialComposer, MockSocialContext
from .passive_memory import PassiveObservationJournal
from .passive_sources import PassiveRead
from .perception import PerceptionEvent, PerceptionSnapshot

FIXTURE_WALL_EPOCH_S = 1_780_000_000.


def bark_receipt() -> PassiveRead:
    event = PerceptionEvent("sound_label", "bark", "mock", 100., 1., .96)
    return PassiveRead(
        "ok", PerceptionSnapshot("mock",(event,),100.), 1,
        "mock_fixture_unix",
    )


def run_demo(path: Path, *, session: str) -> dict:
    if session not in ("first", "second"):
        raise ValueError("unknown fictional session")
    memory=ExperienceMemory(path)
    try:
        brain=AutonomyBrain(memory)
        journal=PassiveObservationJournal(memory)
        composer=MockSocialComposer(brain,journal)
        receipt=bark_receipt()
        default=MockSocialContext()
        if session=="first":
            quiet=composer.propose(
                receipt,context=default,now_monotonic_s=100.1,
                now_wall_epoch_s=FIXTURE_WALL_EPOCH_S)
            assert quiet.kind=="silence"
        allowed=MockSocialContext(
            operator_opt_in=True,supervised=True,privacy_reviewed=True,
            quiet_mode=False,brief_audio_opt_in=True)
        proposed=composer.propose(
            receipt,context=allowed,now_monotonic_s=100.1,
            now_wall_epoch_s=FIXTURE_WALL_EPOCH_S)
        expected="chirp" if session=="first" else "silence"
        if (proposed.kind != expected
                or proposed.speaker_commands_issued
                or proposed.gaze_motor_commands_issued
                or proposed.motor_commands_issued
                or proposed.audio_bytes_stored
                or proposed.physical_execution_authorized
                or proposed.real_consent_verified
                or proposed.real_sensor_authenticated):
            raise RuntimeError("mock social plan cannot perform an action")
        if composer.count_proposals()!=1:
            raise RuntimeError("cooldown must persist between processes")
        return {
            "scenario":"f4c_mock_social_proposals_only",
            "session":session,
            "proposal":asdict(proposed),
            "persisted_generic_proposals":composer.count_proposals(),
            "explicit_opt_in_claim_authenticates_no_one":True,
            "fixture_speaker_calls":0,"fixture_motor_calls":0,
            "microphone_frames":0,"real_media_saved":0,
            "robot_validated":False,
        }
    finally:
        memory.close()


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",required=True,type=Path)
    parser.add_argument("--session",choices=("first","second"),required=True)
    args=parser.parse_args()
    print(json.dumps(run_demo(args.database,session=args.session),
                     sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
