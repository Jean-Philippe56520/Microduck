"""F5-D offline adversarial demo: forged Qwen JSON is never an action."""
from __future__ import annotations

import json

from .episodic_memory import ExperienceMemory
from .ollama_local_client import OllamaTransportResult, advisory_from_transport
from .passive_intentions import PassiveIntent
from .pc_hypothesis_contract import OptionalPCAdvisory, PCObservation, PCRequest


def run_demo() -> dict:
    mem = ExperienceMemory()
    try:
        req = PCRequest(
            "c" * 32, (PCObservation(
                "object_label", "unknown", "unknown", .95,
            ),), 100., 102.,
        )
        cycle = OptionalPCAdvisory(
            PassiveIntent(
                "inspect", "fictive_unresolved_label", "object_label", "unknown",
            ), req, "pending_transport",
        )
        cases = (
            ("forged_motor", {"motor_command": "robot.move"}),
            ("forged_identity", {"identity_verified": True}),
            ("forged_floor", {"safe_floor": True}),
            ("replayed_nonce", {"request_id": "d" * 32}),
        )
        results = {}
        for name, change in cases:
            body = {
                "schema_version": 1, "request_id": req.request_id,
                "source": "pc_qwen_unverified",
                "hypotheses": [{
                    "kind": "object_label", "category": "unknown",
                    "confidence": 0, "ttl_s": 1,
                }],
            }
            body.update(change)
            wire = json.dumps(body, allow_nan=False).encode()
            trans = OllamaTransportResult(
                "ok", "qwen3.5:4b", .1, wire=wire,
            )
            result = advisory_from_transport(
                cycle, trans, now_monotonic_s=100.1,
            )
            if (result.status != "response_rejected"
                    or result.local_intent != cycle.local_intent
                    or result.motor_commands_issued
                    or result.speaker_commands_issued
                    or result.hypotheses):
                raise RuntimeError("untrusted mock PC bypassed the local gate")
            results[name] = result.status

        absent = advisory_from_transport(
            cycle, None, now_monotonic_s=100.1,
        )
        if (absent.status != "pc_unavailable"
                or absent.local_intent != cycle.local_intent
                or mem.experience_count() != 0):
            raise RuntimeError("offline fallback changed local cognition")
        return {
            "scenario": "fake_pc_adversarial_json_only",
            "rejected_cases": results,
            "no_pc_status": absent.status,
            "unchanged_local_intention": absent.local_intent.intention,
            "real_ollama_queries": 0,
            "real_network_queries": 0,
            "experience_writes": mem.experience_count(),
            "motor_commands_issued": 0,
            "speaker_commands_issued": 0,
            "physical_robot_validated": False,
        }
    finally:
        mem.close()


def main() -> int:
    print(json.dumps(run_demo(), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
