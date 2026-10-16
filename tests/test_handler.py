import sys
import types
import unittest
from unittest.mock import Mock

from gate.bedrock import BedrockResponder
from gate.context import ContextBuilder
from gate.gate import GateConfig, InterjectionGate
from gate.handler import InterjectionHandler, make_strands_intervention_handler
from gate.schema import Decision


class FixedDecider:
    def __init__(self, decision):
        self.decision = decision

    def decide(self, question, context):
        return self.decision


class FakeResponder:
    def __init__(self):
        self.calls = []

    def generate(self, decision, context):
        self.calls.append((decision, context))
        return "Try inspecting the repeated error first."


class HandlerTests(unittest.TestCase):
    def test_gate_failure_never_calls_bedrock_responder(self):
        responder = FakeResponder()
        handler = InterjectionHandler(
            FixedDecider(Decision(False, None, 0.99)),
            InterjectionGate(GateConfig(threshold=0.7)),
            responder,
        )

        result = handler.handle(ContextBuilder().snapshot(1))

        self.assertFalse(result.allowed)
        self.assertFalse(result.bedrock_called)
        self.assertEqual(responder.calls, [])
        self.assertEqual(handler.bedrock_calls, 0)

    def test_gate_pass_calls_responder_and_returns_text(self):
        responder = FakeResponder()
        handler = InterjectionHandler(
            FixedDecider(Decision(True, "suggest", 0.85)), InterjectionGate(), responder
        )

        result = handler.handle(ContextBuilder().snapshot(1))

        self.assertTrue(result.allowed)
        self.assertTrue(result.bedrock_called)
        self.assertEqual(result.response, "Try inspecting the repeated error first.")
        self.assertEqual(len(responder.calls), 1)

    def test_bedrock_response_uses_converse_but_test_does_not_contact_aws(self):
        client = Mock()
        client.converse.return_value = {
            "output": {"message": {"content": [{"text": "Check the retry condition."}]}}
        }
        responder = BedrockResponder("test-model", client=client)
        decision = Decision(True, "correct", 0.9)
        context = ContextBuilder().snapshot(1)

        result = responder.generate(decision, context)

        self.assertEqual(result, "Check the retry condition.")
        client.converse.assert_called_once()
        self.assertEqual(client.converse.call_args.kwargs["modelId"], "test-model")

    def test_strands_factory_returns_guide_only_when_gate_passes(self):
        strands = types.ModuleType("strands")
        interventions = types.ModuleType("strands.interventions")

        class Base:
            pass

        class Proceed:
            pass

        class Guide:
            def __init__(self, feedback):
                self.feedback = feedback

        interventions.InterventionHandler = Base
        interventions.Proceed = Proceed
        interventions.Guide = Guide
        responder = FakeResponder()
        core = InterjectionHandler(
            FixedDecider(Decision(True, "suggest", 0.9)), InterjectionGate(), responder
        )
        context = ContextBuilder().snapshot(1)
        sys.modules["strands"] = strands
        sys.modules["strands.interventions"] = interventions
        try:
            handler = make_strands_intervention_handler(core, lambda event: context)
            result = handler.before_model_call(object())
        finally:
            sys.modules.pop("strands", None)
            sys.modules.pop("strands.interventions", None)

        self.assertIsInstance(handler, Base)
        self.assertIsInstance(result, Guide)
        self.assertEqual(result.feedback, "Try inspecting the repeated error first.")


if __name__ == "__main__":
    unittest.main()
