"""Decision context and output model used by the gate."""
from dataclasses import dataclass
from typing import Literal, Optional

QUESTION = "Would a thoughtful teammate interject right now?"
KIND_QUESTION = "If interjecting, what kind of response would help most?"

Kind = Literal["correct", "suggest", "ask"]


@dataclass(frozen=True)
class State:
    secs_since_last_failure: Optional[float]
    is_editing: bool
    inspecting_error: bool
    repeat_count: int
    secs_since_last_spoke: Optional[float]


@dataclass(frozen=True)
class Context:
    now: float
    recent_events: tuple
    state: State


@dataclass(frozen=True)
class Decision:
    speak: bool
    kind: Optional[Kind]
    confidence: float
