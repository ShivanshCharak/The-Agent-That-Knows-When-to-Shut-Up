"""Builds the context window (last N events + state) passed to Decider."""
from collections import deque
from typing import Optional

from adapters.base import Event
from gate.schema import Context, State


class ContextBuilder:
    def __init__(self, window: int = 12):
        self._events = deque(maxlen=window)
        self._last_failure_ts: Optional[float] = None
        self._last_failure_error: Optional[str] = None
        self._repeat_count = 0
        self._inspecting = False
        self._is_editing = False
        self._last_spoke_ts: Optional[float] = None

    def update(self, event: Event) -> None:
        self._events.append(event)
        if event.kind == "test_fail":
            err = event.payload.get("error")
            self._repeat_count = self._repeat_count + 1 if err == self._last_failure_error else 1
            self._last_failure_error = err
            self._last_failure_ts = event.ts
            self._inspecting = False
            self._is_editing = False
        elif event.kind == "inspect_error":
            self._inspecting = True
            self._is_editing = False
        elif event.kind == "edit":
            self._is_editing = True
        elif event.kind == "test_pass":
            self._repeat_count = 0
            self._last_failure_ts = None
            self._last_failure_error = None
            self._inspecting = False
            self._is_editing = False
        elif event.kind in {"idle", "file_open"}:
            self._is_editing = False

    def mark_spoke(self, ts: float) -> None:
        self._last_spoke_ts = ts

    def snapshot(self, now: float) -> Context:
        state = State(
            secs_since_last_failure=None if self._last_failure_ts is None else now - self._last_failure_ts,
            is_editing=self._is_editing,
            inspecting_error=self._inspecting,
            repeat_count=self._repeat_count,
            secs_since_last_spoke=None if self._last_spoke_ts is None else now - self._last_spoke_ts,
        )
        return Context(now=now, recent_events=tuple(self._events), state=state)
