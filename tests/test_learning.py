import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gesture_learning import MIN_SAMPLES, GestureModel


def base_vector(offset=0.0):
    return [offset + index * 0.01 for index in range(42)]


def noisy(vector, amount, sample_index):
    return [
        value + amount * (((index * 7 + sample_index * 13) % 11) - 5) / 5.0
        for index, value in enumerate(vector)
    ]


def fill(model, action, vector, amount=0.01, count=MIN_SAMPLES + 5):
    for sample_index in range(count):
        model.add_sample(action, noisy(vector, amount, sample_index))


class GestureModelTests(unittest.TestCase):
    def test_train_and_predict(self):
        model = GestureModel()
        fill(model, "left_click", base_vector())
        self.assertIn("left_click", model.trained_actions())
        ok, _ = model.evaluate("left_click")
        self.assertTrue(ok)
        action, confidence, _ = model.predict(base_vector())
        self.assertEqual(action, "left_click")
        self.assertGreater(confidence, 0.3)

    def test_rejects_unknown_gesture(self):
        model = GestureModel()
        fill(model, "left_click", base_vector())
        action, _, _ = model.predict([20.0] * 42)
        self.assertIsNone(action)

    def test_separates_two_actions(self):
        model = GestureModel()
        fill(model, "left_click", base_vector())
        fill(model, "right_click", base_vector(0.7))
        left, _, _ = model.predict(base_vector())
        right, _, _ = model.predict(base_vector(0.7))
        self.assertEqual(left, "left_click")
        self.assertEqual(right, "right_click")
        ok, _ = model.evaluate("left_click")
        self.assertTrue(ok)

    def test_not_enough_samples(self):
        model = GestureModel()
        fill(model, "left_click", base_vector(), count=MIN_SAMPLES - 1)
        ok, _ = model.evaluate("left_click")
        self.assertFalse(ok)
        self.assertNotIn("left_click", model.trained_actions())

    def test_clear_action(self):
        model = GestureModel()
        fill(model, "left_click", base_vector())
        model.clear("left_click")
        self.assertEqual(model.count("left_click"), 0)
        self.assertEqual(model.trained_actions(), [])

    def test_validation_requires_confirmation(self):
        model = GestureModel()
        fill(model, "left_click", base_vector())
        self.assertEqual(model.validated_actions(), [])
        model.mark_validated("left_click")
        self.assertEqual(model.validated_actions(), ["left_click"])
        model.add_sample("left_click", base_vector())
        self.assertEqual(model.validated_actions(), [])

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gestures.json"
            model = GestureModel(path)
            fill(model, "left_click", base_vector())
            model.mark_validated("left_click")
            model.save()
            loaded = GestureModel(path)
            self.assertEqual(loaded.count("left_click"), MIN_SAMPLES + 5)
            self.assertEqual(loaded.validated_actions(), ["left_click"])
            action, _, _ = loaded.predict(
                base_vector(), actions=loaded.validated_actions()
            )
            self.assertEqual(action, "left_click")

    def test_double_click_round_trip_preserves_old_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gestures.json"
            model = GestureModel(path)
            actions = ("left_click", "right_click", "close_window", "double_click")
            for index, action in enumerate(actions):
                fill(model, action, base_vector(index))
                model.mark_validated(action)
            model.save()
            loaded = GestureModel(path)
            self.assertEqual(loaded.validated_actions(), list(actions))
            for index, action in enumerate(actions):
                self.assertEqual(loaded.predict(base_vector(index))[0], action)
            loaded.clear("double_click")
            self.assertEqual(loaded.validated_actions(), list(actions[:-1]))

    def test_optimized_distances_match_previous_norm(self):
        model = GestureModel()
        for index, action in enumerate(("left_click", "right_click", "double_click")):
            fill(model, action, base_vector(index * 0.2))
        vectors = [base_vector(offset) for offset in (0.0, 0.001, 0.1, 0.2, 0.4, 20.0)]
        for vector in vectors:
            array = np.asarray(vector, dtype=np.float32)
            for action in model.trained_actions():
                centroid, radius, _ = model._stats_for(action)
                delta = array - centroid
                previous = float(np.linalg.norm(delta)) / radius
                optimized = float(np.dot(delta, delta)) ** 0.5 / radius
                self.assertAlmostEqual(previous, optimized, delta=max(1e-6, previous * 1e-6))

    def test_prediction_cache_invalidates_after_retraining(self):
        model = GestureModel()
        fill(model, "double_click", base_vector())
        model.predict(base_vector())
        model.clear("double_click")
        fill(model, "double_click", base_vector(2.0))
        self.assertIsNone(model.predict(base_vector())[0])
        self.assertEqual(model.predict(base_vector(2.0))[0], "double_click")


if __name__ == "__main__":
    unittest.main()
