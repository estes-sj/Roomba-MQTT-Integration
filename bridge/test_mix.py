import unittest
from roomba_gamepad import mix

class MixTest(unittest.TestCase):
    def test_deadzone(self):
        self.assertEqual(mix(0.05, -0.05, 300), (0, 0))
    def test_forward_back(self):
        self.assertEqual(mix(0, 1, 300), (300, 300))
        self.assertEqual(mix(0, -1, 300), (-300, -300))
    def test_pivot(self):
        self.assertEqual(mix(1, 0, 250), (150, -150))
        self.assertEqual(mix(-1, 0, 250), (-150, 150))
    def test_arc_never_exceeds_max(self):
        l, r = mix(1, 1, 500)
        self.assertLessEqual(max(abs(l), abs(r)), 500)
        self.assertGreater(l, r)
    def test_clamped_to_oi_limit(self):
        self.assertEqual(mix(0, 1, 900), (500, 500))

if __name__ == "__main__":
    unittest.main()
