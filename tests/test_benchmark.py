import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from bench.judge import BedrockJudge
from bench.run import _classification_metrics
from gate.context import ContextBuilder


ROOT = Path(__file__).parents[1]


class BenchmarkTests(unittest.TestCase):
    def test_hand_labels_cover_40_to_60_real_moments(self):
        label_path = ROOT / "bench" / "labels.jsonl"
        labels = [json.loads(line) for line in label_path.read_text().splitlines()]
        self.assertGreaterEqual(len(labels), 40)
        self.assertLessEqual(len(labels), 60)
        for label in labels:
            self.assertEqual(set(label), {"log_id", "tick", "should_speak", "kind"})
            rows = (ROOT / "replay" / "logs" / f"{label['log_id']}.jsonl").read_text().splitlines()
            event = json.loads(rows[label["tick"] - 1])
            self.assertNotEqual(event["kind"], "file_open")
            if label["should_speak"]:
                self.assertIn(label["kind"], {"correct", "suggest", "ask"})
            else:
                self.assertIsNone(label["kind"])

    def test_bedrock_judge_parses_structured_output_and_usage(self):
        client = Mock()
        client.converse.return_value = {
            "output": {"message": {"content": [{"text": '{"should_speak": true, "kind": "ask"}'}]}},
            "usage": {"inputTokens": 32, "outputTokens": 9},
        }
        judge = BedrockJudge("test-model", client=client)
        context = ContextBuilder().snapshot(1)

        result = judge.decide(context)

        self.assertTrue(result.should_speak)
        self.assertEqual(result.kind, "ask")
        self.assertEqual((result.input_tokens, result.output_tokens), (32, 9))
        client.converse.assert_called_once()

    def test_metrics_include_speak_and_joint_accuracy(self):
        gold = [
            {"should_speak": True, "kind": "ask"},
            {"should_speak": False, "kind": None},
        ]
        predictions = [
            {"should_speak": True, "kind": "ask", "latency_ms": 10},
            {"should_speak": True, "kind": "suggest", "latency_ms": 20},
        ]
        result = _classification_metrics(gold, predictions)
        self.assertEqual(result["speak_accuracy"], 0.5)
        self.assertEqual(result["joint_accuracy"], 0.5)
        self.assertEqual(result["kind_accuracy_on_labeled_positive"], 1.0)
        self.assertEqual(result["mean_latency_ms"], 15)


if __name__ == "__main__":
    unittest.main()
