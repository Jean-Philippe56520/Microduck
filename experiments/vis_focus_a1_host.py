"""VIS-FOCUS-A1 HOST COMPARATOR ONLY: F1/F2 mock fixtures, no deployment.

This is an experimental reference to measure a missing current-token focus
contract against existing F2 category-only decisions. It is NOT a Microduck
tracker, OEM skill, robot action, sensor adapter, or a second real brain.
No on-device or B10/B11 pinned Python source is changed by this experiment.
"""
from __future__ import annotations

from dataclasses import dataclass
from microduck_companion.passive_sources import PassiveRead


@dataclass(frozen=True)
class MockFocusHint:
    """One CURRENT fictional attention target, not a physical-object tracker.

    A track_id is an unverified, short-lived F1 fixture token; it is NEVER an
    identity, coordinate, pose, distance, motor intent or movement permission.
    No hint can certify a physical target or authorize an OEM action.
    """

    state: str
    current_track_id: str | None = None
    category: str | None = None
    reason: str = "no_current_focus"
    source: str = "mock_fixture_only"
    physical_identity_verified: bool = False
    location_verified: bool = False
    motor_commands_issued: int = 0

    def __post_init__(self) -> None:
        if (self.state not in {"new", "continued", "none"}
                or self.source != "mock_fixture_only"
                or self.physical_identity_verified is not False
                or self.location_verified is not False
                or type(self.motor_commands_issued) is not int
                or self.motor_commands_issued != 0
                or type(self.reason) is not str or not self.reason):
            raise ValueError("mock focus cannot certify identity, location or action")
        if self.state == "none":
            if self.current_track_id is not None or self.category is not None:
                raise ValueError("absent focus must not retain a track or category")
        elif (not isinstance(self.current_track_id, str)
              or not self.current_track_id.strip()
              or not isinstance(self.category, str) or not self.category.strip()):
            raise ValueError("current fixture focus requires a category and track")


class HostFocusComparator:
    """Ephemeral single-token mock comparator, created ONLY by PC test code.

    It does not persist, match objects, claim identity, access SQLite, load
    a camera/model, request Qwen or issue a motor command. F2 owns ranking.
    """

    def __init__(self) -> None:
        self._mock_focus: tuple[str, str] | None = None
        self._mock_focus_sequence: int | None = None
        self._mock_focus_time: float | None = None

    def describe_mock_visual_focus(self, reading: PassiveRead, selected,
                                   *, now_monotonic_s: float) -> MockFocusHint:
        """Describe at most one F1 fixture token AFTER the existing F2 choice.

        F2 alone chooses whether the category merits attention, considering
        its existing motivations and optional ONE-SQLite hints. This method
        only disambiguates current mock tokens of that chosen category. It
        never estimates geometry, associates different IDs or retries actions.
        No last-known target is returned when its current observation is lost.
        Reuse after cooldown is a description, not a repeated F2 proposal.
        """
        import math
        from microduck_companion.passive_intentions import PassiveIntent
        from microduck_companion.passive_observations import PASSIVE_KINDS, summarize_passive
        from microduck_companion.passive_sources import PassiveRead
        from microduck_companion.perception import PerceptionSnapshot

        if not isinstance(reading, PassiveRead) or not isinstance(selected, PassiveIntent):
            raise TypeError("mock focus requires F1 PassiveRead and F2 PassiveIntent")
        if (type(now_monotonic_s) not in (float, int)
                or not math.isfinite(now_monotonic_s) or now_monotonic_s < 0):
            raise ValueError("mock focus time must be monotonic and finite")
        now = float(now_monotonic_s)

        def clear(reason: str) -> MockFocusHint:
            self._mock_focus = None
            return MockFocusHint("none", reason=reason)

        if self._mock_focus_time is not None and now < self._mock_focus_time:
            # An old monotonic epoch cannot inherit a previous fixture token.
            self._mock_focus_sequence = None
            self._mock_focus_time = now
            return clear("clock_reset_requires_new_observation")
        if (reading.status != "ok" or reading.channel != "mock_fixture_unix"
                or type(reading.sequence) is not int
                or not 0 <= reading.sequence < 2**63
                or not isinstance(reading.snapshot, PerceptionSnapshot)
                or reading.snapshot.environment != "mock"):
            return clear("unavailable_or_untrusted_fixture")
        if (self._mock_focus_sequence is not None
                and reading.sequence <= self._mock_focus_sequence):
            return clear("duplicate_or_out_of_order_fixture")
        self._mock_focus_sequence = reading.sequence
        self._mock_focus_time = now
        if any(event.kind not in PASSIVE_KINDS or event.source != "mock"
               for event in reading.snapshot.events):
            return clear("untrusted_or_nonpassive_event")
        try:
            observations = summarize_passive(reading.snapshot, now=now)
        except (TypeError, ValueError):
            return clear("invalid_observation_batch")
        if any(obs.claimed_source != "mock" or obs.status in {
                "future", "stale", "untrusted"} for obs in observations):
            return clear("untrusted_or_expired_observation")
        if selected.intention == "idle":
            # Continue only an explicitly CURRENT identical fixture token.
            # F2's cooldown is not a command to turn or an identity proof.
            if (selected.reason not in {
                    "no_high_scoring_passive_attention",
                    "no_new_safe_passive_attention"}
                    or self._mock_focus is None):
                return clear("no_admissible_current_interest")
            matches = [obs for obs in observations
                       if obs.kind == "object_label" and obs.usable_category
                       and (obs.track_id, obs.category) == self._mock_focus]
            if len(matches) != 1:
                return clear("original_current_track_missing_or_uncertain")
            return MockFocusHint("continued", self._mock_focus[0],
                                 self._mock_focus[1],
                                 "same_fresh_fixture_track_during_f2_idle")
        if (selected.intention not in {"observe", "inspect"}
                or selected.target_kind != "object_label"):
            return clear("f2_did_not_select_an_object")
        candidates = [obs for obs in observations
                      if obs.kind == "object_label" and obs.track_id is not None
                      and obs.category == selected.target_category
                      and (obs.usable_category or
                           (selected.intention == "inspect"
                            and obs.status == "unknown"))]
        if not candidates:
            # In particular: a conflicting class cannot become a target.
            return clear("selected_category_not_currently_resolved")
        previous = self._mock_focus
        # Prefer the exact token still present. Never equate two distinct
        # tokens just because both say "ball", "person" or "unknown".
        same = [obs for obs in candidates
                if (obs.track_id, obs.category) == previous]
        chosen = same[0] if same else min(
            candidates, key=lambda obs:
            (-obs.confidence, -obs.observed_at, obs.track_id))
        self._mock_focus = (chosen.track_id, chosen.category)
        continuity = previous == self._mock_focus
        return MockFocusHint(
            "continued" if continuity else "new",
            chosen.track_id, chosen.category,
            "same_fresh_fixture_track" if continuity else "fresh_fixture_interest",
        )
