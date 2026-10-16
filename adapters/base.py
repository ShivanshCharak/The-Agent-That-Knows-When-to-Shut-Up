import json
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(frozen=True)
class Event:
    """Normalized event shared by live adapters and recorded replays."""

    ts: float
    kind: str
    payload: dict = field(default_factory=dict)


def load_jsonl(path: str) -> Iterator[Event]:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                yield Event(ts=float(d["ts"]), kind=d["kind"], payload=d.get("payload", {}))
