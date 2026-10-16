import contextlib
import json
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from replay.runner import run


class ReplayTests(unittest.TestCase):
    def test_30_event_log_has_repeatable_gate_outcomes(self):
        log = Path(__file__).parents[1] / "replay" / "logs" / "sample_coding.jsonl"
        outputs = []
        counts = []
        for _ in range(2):
            output = StringIO()
            response = Mock()
            response.json.return_value = {"answers": {
                "speak": {"noul": 0.1}, "kind": {"choice": "suggest"}
            }}
            with patch("gate.decider.requests.post", return_value=response):
                with contextlib.redirect_stdout(output):
                    counts.append(run(str(log), threshold=0.7))
            outputs.append(output.getvalue())

        self.assertEqual(counts[0]["checks"], 30)
        self.assertEqual(counts[0], counts[1])
        self.assertEqual(outputs[0], outputs[1])

    def test_replay_calls_responder_only_for_gate_passes(self):
        class FakeResponder:
            def generate(self, decision, context):
                return f"response for {decision.kind}"

        log = Path(__file__).parents[1] / "replay" / "logs" / "sample_coding.jsonl"
        output = StringIO()
        response = Mock()
        response.json.return_value = {"answers": {
            "speak": {"noul": 0.9}, "kind": {"choice": "suggest"}
        }}
        with patch("gate.decider.requests.post", return_value=response):
            with contextlib.redirect_stdout(output):
                counts = run(str(log), threshold=0.5, responder=FakeResponder())

        records = [json.loads(line) for line in output.getvalue().splitlines() if line.startswith("{")]
        self.assertTrue(records)
        for record in records:
            self.assertEqual(record["bedrock_called"], record["gate"]["allowed"])
            self.assertEqual(bool(record["bedrock_text"]), record["gate"]["allowed"])
        self.assertEqual(counts["bedrock_calls"], sum(r["gate"]["allowed"] for r in records))


if __name__ == "__main__":
    unittest.main()
