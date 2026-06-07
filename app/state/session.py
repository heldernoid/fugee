"""app/state/session.py — interview state machine + session manager.

The interview follows a strict, forward-only state machine. Once the person
has moved forward, earlier answers are append-only — backward transitions
raise ``ValueError`` (CLAUDE.md Critical Rule 3; ARCHITECTURE.md §3).

Session state is in-memory only for the hackathon: no database, no external
logging of personal data (ARCHITECTURE.md §Security and Privacy).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional


class State(IntEnum):
    """Ordered interview / flow states. Order defines forward direction."""

    LANGUAGE_SELECT = 0
    INTAKE = 1
    SITUATION = 2
    HISTORY = 3
    GOALS = 4
    REVIEW = 5
    ASSESSMENT = 6
    RECOMMENDATIONS = 7
    DOCUMENTS = 8
    COMPLETE = 9

    @property
    def label(self) -> str:
        return self.name


# Allowed forward transitions: each state may advance to the next, or stay put
# (idempotent re-entry, e.g. re-rendering the same phase).
_NEXT: dict[State, State] = {
    State.LANGUAGE_SELECT: State.INTAKE,
    State.INTAKE: State.SITUATION,
    State.SITUATION: State.HISTORY,
    State.HISTORY: State.GOALS,
    State.GOALS: State.REVIEW,
    State.REVIEW: State.ASSESSMENT,
    State.ASSESSMENT: State.RECOMMENDATIONS,
    State.RECOMMENDATIONS: State.DOCUMENTS,
    State.DOCUMENTS: State.COMPLETE,
    State.COMPLETE: State.COMPLETE,
}


@dataclass
class Interview:
    origin_country: Optional[str] = None
    current_country: Optional[str] = None
    persecution_types: list[str] = field(default_factory=list)
    immediate_danger: Optional[bool] = None
    family_situation: Optional[str] = None
    documents_available: list[str] = field(default_factory=list)
    languages_spoken: list[str] = field(default_factory=list)
    destination_preferences: list[str] = field(default_factory=list)
    prior_claims: Optional[bool] = None
    displacement_duration: Optional[str] = None
    free_text_history: Optional[str] = None


@dataclass
class Assessment:
    convention_grounds: list[str] = field(default_factory=list)
    risk_level: Optional[str] = None  # "high" | "moderate" | "low"
    reasoning_trace: str = ""
    recommended_countries: list[dict] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SessionState:
    """A single person's interview session. In-memory only."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    language: Optional[str] = None
    state: State = State.LANGUAGE_SELECT
    interview: Interview = field(default_factory=Interview)
    assessment: Assessment = field(default_factory=Assessment)
    selected_country: Optional[str] = None
    messages: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    # -- state machine ---------------------------------------------------

    def can_transition(self, target: State) -> bool:
        """True iff ``target`` is the current state or its sole successor."""
        target = State(target)
        if target == self.state:
            return True
        return _NEXT.get(self.state) == target and target != self.state

    def transition_to(self, target: State) -> State:
        """Advance the state machine. Forward-only.

        Raises ``ValueError`` on any backward move or a skipped state
        (e.g. REVIEW -> SITUATION, or INTAKE -> ASSESSMENT).
        """
        target = State(target)
        if target == self.state:
            return self.state
        if not self.can_transition(target):
            raise ValueError(
                f"Illegal transition {self.state.label} -> {target.label}: "
                "the interview is append-only and forward-only."
            )
        self.state = target
        self.updated_at = _now_iso()
        return self.state

    def advance(self) -> State:
        """Move to the next state in sequence."""
        return self.transition_to(_NEXT[self.state])

    # -- serialisation ---------------------------------------------------

    def touch(self) -> None:
        self.updated_at = _now_iso()


class SessionManager:
    """Holds active sessions for the running process (in-memory)."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(self) -> SessionState:
        session = SessionState()
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


__all__ = [
    "State",
    "Interview",
    "Assessment",
    "SessionState",
    "SessionManager",
]
