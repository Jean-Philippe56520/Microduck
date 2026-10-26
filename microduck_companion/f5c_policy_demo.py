"""F5-C two-process fictional SQLite cooldown, NO Ollama or network."""
from __future__ import annotations

import argparse
import json
import uuid

from .episodic_memory import ExperienceMemory
from .passive_intentions import PassiveIntent
from .pc_hypothesis_contract import OptionalPCAdvisory, PCObservation, PCRequest
from .selective_pc_policy import SelectivePCPolicy

MOCK_MONO = 100.
MOCK_WALL = 1_780_000_000.


def run_session(path: str, session: str) -> dict:
    if session not in {"first", "second"}:
        raise ValueError("only two fictional sessions are supported")
    memory = ExperienceMemory(path)
    try:
        policy = SelectivePCPolicy(memory)
        req = PCRequest(
            uuid.uuid4().hex,
            (PCObservation("object_label","unknown","unknown",.93),),
            MOCK_MONO,MOCK_MONO+2.,
        )
        cycle = OptionalPCAdvisory(
            PassiveIntent("inspect","fictional_unresolved_category",
                          "object_label","unknown"),
            req,"pending_transport",
        )
        wall = MOCK_WALL if session=="first" else MOCK_WALL+10
        decision = policy.reserve(
            cycle,pc_opt_in=True,now_monotonic_s=MOCK_MONO,
            now_wall_epoch_s=wall,
        )
        if session=="first":
            if not decision.allowed:
                raise RuntimeError("fictional initial consultation not reserved")
            if not policy.complete(
                req.request_id,status="pc_unavailable",
                now_wall_epoch_s=wall+.1,
            ):
                raise RuntimeError("fictional unavailable result not persisted")
        elif decision.allowed or decision.reason!="cooldown":
            raise RuntimeError("SQLite restart lost consultation cooldown")
        return {
            "session":session,
            "local_intention":decision.local_intention,
            "pc_reservation_allowed":decision.allowed,
            "decision_reason":decision.reason,
            "persisted_anonymous_status_counts":policy.counts(),
            "real_network_queries":0,
            "real_model_inferences":0,
            "camera_or_audio_samples":0,
            "motor_commands_issued":decision.motor_commands_issued,
            "real_robot_validated":False,
        }
    finally:
        memory.close()


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database",required=True)
    parser.add_argument("--session",choices=("first","second"),required=True)
    args=parser.parse_args(argv)
    print(json.dumps(run_session(args.database,args.session),
                     sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
