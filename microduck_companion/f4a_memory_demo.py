"""F4-A: two-process MOCK evidence replay, never a live robot cycle.

Offline SQLite persistence demo. Category source is F1-C/F2-C; P2a mock
feedback is explicit and *not* an actual action/reward. Hypotheses have no
authority. No robotd, media, network, Qwen, simulator motor or physical IO.
"""
from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path
import time

from .episodic_memory import ExperienceMemory
from .passive_sources import PassiveRead
from .passive_memory import PassiveObservationJournal
from .passive_learning import PassiveLearning
from .perception import PerceptionEvent, PerceptionSnapshot
from .category_semantics import CategorySemantics
from .behavioral_memory import BehavioralMemory
from .mock_cycles import MockCycleRunner, MockConsequence
from .mock_cycle_demo import mock_snapshot


def run_demo(db: Path, *, session: str) -> dict:
    if session not in {"first","second"}:
        raise ValueError("two explicitly fictional demo sessions only")
    memory=ExperienceMemory(db)
    try:
        wall=time.time()
        journal=PassiveObservationJournal(memory)
        learning=PassiveLearning(memory)
        semantics=CategorySemantics(memory)
        behavior=BehavioralMemory(memory)
        mono=100.
        received=PassiveRead("ok",PerceptionSnapshot("mock",(
            PerceptionEvent("object_label","dog","mock",mono,1.,.93,
                            track_id="track-fictional-animal"),
        ),mono),1,"mock_fixture_unix")
        assert journal.append(
            received,now_monotonic_s=mono+.1,now_wall_epoch_s=wall)==1
        traces=learning.record(journal=journal,sequence=1,
                               now_wall_epoch_s=wall)
        assert len(traces)==1
        assert semantics.remember(
            journal=journal,learning=learning,
            observation_id=traces[0].observation_id,now_wall_epoch_s=wall)
        semantics.hypothesize(category="dog",property="texture",value="soft",
                              confidence=.6,now_wall_epoch_s=wall)
        runner=MockCycleRunner(memory,session="f4a-demo-"+session)
        target="fictional-toy-"+session
        consequence=runner.step(
            mock_snapshot(200.,target=target),now=200.5,
            followup=mock_snapshot(200.4,target=target),
            consequence=MockConsequence(target,"positive",200.3),
        )
        assert consequence.disposition=="mock_feedback"
        assert behavior.record(runner=runner,sequence=consequence.sequence,
                               now_wall_epoch_s=wall)
        cats=semantics.recall(now_wall_epoch_s=wall)
        hints=semantics.hypotheses(category="dog",now_wall_epoch_s=wall)
        mock=behavior.summary(now_wall_epoch_s=wall)
        if (not cats or not hints or mock.motor_commands_issued
                or mock.executed_actions or mock.verified_on_robot or
                any(x.real_sensor_verified for x in cats)
                or any(x.confirmed or x.can_authorize_actions for x in hints)):
            raise RuntimeError("mock memory cannot authorize action")
        return {
            "scope":"fictional_sqlite_historical_only",
            "session":session,
            "semantic_categories":[x.category for x in cats],
            "semantic_evidence_count":len(cats),
            "unverified_hypothesis_count":len(hints),
            "mock_behavior_summary":asdict(mock),
            "sqlite_persistent":True,
            "images_saved":0,"audio_saved":0,"motor_commands_issued":0,
            "real_robot_validated":False,
        }
    finally:
        memory.close()


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database",type=Path,required=True)
    p.add_argument("--session",choices=("first","second"),required=True)
    args=p.parse_args()
    print(json.dumps(run_demo(args.database,session=args.session),
                     sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
