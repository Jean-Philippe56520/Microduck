"""EX4-C: mock-only cross-check of queued intent, scripted stages and EX2 effect.

Not a robot receipt, not a causal learner. Reads the existing EX1/EX2
ExperienceMemory through EX4-A, validates OEM wire fixtures through EX4-B.
No SQL writes, network, actuators, inference, reward or parallel memory.
"""
from __future__ import annotations

from dataclasses import dataclass

from .experience_ledger import _epoch, _key
from .ex4_evidence_audit import ExecutionEvidenceAudit
from .ex4b_oem_wire_audit import (
    OemWireFrame,
    OemWireProposal,
    OemWireVerdict,
    review_oem_wire_fixture,
)

MOCK_STAGE_SOURCE = "ex4c_scripted_stages_only"
MAX_EVENTS = 3
MAX_BATCH = 32
_STAGES = frozenset({"started", "completed", "refused", "interrupted"})
_EFFECT_STATUSES = {
    "mock_temporal_only": "temporal_only",
    "mock_confounded": "confounded",
    "mock_unchanged": "no_change",
    "mock_indeterminate": "indeterminate",
    "mock_resolution_only": "not_observed",
}


@dataclass(frozen=True, slots=True)
class ScriptedStage:
    """A test script's claimed transition, NEVER a signal from robotd."""

    session: str
    sequence: int
    rpc_id: int
    event_number: int
    stage: str
    at_epoch_s: float
    source: str = MOCK_STAGE_SOURCE

    def __post_init__(self) -> None:
        _key(self.session, self.sequence)
        if (type(self.rpc_id) is not int or not 1 <= self.rpc_id <= 2_147_483_647
                or type(self.event_number) is not int
                or not 1 <= self.event_number <= MAX_EVENTS
                or type(self.stage) is not str or self.stage not in _STAGES
                or self.source != MOCK_STAGE_SOURCE):
            raise ValueError("untrusted scripted transition")
        _epoch(self.at_epoch_s)


@dataclass(frozen=True, slots=True)
class CausalPreflightVerdict:
    session: str
    sequence: int
    method: str
    wire_status: str
    stage_status: str
    effect_status: str
    status: str
    source: str = "mock_fixture_crosscheck_only"
    authorized: str = "not_attested"
    executed: str = "not_attested"
    observations_authenticated: bool = False
    causality_established: bool = False
    physical_execution_verified: bool = False
    physical_learning_allowed: bool = False
    motor_commands_issued: int = 0


class MockCausalPreflight:
    """Use an existing EX4-A audit and its sole SQLite, with no writes.

    EX1/EX2 correction flags are reread for EACH review. Both EX2's scene
    correspondence and OEM state frames are merely untrusted fixture claims.
    This preflight never accepts raw "robotd" receipts or physical provenance.
    """

    def __init__(self, audit: ExecutionEvidenceAudit) -> None:
        if type(audit) is not ExecutionEvidenceAudit:
            raise TypeError("requires the existing EX4-A audit")
        self._audit = audit

    def review(
        self,
        proposal: OemWireProposal,
        *,
        reply: OemWireFrame | None = None,
        states: tuple[OemWireFrame, ...] = (),
        stages: tuple[ScriptedStage, ...] = (),
        now_monotonic_s: float,
        now_epoch_s: float,
    ) -> CausalPreflightVerdict:
        """Assess consistency of historical mock effects and scripted lifecycle.

        The two clock domains remain separate: EX4-B's local monotonic
        timestamps are NEVER matched to EX1/EX2's fictional epoch times.
        """
        if not isinstance(proposal, OemWireProposal):
            raise TypeError("OEM fixture proposal expected")
        now_epoch = _epoch(now_epoch_s)
        if type(stages) is not tuple or len(stages) > MAX_EVENTS:
            raise ValueError("bounded scripted stages tuple expected")

        wire: OemWireVerdict = review_oem_wire_fixture(
            proposal, reply=reply, states=states,
            now_monotonic_s=now_monotonic_s,
        )
        history = self._audit.review_ex1(
            session=wire.session, sequence=wire.sequence,
        )

        def verdict(stage: str, effect: str, status: str) -> CausalPreflightVerdict:
            return CausalPreflightVerdict(
                session=wire.session,
                sequence=wire.sequence,
                method=wire.method,
                wire_status=wire.reply_status,
                stage_status=stage,
                effect_status=effect,
                status=status,
            )

        # No accepted completion is even modelled for velocity, gaze or
        # other continuously updated intents. "robot.do" itself only queues.
        if wire.method != "robot.do":
            if stages:
                raise ValueError("cannot attach scripted completion to non-skill RPC")
            return verdict("not_applicable", "not_attributable", "no_skill_lifecycle")
        if wire.request_id is None or wire.reply_status not in (
            "queued_only", "refused",
        ):
            if stages:
                raise ValueError("scripted stage cannot upgrade an unanswered request")
            return verdict("not_attested", "not_attributable", "unanswered_or_error")
        # Validate every caller-supplied stage even if EX1 has since been
        # retracted, so a conflicting fake ID cannot disappear behind a
        # historical correction. No stage can turn an OEM ack into execution.
        if stages:
            self._validate_stages(stages, wire=wire, now_epoch=now_epoch)
        if history.status == "missing":
            if stages:
                raise ValueError("no source EX1 history for scripted stages")
            return verdict("not_attested", "not_observed", "missing_mock_history")
        if history.status in ("withdrawn", "withdrawn_effect"):
            return verdict("withdrawn", "not_attributable", history.status)
        if history.status == "invalid_provenance":
            return verdict("invalid", "not_attributable", "invalid_mock_history")
        if history.status == "proposed":
            if stages:
                raise ValueError("EX1 unresolved proposal cannot have stages")
            return verdict("not_attested", "not_observed", "unresolved_mock_proposal")
        if history.status in ("refused", "interrupted"):
            if stages and (
                len(stages) != 1 or stages[0].stage != history.status
            ):
                raise ValueError("mock refusal/interruption has no execution")
            if stages:
                lifecycle = self._audit._memory.conn.execute("""
                    SELECT proposed_at_epoch_s,resolved_at_epoch_s
                    FROM ex1_mock_experiences
                    WHERE session=? AND sequence=?
                """, (wire.session, wire.sequence)).fetchone()
                if lifecycle is None or lifecycle["resolved_at_epoch_s"] is None:
                    raise ValueError("missing EX1 mock resolution")
                at = stages[0].at_epoch_s
                if not (lifecycle["proposed_at_epoch_s"] <= at
                        <= lifecycle["resolved_at_epoch_s"]):
                    raise ValueError("scripted refusal outside EX1 lifecycle")
            return verdict(history.status, "not_observed", history.status)
        if history.status not in _EFFECT_STATUSES:
            return verdict("invalid", "not_attributable", "invalid_mock_history")
        if wire.reply_status == "refused":
            if stages:
                raise ValueError("refused OEM request has claimed execution")
            return verdict("not_attested", "not_attributable", "oem_refused")
        if not stages:
            return verdict("not_attested", "not_attributable", "no_scripted_stages")

        stage_names = tuple(e.stage for e in stages)
        if stage_names not in (
            ("started",), ("started", "interrupted"),
            ("started", "completed"),
        ):
            raise ValueError("unsupported scripted state machine")

        # Recheck EX1 times even for a partial script: a stale "started"
        # event is not a currently pending scripted action.
        con = self._audit._memory.conn
        effect_join = self._audit._exists("ex2_mock_effects")
        if effect_join:
            row = con.execute("""
                SELECT p.proposed_at_epoch_s AS proposed,
                       p.resolved_at_epoch_s AS resolved,
                       e.before_epoch_s AS before_cue,
                       e.after_epoch_s AS after_cue,
                       e.active AS effect_active
                FROM ex1_mock_experiences p
                LEFT JOIN ex2_mock_effects e ON e.ex1_id=p.id
                WHERE p.session=? AND p.sequence=?
            """, (wire.session, wire.sequence)).fetchone()
        else:
            row = con.execute("""
                SELECT proposed_at_epoch_s AS proposed,
                       resolved_at_epoch_s AS resolved,
                       NULL AS before_cue, NULL AS after_cue,
                       NULL AS effect_active
                FROM ex1_mock_experiences
                WHERE session=? AND sequence=?
            """, (wire.session, wire.sequence)).fetchone()
        if row is None or row["resolved"] is None:
            raise ValueError("missing EX1 mock resolution")
        proposed = _epoch(row["proposed"])
        resolved = _epoch(row["resolved"])
        times = tuple(s.at_epoch_s for s in stages)
        if (not proposed <= times[0] < resolved
                or any(not proposed < moment <= resolved for moment in times[1:])):
            raise ValueError("scripted stages outside EX1 resolution")
        if stage_names == ("started",):
            return verdict("mock_started_only", "not_attributable", "mock_incomplete")
        if stage_names == ("started", "interrupted"):
            return verdict("mock_interrupted", "not_attributable", "mock_interrupted")
        started, completed = times
        if row["before_cue"] is not None and row["effect_active"] == 1:
            before = _epoch(row["before_cue"])
            after = _epoch(row["after_cue"])
            if not before < started < completed < after:
                raise ValueError("mock effect cues contradict scripted lifecycle")
        effect = _EFFECT_STATUSES[history.status]
        if wire.state_status.startswith(("unsafe_", "limited_", "incomplete_")):
            return verdict("mock_completed_only", effect, "unsafe_or_limited_wire")
        if effect == "temporal_only":
            return verdict("mock_completed_only", effect, "mock_temporal_only")
        if effect == "confounded":
            return verdict("mock_completed_only", effect, "mock_confounded")
        if effect == "no_change":
            return verdict("mock_completed_only", effect, "mock_unchanged")
        if effect == "indeterminate":
            return verdict("mock_completed_only", effect, "mock_indeterminate")
        return verdict("mock_completed_only", effect, "mock_no_effect")

    @staticmethod
    def _validate_stages(
        stages: tuple[ScriptedStage, ...],
        *,
        wire: OemWireVerdict,
        now_epoch: float,
    ) -> None:
        prior = None
        seen = set()
        for index, event in enumerate(stages, 1):
            if type(event) is not ScriptedStage:
                raise TypeError("only typed, synthetic EX4-C transitions accepted")
            if ((event.session, event.sequence) !=
                    (wire.session, wire.sequence)
                    or event.rpc_id != wire.request_id
                    or event.event_number != index):
                raise ValueError("unmatched or replayed mock execution stage")
            if not event.at_epoch_s <= now_epoch:
                raise ValueError("future scripted event")
            if prior is not None and event.at_epoch_s <= prior:
                raise ValueError("reordered scripted events")
            if event.stage in seen:
                raise ValueError("replayed scripted stage")
            seen.add(event.stage)
            prior = event.at_epoch_s

    def review_batch(
        self,
        entries: tuple[tuple[OemWireProposal, OemWireFrame | None,
                            tuple[OemWireFrame, ...],
                            tuple[ScriptedStage, ...]], ...],
        *,
        now_monotonic_s: float,
        now_epoch_s: float,
    ) -> tuple[CausalPreflightVerdict, ...]:
        """Prevent duplicate fixture keys in a batch, not across restarts."""
        if type(entries) is not tuple or len(entries) > MAX_BATCH:
            raise ValueError("bounded EX4-C batch required")
        seen_cycles: set[tuple[str, int]] = set()
        seen_rpc: set[tuple[str, int]] = set()
        outcomes: list[CausalPreflightVerdict] = []
        for item in entries:
            if type(item) is not tuple or len(item) != 4:
                raise ValueError("invalid EX4-C batch entry")
            proposal, reply, states, stages = item
            if not isinstance(proposal, OemWireProposal):
                raise TypeError("typed OEM proposal required")
            key = (proposal.session, proposal.sequence)
            rpc_id = proposal.packet.get("id") if type(proposal.packet) is dict else None
            rpc_key = (proposal.session, rpc_id) if rpc_id is not None else None
            if key in seen_cycles or (rpc_key is not None and rpc_key in seen_rpc):
                raise ValueError("replayed mock session/sequence or RPC ID")
            result = self.review(
                proposal, reply=reply, states=states, stages=stages,
                now_monotonic_s=now_monotonic_s, now_epoch_s=now_epoch_s,
            )
            seen_cycles.add(key)
            if rpc_key is not None:
                seen_rpc.add(rpc_key)
            outcomes.append(result)
        return tuple(outcomes)
