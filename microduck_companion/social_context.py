"""Shared F4-C/P-C fixture-only context contract, never hardware consent.

This dataclass is intentionally independent of the F4-C social composer,
SQLite, robotd, sensors, speech and all motor or sound dispatch. The flags
describe a fictional scenario; they do not authenticate a person or authorize
physical actions. Both historical mock labs and read-only OEM expression
hints consume the SAME class to preserve strict isinstance checks.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MockSocialContext:
    """Claims for test scenarios only, never consent verification hardware."""

    operator_opt_in: bool = False
    supervised: bool = False
    privacy_reviewed: bool = False
    quiet_mode: bool = True
    brief_audio_opt_in: bool = False
    play_invitation_opt_in: bool = False

    def __post_init__(self) -> None:
        if any(type(getattr(self, k)) is not bool for k in (
            "operator_opt_in", "supervised", "privacy_reviewed",
            "quiet_mode", "brief_audio_opt_in", "play_invitation_opt_in",
        )):
            raise ValueError("mock consent flags must be booleans")
