import json
from pathlib import Path
import unittest

from adapters.base import Event
from gate.context import ContextBuilder
from gate.rules import should_skip


LOG_DIR = Path(__file__).parents[1] / "replay" / "logs"


class ScenarioTests(unittest.TestCase):
    def test_labeled_scenarios_keep_declared_context_dependencies(self):
        labels = [json.loads(line) for line in (LOG_DIR / "scenario_labels.jsonl").read_text().splitlines()]
        self.assertEqual(len(labels), 6)
        for label in labels:
            with self.subTest(session=label["session"]):
                rows = [json.loads(line) for line in (LOG_DIR / f"{label['session']}.jsonl").read_text().splitlines()]
                events = [Event(float(row["ts"]), row["kind"], row.get("payload", {})) for row in rows]
                self.assertEqual(len(events), label["tick"])
                ctx = ContextBuilder()
                context_at_label = None
                for tick, event in enumerate(events, start=1):
                    # Rules skip a model check, but the event remains in the context window.
                    ctx.update(event)
                    if tick == label["tick"]:
                        context_at_label = ctx.snapshot(event.ts)

                self.assertFalse(should_skip(events[label["tick"] - 1]))
                available = context_at_label.recent_events
                for dependency_tick in label["depends_on"]:
                    self.assertIn(events[dependency_tick - 1], available)


if __name__ == "__main__":
    unittest.main()
