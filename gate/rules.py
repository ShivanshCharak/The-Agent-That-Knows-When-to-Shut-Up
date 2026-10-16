"""Cheap deterministic pre-filter. Events dropped here never reach Decider."""
from adapters.base import Event

SKIP_KINDS = {"file_open"}


def should_skip(event: Event) -> bool:
    return event.kind in SKIP_KINDS
