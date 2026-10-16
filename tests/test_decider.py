import json
import unittest
from unittest.mock import Mock, patch

from adapters.base import Event
from gate.context import ContextBuilder
from gate.decider import HttpDecider


class HttpDeciderTests(unittest.TestCase):
    @patch("gate.decider.requests.post")
    def test_posts_typed_questions_and_maps_answers(self, post):
        response = Mock()
        response.json.return_value = {
            "answers": {
                "speak": {"type": "noul", "noul": 0.82},
                "kind": {"type": "choice", "choice": "suggest"},
            }
        }
        post.return_value = response
        context = ContextBuilder()
        context.update(Event(1, "edit", {"file": "app.py"}))

        decision = HttpDecider("http://localhost:8000/").decide(
            "Would a thoughtful teammate interject now?", context.snapshot(2)
        )

        self.assertTrue(decision.speak)
        self.assertEqual(decision.kind, "suggest")
        self.assertEqual(decision.confidence, 0.82)
        args, kwargs = post.call_args
        self.assertEqual(args[0], "http://localhost:8000/v1/systemone")
        self.assertEqual(kwargs["json"]["questions"]["speak"]["type"], "noul")
        self.assertEqual(kwargs["json"]["questions"]["kind"]["type"], "choice")
        self.assertIn('"is_editing":true', kwargs["json"]["state"])
        json.loads(kwargs["json"]["state"])
        response.raise_for_status.assert_called_once_with()

    @patch("gate.decider.requests.post")
    def test_probability_below_half_means_silent(self, post):
        response = Mock()
        response.json.return_value = {
            "answers": {
                "speak": {"type": "noul", "noul": 0.31},
                "kind": {"type": "choice", "choice": "ask"},
            }
        }
        post.return_value = response
        decision = HttpDecider("http://localhost:8000").decide(
            context=ContextBuilder().snapshot(0)
        )
        self.assertFalse(decision.speak)
        self.assertIsNone(decision.kind)
        self.assertEqual(decision.confidence, 0.31)

    @patch("gate.decider.requests.post")
    def test_sends_basic_auth_for_protected_decider_endpoint(self, post):
        response = Mock()
        response.json.return_value = {
            "answers": {
                "speak": {"type": "noul", "noul": 0.82},
                "kind": {"type": "choice", "choice": "ask"},
            }
        }
        post.return_value = response
        HttpDecider(
            "https://decider.example", auth=("demo-user", "demo-password")
        ).decide(context=ContextBuilder().snapshot(0))
        self.assertEqual(post.call_args.kwargs["auth"], ("demo-user", "demo-password"))

    @patch("gate.decider.requests.post")
    def test_rejects_incomplete_response(self, post):
        response = Mock()
        response.json.return_value = {"answers": {}}
        post.return_value = response
        with self.assertRaisesRegex(ValueError, "missing a valid"):
            HttpDecider("http://localhost:8000").decide(context=ContextBuilder().snapshot(0))


if __name__ == "__main__":
    unittest.main()
