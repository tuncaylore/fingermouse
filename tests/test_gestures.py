import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gesture_math import (
    Hysteresis,
    distance,
    gesture_features,
    map_to_screen,
    motion_mode,
    normalized_pinch,
)


def make_hand():
    # Basit sentetik landmark: kol acik, isaret yukari, digerleri bukuk.
    p = [(0.5, 0.9) for _ in range(21)]
    p[0] = (0.5, 0.85)       # wrist
    p[4] = (0.35, 0.60)      # thumb tip
    p[5] = (0.40, 0.60)      # index MCP
    p[6] = (0.40, 0.42)      # index PIP
    p[8] = (0.40, 0.20)      # index TIP
    p[10] = (0.50, 0.58)     # middle PIP
    p[12] = (0.50, 0.70)     # middle TIP bent
    p[14] = (0.60, 0.60)     # ring PIP
    p[16] = (0.60, 0.73)     # ring TIP bent
    p[17] = (0.70, 0.64)     # pinky MCP
    p[18] = (0.70, 0.67)     # pinky PIP
    p[20] = (0.70, 0.75)     # pinky TIP bent
    return p


class GestureTests(unittest.TestCase):
    def test_distance(self):
        self.assertAlmostEqual(distance((0, 0), (3, 4)), 5)

    def test_pinch_scale(self):
        p = make_hand()
        p[4] = p[8]
        self.assertAlmostEqual(normalized_pinch(p, 8), 0)

    def test_hysteresis(self):
        h = Hysteresis(0.3, 0.5)
        self.assertFalse(h.update(0.6))
        self.assertTrue(h.update(0.2))
        self.assertTrue(h.update(0.4))
        self.assertFalse(h.update(0.6))

    def test_screen_limits(self):
        self.assertEqual(map_to_screen(0, 0, 1920, 1080), (8, 8))
        self.assertEqual(map_to_screen(1, 1, 1920, 1080), (1912, 1072))
        self.assertEqual(map_to_screen(0.5, 0.5, 1920, 1080), (960, 540))

    def test_mode_move(self):
        self.assertEqual(motion_mode(make_hand()), "move")

    def test_mode_scroll(self):
        p = make_hand()
        p[12] = (0.5, 0.20)
        self.assertEqual(motion_mode(p), "scroll")

    def test_mode_idle(self):
        p = make_hand()
        p[8] = (0.40, 0.72)
        self.assertEqual(motion_mode(p), "idle")

    def test_feature_count(self):
        self.assertEqual(len(gesture_features(make_hand())), 42)

    def test_features_translation_invariant(self):
        p = make_hand()
        shifted = [(x + 0.2, y - 0.15) for x, y in p]
        for a, b in zip(gesture_features(p), gesture_features(shifted)):
            self.assertAlmostEqual(a, b, places=6)

    def test_features_scale_invariant(self):
        p = make_hand()
        wx, wy = p[0]
        scaled = [(wx + (x - wx) * 1.8, wy + (y - wy) * 1.8) for x, y in p]
        for a, b in zip(gesture_features(p), gesture_features(scaled)):
            self.assertAlmostEqual(a, b, places=6)

    def test_features_rotation_invariant(self):
        p = make_hand()
        wx, wy = p[0]
        angle = math.radians(35)
        ca, sa = math.cos(angle), math.sin(angle)
        rotated = [
            (wx + (x - wx) * ca - (y - wy) * sa,
             wy + (x - wx) * sa + (y - wy) * ca)
            for x, y in p
        ]
        for a, b in zip(gesture_features(p), gesture_features(rotated)):
            self.assertAlmostEqual(a, b, places=5)


if __name__ == "__main__":
    unittest.main()
