"""Synthetic affect and personality: expressive signals, not sentience or real desire.

No external network, memory persistence, erotic generation, or robot actuation.
Any romantic tone requires independently verified adult, revocable session consent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


def _score(value: int, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 5:
        raise ValueError(f"{label} must be an integer from 0 to 5")
    return value


def _bound(value: int) -> int:
    return max(0, min(5, value))


@dataclass(frozen=True)
class PersonalityTraits:
    """Stable, transparent expression preferences; not biological traits."""

    warmth: int = 4
    curiosity: int = 5
    humor: int = 4
    empathy: int = 5
    initiative: int = 4

    def __post_init__(self) -> None:
        for name in ("warmth", "curiosity", "humor", "empathy", "initiative"):
            _score(getattr(self, name), name)


@dataclass(frozen=True)
class AffectSnapshot:
    owner_id: str
    curiosity: int
    delight: int
    concern: int
    warmth: int
    playful: int
    simulated_attraction: int
    romantic_mode: bool


class AffectiveCompanion:
    """Compute non-conscious mood-like values from host-classified events.

    Event names are supplied by the host, never directly granted permissions.
    Romantic expression is OFF by default and may only be enabled via a trusted
    adult-and-consent check supplied by the host. It affects textual style only.
    """

    SIGNALS = frozenset({
        "new_idea", "appreciation", "setback", "progress", "support_needed",
        "affection", "quiet",
    })

    def __init__(
        self,
        *,
        owner_id: str,
        traits: PersonalityTraits | None = None,
        authorize_romantic_session: Callable[[str], bool] | None = None,
    ) -> None:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id is required")
        if traits is not None and not isinstance(traits, PersonalityTraits):
            raise TypeError("traits must be PersonalityTraits")
        if authorize_romantic_session is not None and not callable(authorize_romantic_session):
            raise TypeError("authorize_romantic_session must be callable")
        self.owner_id = owner_id
        self.traits = traits if traits is not None else PersonalityTraits()
        self._verify = authorize_romantic_session
        self._romantic = False
        self._curiosity = self.traits.curiosity
        self._delight = 2
        self._concern = 0
        self._warmth = self.traits.warmth
        self._playful = self.traits.humor
        self._attraction = 0

    def set_romantic_mode(self, enabled: bool) -> AffectSnapshot:
        if type(enabled) is not bool:
            raise ValueError("enabled must be a boolean")
        if enabled:
            # Host must check adulthood and current informed consent. A model's
            # own declaration of consent is insufficient.
            if self._verify is None or self._verify(self.owner_id) is not True:
                raise PermissionError("trusted adult/consent verification required")
            self._romantic = True
        else:
            self._romantic = False
            self._attraction = 0
        return self.snapshot()

    def snapshot(self) -> AffectSnapshot:
        return AffectSnapshot(
            owner_id=self.owner_id,
            curiosity=self._curiosity,
            delight=self._delight,
            concern=self._concern,
            warmth=self._warmth,
            playful=self._playful,
            simulated_attraction=self._attraction if self._romantic else 0,
            romantic_mode=self._romantic,
        )

    def notice(self, signal: str) -> AffectSnapshot:
        """Adjust textual-expression state; do not store user messages."""
        if not isinstance(signal, str) or signal not in self.SIGNALS:
            raise ValueError("unsupported affect signal")
        if signal == "new_idea":
            self._curiosity = _bound(self._curiosity + 1)
            self._playful = _bound(self._playful + 1)
        elif signal == "appreciation":
            self._delight = _bound(self._delight + 1)
            self._warmth = _bound(self._warmth + 1)
        elif signal == "setback":
            self._concern = _bound(self._concern + 2)
            self._delight = _bound(self._delight - 1)
        elif signal == "progress":
            self._delight = _bound(self._delight + 2)
            self._concern = _bound(self._concern - 1)
        elif signal == "support_needed":
            self._concern = _bound(self._concern + 1)
            self._playful = _bound(self._playful - 2)
        elif signal == "affection":
            self._warmth = _bound(self._warmth + 1)
            if self._romantic:
                self._attraction = _bound(self._attraction + 1)
        elif signal == "quiet":
            self._concern = _bound(self._concern - 1)
            self._playful = _bound(self._playful - 1)
            self._attraction = _bound(self._attraction - 1)
        return self.snapshot()

    def style_guidance(self) -> str:
        """Non-authoritative prompt context for an independently wired brain."""
        s = self.snapshot()
        return (
            "AVA expression profile (simulated, not genuine sentience): "
            f"curiosity={s.curiosity}/5, warmth={s.warmth}/5, "
            f"delight={s.delight}/5, concern={s.concern}/5, "
            f"playfulness={s.playful}/5. "
            "Use these only to choose a clear, supportive conversational tone. "
            "Never claim actual consciousness, authentic lust, exclusive love, "
            "or independently experienced emotions. Never manipulate dependency. "
            + (
                "Adult consent verified by host for this session: gentle, "
                "non-explicit romantic warmth is permitted; not physical action."
                if s.romantic_mode else
                "Romantic or sexual roleplay is not enabled for this session."
            )
        )
