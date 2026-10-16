import unittest

from gate.gate import GateConfig, InterjectionGate
from gate.schema import Decision


def speak(conf=0.9):
    return Decision(True, "suggest", conf)


class GateTests(unittest.TestCase):
    def test_silent_decision_blocked(self):
        g = InterjectionGate()
        self.assertEqual(g.evaluate(Decision(False, None, 0.99), 0).reason, "silent_decision")

    def test_threshold_boundary(self):
        g = InterjectionGate(GateConfig(threshold=0.7))
        self.assertFalse(g.evaluate(speak(0.69), 0).allowed)
        self.assertTrue(g.evaluate(speak(0.70), 0).allowed)

    def test_cooldown(self):
        g = InterjectionGate(GateConfig(cooldown_s=60))
        self.assertTrue(g.evaluate(speak(), 0).allowed)
        self.assertEqual(g.evaluate(speak(), 30).reason, "cooldown")
        self.assertTrue(g.evaluate(speak(), 61).allowed)

    def test_budget_exhaustion_and_window_expiry(self):
        g = InterjectionGate(GateConfig(cooldown_s=0, budget_max=2, budget_window_s=100))
        self.assertTrue(g.evaluate(speak(), 0).allowed)
        self.assertTrue(g.evaluate(speak(), 10).allowed)
        self.assertEqual(g.evaluate(speak(), 20).reason, "budget_exhausted")
        self.assertTrue(g.evaluate(speak(), 111).allowed)


if __name__ == "__main__":
    unittest.main()
