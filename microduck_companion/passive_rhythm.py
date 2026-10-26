"""F2-B: bounded, deterministic *proposals* of passive attention.

The existing AutonomyBrain owns one PassiveRhythm state. It consumes F2-A's
already validated mock-only PassiveRead and the existing category journal.
This module NEVER calls robotd, mediad, motors, speakers, a PC or a network.

'energy' is a *simulated motivation variable*: this bookkeeping does NOT
measure battery, CPU consumption, sleep or actual effects of an action.
No rewards or object preferences are updated in F2-B (reserved for F2-C).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
import sqlite3

from .autonomy import Motivations
from .passive_intentions import (PassiveIntent, propose_passive_intention,
                                 _valid_motivations, _valid_scalar)
from .passive_memory import PassiveObservationJournal
from .passive_learning import PassiveLearning
from .behavioral_memory import BehavioralMemory, valid_mock_summary
from .experience_expectations import MockAttentionTrends, MAX_ATTENTION_BIAS
from .passive_observations import summarize_passive
from .passive_sources import PassiveRead

MIN_CYCLE_GAP_S = 0.5
ATTENTION_COOLDOWN_S = 3.0
REST_ENTER_ENERGY = 0.22
REST_EXIT_ENERGY = 0.34
REST_GAIN_PER_TICK = 0.04
IDLE_GAIN_PER_TICK = 0.005
ATTENTION_COST_PER_TICK = 0.015
_HISTORY_LIMIT = 32
_VALID_BASELINE_IDLE = frozenset({
    "no_current_observation", "no_new_safe_passive_attention",
})
_ACTIVE = frozenset({"observe", "inspect", "listen"})


@dataclass(frozen=True)
class PassiveRhythmMetrics:
    """Measurements of *proposals*, not of real or simulated execution."""

    cycles: int
    counts: tuple[tuple[str, int], ...]
    cooldown_blocks: int
    consecutive_active_repeats: int
    recent_intentions: tuple[str, ...]
    simulated_motivation_energy: float

    def count(self, intention: str) -> int:
        return dict(self.counts).get(intention, 0)


class PassiveRhythm:
    """Small process-local cadence state, owned by the EXISTING brain.

    No SQLite changes and no cross-process cooldown claims. A caller should
    pass each new F1-B read once, BEFORE optionally journaling it in F1-C.
    """

    def __init__(self) -> None:
        self._last_tick_s: float | None = None
        self._last_sequence: int | None = None
        self._cooldown_until: dict[tuple[str, str, str], float] = {}
        self._resting = False
        self._recent: deque[str] = deque(maxlen=_HISTORY_LIMIT)
        self._counts = {key: 0 for key in
                        ("observe", "inspect", "listen", "idle", "rest")}
        self._cooldown_blocks = 0
        self._active_repeats = 0

    def metrics(self, motivations: Motivations) -> PassiveRhythmMetrics:
        if not isinstance(motivations, Motivations):
            raise TypeError("the existing Motivations state is required")
        return PassiveRhythmMetrics(
            cycles=sum(self._counts.values()),
            counts=tuple(sorted(self._counts.items())),
            cooldown_blocks=self._cooldown_blocks,
            consecutive_active_repeats=self._active_repeats,
            recent_intentions=tuple(self._recent),
            simulated_motivation_energy=motivations.energy,
        )

    def _record(self, proposal: PassiveIntent, *, motivations: Motivations,
                update_energy: bool) -> PassiveIntent:
        if self._recent and (proposal.intention in _ACTIVE
                             and self._recent[-1] == proposal.intention):
            self._active_repeats += 1
        self._recent.append(proposal.intention)
        self._counts[proposal.intention] += 1
        # Only a validated *fictional cognitive cycle* changes simulated
        # energy, never a failed read, malformed datum or rate-limited tick.
        if update_energy:
            if proposal.intention == "rest":
                delta = REST_GAIN_PER_TICK
            elif proposal.intention == "idle":
                delta = IDLE_GAIN_PER_TICK
            else:
                delta = -ATTENTION_COST_PER_TICK
            motivations.energy = max(0., min(1., motivations.energy + delta))
        return proposal

    @staticmethod
    def _idle(reason: str) -> PassiveIntent:
        return PassiveIntent("idle", reason)

    @staticmethod
    def _score(intention: str, category: str, motives: Motivations) -> float:
        """All five motives participate; scoring remains fixed in F2-B."""
        fatigue = 1.0 - motives.energy
        if intention == "observe":
            toy_attention = motives.play * 0.22 if category in {"ball", "toy"} else 0.
            return (0.12 + 0.70 * motives.curiosity + toy_attention
                    - 0.45 * motives.caution - 0.10 * fatigue)
        if intention == "inspect":
            return (0.13 + 0.80 * motives.curiosity
                    - 0.55 * motives.caution - 0.10 * fatigue)
        if intention == "listen":
            return (0.18 + 0.80 * motives.sociability
                    - 0.28 * motives.caution - 0.10 * fatigue)
        raise ValueError("unsupported active attention")

    def tick(self, reading: PassiveRead, *,
             journal: PassiveObservationJournal, motivations: Motivations,
             now_monotonic_s: float, now_wall_epoch_s: float,
             learning: PassiveLearning | None = None,
             behavioral: BehavioralMemory | None = None,
             expectations: MockAttentionTrends | None = None) -> PassiveIntent:
        """One strictly passive, mock-only cognitive cycle.

        F2-A validation is called *inside* this module. The caller cannot
        forge a validated baseline to promote untrusted or stale snapshots.
        The snapshot is NEVER interpreted when F2-A returns an invalid state.
        """
        if not isinstance(reading, PassiveRead):
            raise TypeError("expected F1-B PassiveRead")
        if not isinstance(journal, PassiveObservationJournal):
            raise TypeError("expected F1-C passive journal")
        if not isinstance(motivations, Motivations):
            raise TypeError("expected existing motivations")
        if learning is not None:
            if not isinstance(learning, PassiveLearning):
                raise TypeError("expected optional F2-C passive learning")
            if learning._memory is not journal._memory:
                raise ValueError("learning must share the journal SQLite")
        if behavioral is not None:
            if not isinstance(behavioral, BehavioralMemory):
                raise TypeError("existing F4-A BehavioralMemory required")
            if behavioral._memory is not journal._memory:
                raise ValueError("F4-A memory must share F1/F2 SQLite")
        if expectations is not None:
            if not isinstance(expectations, MockAttentionTrends):
                raise TypeError("EX3 must use the existing mock trend reader")
            if expectations._memory is not journal._memory:
                raise ValueError("EX3 and F2 must share one ExperienceMemory")
        if not _valid_scalar(now_monotonic_s) or not _valid_scalar(now_wall_epoch_s):
            raise ValueError("clocks must be finite and nonnegative")
        now = float(now_monotonic_s)

        # A monotonic reset is not a legitimate new observation. Require a
        # separate future tick after reset; never reuse cooldowns/sequence.
        if self._last_tick_s is not None and now < self._last_tick_s:
            self._last_tick_s = now
            self._last_sequence = None
            self._cooldown_until.clear()
            self._resting = False
            return self._record(self._idle("clock_reset_requires_new_read"),
                                motivations=motivations, update_energy=False)
        if (self._last_tick_s is not None
                and now - self._last_tick_s < MIN_CYCLE_GAP_S):
            return self._record(self._idle("cycle_rate_limited"),
                                motivations=motivations, update_energy=False)
        self._last_tick_s = now

        baseline = propose_passive_intention(
            reading, journal=journal, motivations=motivations,
            now_monotonic_s=now, now_wall_epoch_s=now_wall_epoch_s,
        )
        if (not _valid_motivations(motivations)
                or (baseline.intention == "idle"
                    and baseline.reason not in _VALID_BASELINE_IDLE)):
            return self._record(self._idle(baseline.reason),
                                motivations=motivations, update_energy=False)
        # F2-A has already validated sequence type/bounds and mock channel.
        if (reading.status != "ok" or reading.channel != "mock_fixture_unix"
                or type(reading.sequence) is not int
                or not 0 <= reading.sequence < 2**63):
            return self._record(self._idle("invalid_fixture_read"),
                                motivations=motivations, update_energy=False)
        if (self._last_sequence is not None
                and reading.sequence <= self._last_sequence):
            return self._record(self._idle("duplicate_source_sequence"),
                                motivations=motivations, update_energy=False)
        self._last_sequence = reading.sequence

        # A valid read with too little simulated motivational energy can
        # propose rest, with two thresholds to avoid oscillating decisions.
        if motivations.energy <= REST_ENTER_ENERGY:
            self._resting = True
        if self._resting and motivations.energy < REST_EXIT_ENERGY:
            return self._record(
                PassiveIntent("rest", "simulated_energy_recovery_hysteresis"),
                motivations=motivations, update_energy=True,
            )
        self._resting = False

        # F2-A returned a valid baseline (possibly idle for an already-known
        # category): therefore provenance + fresh timestamps have passed.
        observations = summarize_passive(reading.snapshot, now=now)
        # EX3 is an OPTIONAL read-only hint, never a second action loop.
        # Read only after F2-A authenticated this synthetic passive frame.
        trend_biases: dict[tuple[str, str], float] = {}
        if expectations is not None:
            try:
                for obs in observations:
                    if not obs.usable_category or obs.category == "unknown":
                        continue
                    verb = ("observe" if obs.kind == "object_label"
                            else "listen")
                    key = (verb, obs.category)
                    if key not in trend_biases:
                        bias = expectations.bias_for(
                            intention=verb, category=obs.category,
                            now_wall_epoch_s=now_wall_epoch_s)
                        if (type(bias) is not float or not math.isfinite(bias)
                                or not -MAX_ATTENTION_BIAS <= bias <= MAX_ATTENTION_BIAS):
                            raise ValueError("invalid EX3 trend hint")
                        trend_biases[key] = bias
            except (sqlite3.Error, ValueError, OverflowError):
                return self._record(self._idle("ex3_history_unavailable"),
                                    motivations=motivations, update_energy=False)
        idle_score = (0.24 + 0.35 * motivations.caution
                      + 0.25 * (1.0 - motivations.energy))
        best_score, best_proposal = idle_score, self._idle(
            "no_high_scoring_passive_attention")
        candidates: list[tuple[str, str, str, str]] = []
        for obs in observations:
            if obs.kind == "object_label":
                if obs.status in {"unknown", "conflict"}:
                    candidates.append(("inspect", "object_label", "unknown",
                                       "uncertain_mock_object_category"))
                elif obs.usable_category:
                    try:
                        known = journal.category_count(
                            "object_label", obs.category,
                            now_wall_epoch_s=now_wall_epoch_s)
                    except sqlite3.Error:
                        return self._record(self._idle("history_unavailable"),
                                            motivations=motivations,
                                            update_energy=False)
                    if known == 0:
                        candidates.append(("observe", "object_label",
                                           obs.category,
                                           "novel_mock_category"))
                    elif trend_biases.get(("observe", obs.category), 0.0) > 0:
                        # Only a positive, repeated MOCK trend can re-propose
                        # familiar passive attention; cooldown still applies.
                        candidates.append(("observe", "object_label",
                                           obs.category,
                                           "repeated_temporal_mock_attention"))
            elif obs.kind == "sound_label" and obs.status in {
                "identified", "unknown", "conflict",
            }:
                candidates.append(("listen", "sound_label", obs.category,
                                   "fictional_sound_category"))

        # F4-A stores only explicitly corroborated P2a *fictional* outcomes.
        # The optional bounded summary is an inspection tendency, not a
        # second learned policy or evidence of physical execution. Read once.
        outcome_bias = 0.0
        if behavioral is not None and any(c[0] == "inspect" for c in candidates):
            try:
                summary = behavioral.summary(now_wall_epoch_s=now_wall_epoch_s)
                if not valid_mock_summary(summary):
                    return self._record(self._idle("invalid_mock_outcome_summary"),
                                        motivations=motivations,
                                        update_energy=False)
                outcome_bias = summary.bias
            except (sqlite3.Error, ValueError, OverflowError):
                return self._record(self._idle("behavioral_history_unavailable"),
                                    motivations=motivations,
                                    update_energy=False)

        # Keep category-only cooldowns: never retain raw frames, track IDs,
        # transcripts or identities in scheduler state.
        self._cooldown_until = {
            key: until for key, until in self._cooldown_until.items()
            if until > now
        }
        seen: set[tuple[str, str, str]] = set()
        for intention, kind, category, reason in candidates:
            key = (intention, kind, category)
            if key in seen:
                continue
            seen.add(key)
            if self._cooldown_until.get(key, 0.) > now:
                self._cooldown_blocks += 1
                continue
            score = self._score(intention, category, motivations)
            score += trend_biases.get((intention, category), 0.0)
            if intention == "inspect":
                score += outcome_bias  # <= +/-0.12, mock-only; no motor effect
            # Explicitly opt-in: F2-B callers keep their original fixed scores.
            # These tiny values only rank passive proposals, never motor acts.
            if learning is not None:
                try:
                    score += learning.preference(intention)
                except (sqlite3.Error, ValueError):
                    return self._record(self._idle("learning_unavailable"),
                                        motivations=motivations,
                                        update_energy=False)
            # Small, bounded same-intention penalty; a genuinely different
            # fresh category must not be suppressed just because another
            # category used the same passive verb on the prior tick.
            if self._recent and self._recent[-1] == intention:
                score -= 0.02
            if score > best_score:
                best_score = score
                best_proposal = PassiveIntent(
                    intention, reason, kind, category)

        if best_proposal.intention in _ACTIVE:
            key = (best_proposal.intention, best_proposal.target_kind,
                   best_proposal.target_category)
            self._cooldown_until[key] = now + ATTENTION_COOLDOWN_S
        return self._record(best_proposal, motivations=motivations,
                            update_energy=True)
