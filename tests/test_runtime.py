import queue
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fingermouse as app
from gesture_learning import MIN_SAMPLES, GestureModel


class FakeCapture:
    def __init__(self):
        self.frames = queue.Queue()

    def read(self):
        frame = self.frames.get(timeout=2)
        if isinstance(frame, Exception):
            raise frame
        return frame is not None, frame

    def release(self):
        pass


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.capture = FakeCapture()
        self.camera = app.LatestFrameCamera(self.capture)

    def tearDown(self):
        self.capture.frames.put(None)
        self.camera.release()
        self.assertFalse(self.camera._thread.is_alive())

    def test_publishes_new_frame_without_copy(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.capture.frames.put(frame)
        ok, received = self.camera.read()
        self.assertTrue(ok)
        self.assertIs(received, frame)
        app.cv2.flip(received, 1)[:] = 255
        self.assertFalse(frame.any())

    def test_does_not_reuse_a_stale_frame(self):
        self.capture.frames.put(np.zeros((2, 2, 3), dtype=np.uint8))
        self.assertTrue(self.camera.read()[0])
        self.assertEqual(self.camera.read(timeout=0.01), (False, None))

    def test_keeps_latest_frame_only(self):
        first = np.zeros((2, 2, 3), dtype=np.uint8)
        last = np.ones((2, 2, 3), dtype=np.uint8)
        self.capture.frames.put(first)
        self.capture.frames.put(last)
        with self.camera._condition:
            self.assertTrue(self.camera._condition.wait_for(
                lambda: self.camera._sequence == 2, timeout=1.0
            ))
        self.assertIs(self.camera.read()[1], last)

    def test_reports_capture_exception(self):
        error = OSError("camera disconnected")
        self.capture.frames.put(error)
        with self.assertRaises(RuntimeError) as raised:
            self.camera.read()
        self.assertIs(raised.exception.__cause__, error)

    def test_reports_failed_read(self):
        self.capture.frames.put(None)
        self.assertEqual(self.camera.read(), (False, None))


class DoubleClickTests(unittest.TestCase):
    def setUp(self):
        self.mouse_patch = patch.object(app, "FastMouse")
        mouse = self.mouse_patch.start().return_value
        mouse.width, mouse.height = 1920, 1080
        self.addCleanup(self.mouse_patch.stop)
        self.click_patch = patch.object(app.pyautogui, "click")
        self.click = self.click_patch.start()
        self.addCleanup(self.click_patch.stop)
        self.controller = app.MouseController()

    def test_two_left_clicks_without_sleep_or_drag(self):
        with patch.object(app.time, "monotonic", return_value=10.0), \
                patch.object(app.time, "sleep") as sleep, \
                patch.object(app.pyautogui, "mouseDown") as mouse_down:
            self.controller.trigger("double_click")
            self.assertEqual(self.click.call_count, 1)
            self.controller.complete_pending_click(10.05)
            self.assertEqual(self.click.call_count, 1)
            self.controller.complete_pending_click(10.1)
            self.controller.complete_pending_click(11.0)
            self.assertEqual(self.click.call_count, 2)
            self.assertTrue(all(call.kwargs == {"button": "left"} for call in self.click.call_args_list))
            sleep.assert_not_called()
            mouse_down.assert_not_called()

    def test_release_cancels_second_click(self):
        self.controller.trigger("double_click")
        self.controller.release()
        self.controller.complete_pending_click(float("inf"))
        self.assertEqual(self.click.call_count, 1)

    def test_second_click_checks_failsafe(self):
        self.controller.trigger("double_click")
        self.controller.mouse.check_failsafe.side_effect = app.pyautogui.FailSafeException
        with self.assertRaises(app.pyautogui.FailSafeException):
            self.controller.complete_pending_click(float("inf"))
        self.controller.release()
        self.assertEqual(self.click.call_count, 1)
        self.assertIsNone(self.controller.pending_double_click)

    def test_existing_single_click_unchanged(self):
        self.controller.trigger("left_click")
        self.controller.complete_pending_click(float("inf"))
        self.click.assert_called_once_with(button="left")

    def test_menu_key_and_training_validation(self):
        self.assertEqual(app.TRAINING_KEYS[ord("6")], "double_click")
        points = [SimpleNamespace(x=0.1 + i * 0.01, y=0.2 + (i % 4) * 0.03) for i in range(21)]
        model = GestureModel()
        session = app.TrainingSession(model, "double_click")
        session._set_phase("record")
        for _ in range(MIN_SAMPLES):
            session.handle_landmarks(points)
        session._finish_recording()
        self.assertEqual(session.phase, "verify")
        self.assertFalse(model.is_validated("double_click"))
        for _ in range(session.VERIFY_FRAMES):
            session.handle_landmarks(points)
        session.tick()
        self.assertEqual(session.phase, "done")
        self.assertTrue(model.is_validated("double_click"))

    def test_held_gesture_fires_once_and_release_rearms(self):
        model = Mock()
        model.validated_actions.return_value = ["double_click"]
        model.predict.return_value = ("double_click", 1.0, 1.0)
        controller = Mock()
        runtime = app.CustomGestureRuntime(model, controller)
        with patch.object(app, "gesture_features", return_value=[0.0] * 42):
            for i in range(20):
                runtime.update([], 10.0 + i * 0.1)
            controller.trigger.assert_called_once_with("double_click")
            model.predict.return_value = (None, 0.0, 0.0)
            runtime.update([], 13.0)
            model.predict.return_value = ("double_click", 1.0, 1.0)
            for i in range(app.CUSTOM_HOLD_FRAMES):
                runtime.update([], 14.0 + i * 0.1)
            self.assertEqual(controller.trigger.call_count, 2)

    def test_unarmed_close_window_does_not_fire(self):
        model = Mock()
        model.validated_actions.return_value = ["close_window"]
        model.predict.return_value = ("close_window", 1.0, 1.0)
        controller = Mock()
        runtime = app.CustomGestureRuntime(model, controller)
        with patch.object(app, "gesture_features", return_value=[0.0] * 42):
            for i in range(20):
                runtime.update([], 10.0 + i * 0.1)
        controller.trigger.assert_not_called()

    def test_t_menu_starts_double_click_training(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        model = GestureModel()
        with patch.object(app, "download_model"), \
                patch.object(app, "GestureModel", return_value=model), \
                patch.object(app, "MouseController"), \
                patch.object(app, "open_camera"), \
                patch.object(app, "LatestFrameCamera") as camera, \
                patch.object(app, "TrainingSession", wraps=app.TrainingSession) as training, \
                patch.object(app.mp.tasks.vision.HandLandmarker, "create_from_options") as landmarker, \
                patch.multiple(app.cv2, namedWindow=Mock(), resizeWindow=Mock(),
                               imshow=Mock(), destroyAllWindows=Mock(),
                               getWindowProperty=Mock(return_value=1),
                               waitKey=Mock(side_effect=[ord("t"), ord("6"), 27, 27, 27])), \
                patch.object(sys, "argv", ["fingermouse.py"]):
            camera.return_value.read.return_value = (True, frame)
            detector = landmarker.return_value.__enter__.return_value
            detector.detect_for_video.return_value.hand_landmarks = []
            app.main()
            training.assert_called_once_with(model, "double_click")
            camera.return_value.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
