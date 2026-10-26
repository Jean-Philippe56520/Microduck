"""F5-A deterministic offline demonstration: NO Ollama/Qwen, no network."""
from __future__ import annotations

import json

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .passive_memory import PassiveObservationJournal
from .passive_sources import PassiveRead
from .perception import PerceptionEvent, PerceptionSnapshot
from .pc_hypothesis_contract import (
    finish_optional_pc_cycle, start_optional_pc_cycle,
)


def run_demo() -> dict:
    memory = ExperienceMemory(":memory:")
    try:
        journal = PassiveObservationJournal(memory)
        event = PerceptionEvent(
            kind="object_label", value="unknown", source="mock",
            observed_at=100.0, ttl_s=1.0, confidence=.95,
            track_id="track-fictional-object",
        )
        reading = PassiveRead(
            "ok", PerceptionSnapshot("mock", (event,), 100.0),
            sequence=1, channel="mock_fixture_unix",
        )
        offline = start_optional_pc_cycle(
            AutonomyBrain(memory), reading, journal=journal,
            now_monotonic_s=100.0, now_wall_epoch_s=1_780_000_000.,
        )
        no_pc = finish_optional_pc_cycle(
            offline, None, received_monotonic_s=100.1,
        )
        # Second independent brain instance, SAME SQLite. No network is opened.
        mock = start_optional_pc_cycle(
            AutonomyBrain(memory), reading, journal=journal,
            now_monotonic_s=100.0, now_wall_epoch_s=1_780_000_000.,
        )
        fixture_reply = json.dumps({
            "schema_version": 1,
            "request_id": mock.request.request_id,
            "source": "pc_qwen_unverified",
            "hypotheses": [{
                "kind": "object_label", "category": "cat",
                "confidence": .7, "ttl_s": 1.,
            }],
        }).encode("utf-8")
        done = finish_optional_pc_cycle(
            mock, fixture_reply, received_monotonic_s=100.2,
        )
        if (no_pc.status != "pc_unavailable" or done.status
                != "hypotheses_unverified" or done.hypotheses[0].verified
                or no_pc.local_intent != mock.local_intent
                or memory.experience_count() != 0):
            raise RuntimeError("F5-A mock PC results violated local autonomy")
        return {
            "scenario": "fictional_category_and_fake_pc_reply_only",
            "offline_local_intention": no_pc.local_intent.intention,
            "offline_pc_status": no_pc.status,
            "mock_reply_status": done.status,
            "hypotheses_only_unverified": len(done.hypotheses),
            "actual_pc_queries": 0,
            "camera_frames_saved": 0,
            "audio_samples_saved": 0,
            "motor_commands_issued": 0,
            "speaker_commands_issued": 0,
            "physical_robot_validated": False,
        }
    finally:
        memory.close()


def main() -> int:
    print(json.dumps(run_demo(), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
