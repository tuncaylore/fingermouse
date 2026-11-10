"""FingerMouse - OpenCV + MediaPipe Tasks + PyAutoGUI Windows sanal fare.

run.bat dosyasina cift tiklayin. ESC = cikis, BOSLUK = duraklat.
T = hareket tanimlama menusu.
"""
from __future__ import annotations

import argparse
import ctypes
import os
from math import exp
from pathlib import Path
import sys
import threading
import time
import traceback
from urllib.request import urlopen

import cv2
import mediapipe as mp
import numpy as np
import pyautogui

try:
    from ctypes import wintypes
except (ImportError, ValueError):
    wintypes = None

from gesture_learning import (
    ACTION_LABELS,
    MIN_SAMPLES,
    GestureModel,
)
from gesture_math import (
    Hysteresis,
    INDEX_TIP,
    MIDDLE_TIP,
    THUMB_TIP,
    gesture_features,
    map_to_screen,
    motion_mode,
    normalized_pinch,
)

BASE = Path(__file__).resolve().parent
MODEL = BASE / "hand_landmarker.task"
GESTURE_FILE = BASE / "gestures.json"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
WINDOW_NAME = "FingerMouse | ESC: Cikis  SPACE: Duraklat  T: Hareket Tanimla"
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
CAMERA_FPS = 60
CUSTOM_HOLD_FRAMES = 4
CUSTOM_CONFIDENCE = 0.25
CUSTOM_COOLDOWN = 0.9
DOUBLE_CLICK_INTERVAL = 0.1
TRAINING_KEYS = {
    ord("1"): "left_click",
    ord("2"): "right_click",
    ord("6"): "double_click",
}
CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
]


def download_model():
    if MODEL.exists() and MODEL.stat().st_size > 1_000_000:
        return
    print("Ilk acilis: Google MediaPipe el takip modeli indiriliyor...")
    temp = MODEL.with_suffix(".part")
    try:
        with urlopen(MODEL_URL, timeout=45) as response, temp.open("wb") as dest:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                dest.write(block)
        if temp.stat().st_size <= 1_000_000:
            raise ValueError("Indirilen model beklenenden kucuk.")
        temp.replace(MODEL)
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def open_camera(index):
    backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if os.name == "nt" else [cv2.CAP_ANY]
    for backend in backends:
        cam = cv2.VideoCapture(index, backend)
        if cam.isOpened():
            cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cam.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            cam.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            cam.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
            cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret = False
            for _ in range(3):
                ret, _ = cam.read()
                if not ret:
                    break
            if ret:
                return cam
        cam.release()
    raise RuntimeError(
        f"Kamera {index} acilamadi. Kamera izinlerini ve diger uygulamalari kontrol edin. "
        "Harici kamera icin 'run.bat 1' deneyin."
    )


class LatestFrameCamera:
    def __init__(self, capture):
        self.capture = capture
        self._frame = None
        self._ok = False
        self._sequence = 0
        self._last_sequence = 0
        self._condition = threading.Condition()
        self._read_failed = False
        self._error = None
        self._running = True
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self):
        while self._running:
            try:
                ok, frame = self.capture.read()
            except Exception as exc:
                with self._condition:
                    self._error = exc
                    self._condition.notify_all()
                return
            with self._condition:
                self._ok = ok
                self._read_failed = not ok
                if ok:
                    self._frame = frame
                    self._sequence += 1
                else:
                    self._frame = None
                self._condition.notify_all()
            if not ok:
                time.sleep(0.01)

    def read(self, timeout=1.0):
        with self._condition:
            ready = self._condition.wait_for(
                lambda: self._sequence != self._last_sequence
                or self._read_failed
                or self._error is not None
                or not self._running,
                timeout=timeout,
            )
            if self._error is not None:
                raise RuntimeError("Kamera okuma isleminde hata olustu.") from self._error
            if ready and self._running and self._ok and self._frame is not None:
                self._last_sequence = self._sequence
                # Capture publishes new arrays; main() flips into a separate array.
                return True, self._frame
        return False, None

    def release(self):
        with self._condition:
            self._running = False
            self._condition.notify_all()
        self._thread.join(timeout=1.0)
        self.capture.release()


class FastMouse:
    def __init__(self):
        self.width, self.height = pyautogui.size()
        self._user32 = ctypes.windll.user32 if os.name == "nt" else None
        self._point = wintypes.POINT if self._user32 is not None and wintypes else None

    def position(self):
        if self._user32 is not None and self._point is not None:
            point = self._point()
            self._user32.GetCursorPos(ctypes.byref(point))
            return point.x, point.y
        position = pyautogui.position()
        return position.x, position.y

    def move(self, x, y):
        if self._user32 is not None:
            self._user32.SetCursorPos(int(x), int(y))
        else:
            pyautogui.moveTo(int(x), int(y), duration=0)

    def check_failsafe(self):
        x, y = self.position()
        if (
            (x <= 2 and y <= 2)
            or (x >= self.width - 3 and y <= 2)
            or (x <= 2 and y >= self.height - 3)
            or (x >= self.width - 3 and y >= self.height - 3)
        ):
            raise pyautogui.FailSafeException


def draw_landmarks(frame, landmarks, color=(78, 215, 175)):
    h, w = frame.shape[:2]
    points = [(int(p.x * w), int(p.y * h)) for p in landmarks]
    for a, b in CONNECTIONS:
        cv2.line(frame, points[a], points[b], color, 2, cv2.LINE_AA)
    for idx, p in enumerate(points):
        radius = 7 if idx in (THUMB_TIP, INDEX_TIP, MIDDLE_TIP) else 3
        cv2.circle(frame, p, radius, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, p, radius - 1, color, -1, cv2.LINE_AA)


def draw_hud(frame, status, mode, fps, paused):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 81), (18, 25, 39), -1)
    cv2.putText(frame, "FINGERMOUSE", (17, 30), cv2.FONT_HERSHEY_SIMPLEX,
                0.75, (94, 225, 197), 2, cv2.LINE_AA)
    cv2.putText(frame, f"{status} | {mode} | {fps:.0f} FPS", (17, 61),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (231, 236, 243), 1, cv2.LINE_AA)
    cv2.rectangle(frame, (0, h - 46), (w, h), (18, 25, 39), -1)
    cv2.putText(frame, "1 parmak: Hareket | Pinch: Sol tik | T: Hareket Tanimla",
                (12, h - 27), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (233, 239, 246), 1, cv2.LINE_AA)
    cv2.putText(frame, "Orta+bas: Sag tik | 2 parmak: Kaydir | SPACE: Pause | ESC: Quit",
                (12, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                (170, 185, 202), 1, cv2.LINE_AA)
    if paused:
        cv2.rectangle(frame, (170, 185), (470, 265), (11, 17, 28), -1)
        cv2.putText(frame, "DURAKLATILDI", (188, 234), cv2.FONT_HERSHEY_SIMPLEX,
                    0.96, (100, 213, 246), 2, cv2.LINE_AA)


def draw_menu(frame, runtime, model, message=""):
    cv2.rectangle(frame, (55, 90), (585, 430), (12, 18, 30), -1)
    cv2.rectangle(frame, (55, 90), (585, 430), (75, 105, 140), 2)
    cv2.putText(frame, "HAREKET TANIMLAMA", (80, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (94, 225, 197), 2, cv2.LINE_AA)
    def state(action):
        return "HAZIR" if model.is_validated(action) else "EGIT"

    lines = [
        f"1) Sol Tik       [{state('left_click')}] [{model.count('left_click')} ornek]",
        f"2) Sag Tik       [{state('right_click')}] [{model.count('right_click')} ornek]",
        f"3) Pencere Kapat [{'ACIK' if runtime.close_armed else 'KAPALI'}] "
        f"[{state('close_window')}] [{model.count('close_window')}]",
        "4) Tum egitimi sil  (iki kez bas)",
        "5) Pencere kapatmayi devre disi birak",
        f"6) Sol Cift Tik  [{state('double_click')}] [{model.count('double_click')} ornek]",
        f"X) Ozel hareketler: {'ACIK' if runtime.enabled else 'KAPALI'}",
        "T / ESC) Menuyu kapat",
    ]
    for index, line in enumerate(lines):
        cv2.putText(frame, line, (80, 166 + index * 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.53, (225, 232, 241), 1, cv2.LINE_AA)
    if message:
        cv2.putText(frame, message, (80, 388),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.41, (255, 160, 140), 1, cv2.LINE_AA)
    cv2.putText(frame, "Egitmek icin eylem numarasina basin.",
                (80, 412), cv2.FONT_HERSHEY_SIMPLEX, 0.44,
                (150, 190, 225), 1, cv2.LINE_AA)


def draw_training(frame, session):
    cv2.rectangle(frame, (55, 90), (585, 430), (12, 18, 30), -1)
    cv2.rectangle(frame, (55, 90), (585, 430), (75, 105, 140), 2)
    cv2.putText(frame, "HAREKET EGITIMI", (80, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (94, 225, 197), 2, cv2.LINE_AA)
    cv2.putText(frame, f"Eylem: {session.label}", (80, 175),
                cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 220, 120), 2, cv2.LINE_AA)
    cv2.putText(frame, session.status_text(), (80, 220),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 238, 248), 1, cv2.LINE_AA)
    if session.phase == "record":
        cv2.putText(frame, f"Toplanan ornek: {len(session.batch)}", (80, 258),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (160, 200, 235), 1, cv2.LINE_AA)
    elif session.phase == "verify":
        cv2.putText(frame, f"Guven: {session.last_confidence:.2f}", (80, 258),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (160, 200, 235), 1, cv2.LINE_AA)
    if session.message:
        cv2.putText(frame, session.message, (80, 305),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 160, 140), 1, cv2.LINE_AA)
    if session.phase == "retry":
        hint = "ENTER: tekrar dene | R: bu eylemi sifirla | ESC: iptal"
    elif session.phase == "done":
        hint = "ENTER: menuye don"
    else:
        hint = "ESC: iptal"
    cv2.putText(frame, hint, (80, 400),
                cv2.FONT_HERSHEY_SIMPLEX, 0.43, (150, 190, 225), 1, cv2.LINE_AA)


class MouseController:
    def __init__(self):
        self.mouse = FastMouse()
        self.width, self.height = self.mouse.width, self.mouse.height
        self.left = Hysteresis(0.30, 0.45)
        self.right = Hysteresis(0.31, 0.46)
        self.dragging = False
        self.right_latched = False
        self.last_right = 0.0
        self.previous_cursor = None
        self.scroll_previous_y = None
        self.scroll_accumulator = 0.0
        self.last_mode = None
        self.last_update = None
        self.pending_double_click = None

    def release(self):
        self.pending_double_click = None
        if self.dragging:
            try:
                pyautogui.mouseUp(button="left")
            except pyautogui.FailSafeException:
                pass
            self.dragging = False
        self.left.reset()
        self.right.reset()
        self.right_latched = False
        self.scroll_previous_y = None
        self.scroll_accumulator = 0.0
        self.previous_cursor = None
        self.last_mode = None
        self.last_update = None

    def trigger(self, action):
        self.mouse.check_failsafe()
        if action == "left_click":
            pyautogui.click(button="left")
        elif action == "double_click":
            pyautogui.click(button="left")
            self.pending_double_click = time.monotonic() + DOUBLE_CLICK_INTERVAL
        elif action == "right_click":
            pyautogui.click(button="right")
        elif action == "close_window":
            pyautogui.hotkey("alt", "f4")

    def complete_pending_click(self, now):
        if self.pending_double_click is not None and now >= self.pending_double_click:
            self.mouse.check_failsafe()
            self.pending_double_click = None
            pyautogui.click(button="left")

    def _delta_time(self):
        now = time.monotonic()
        if self.last_update is None:
            delta = 1.0 / 30.0
        else:
            delta = max(0.001, min(0.2, now - self.last_update))
        self.last_update = now
        return delta

    def update(self, landmarks):
        self.mouse.check_failsafe()
        delta = self._delta_time()
        ratio_left = normalized_pinch(landmarks, INDEX_TIP)
        ratio_right = normalized_pinch(landmarks, MIDDLE_TIP)
        left = self.left.update(ratio_left)
        right = self.right.update(ratio_right)
        right = right and not left
        mode = motion_mode(landmarks)
        if mode != self.last_mode:
            self.scroll_previous_y = None
            self.scroll_accumulator = 0.0
            self.last_mode = mode

        if not left and self.dragging:
            pyautogui.mouseUp(button="left")
            self.dragging = False

        if right and not self.right_latched and not self.dragging:
            if time.monotonic() - self.last_right >= 0.55:
                pyautogui.click(button="right")
                self.last_right = time.monotonic()
            self.right_latched = True
        if not right:
            self.right_latched = False

        if mode == "move" or left or self.dragging:
            px, py = map_to_screen(landmarks[INDEX_TIP].x,
                                   landmarks[INDEX_TIP].y,
                                   self.width, self.height)
            if self.previous_cursor is None:
                self.previous_cursor = (px, py)
            else:
                prevx, prevy = self.previous_cursor
                alpha = 1.0 - exp(-delta / 0.045)
                alpha = min(0.85, max(0.20, alpha))
                px = prevx + alpha * (px - prevx)
                py = prevy + alpha * (py - prevy)
                self.previous_cursor = (px, py)
            currx, curry = self.mouse.position()
            if abs(currx - px) + abs(curry - py) >= 2:
                self.mouse.move(px, py)
            if left and not self.dragging:
                pyautogui.mouseDown(button="left")
                self.dragging = True
            return "SOL TIK / SURUKLE" if self.dragging else "HAREKET"

        self.previous_cursor = None
        if mode == "scroll" and not left and not right:
            current_y = (landmarks[INDEX_TIP].y + landmarks[MIDDLE_TIP].y) / 2
            if self.scroll_previous_y is not None:
                delta_y = self.scroll_previous_y - current_y
                if abs(delta_y) < 0.40:
                    self.scroll_accumulator += delta_y * 1500
                    steps = int(self.scroll_accumulator)
                    if steps:
                        pyautogui.scroll(steps)
                        self.scroll_accumulator -= steps
            self.scroll_previous_y = current_y
            return "KAYDIR"
        self.scroll_previous_y = None
        if right:
            return "SAG TIK"
        return "BEKLIYOR"


class CustomGestureRuntime:
    def __init__(self, model, controller):
        self.model = model
        self.controller = controller
        self.enabled = True
        self.close_armed = False
        self.latched = False
        self.streak = 0
        self.last_action = None
        self.last_trigger = 0.0
        self.active = False

    def reset(self):
        self.latched = False
        self.streak = 0
        self.last_action = None
        self.active = False

    def update(self, landmarks, now):
        actions = self.model.validated_actions()
        if not self.enabled or not actions:
            self.reset()
            return None
        action, confidence, _ = self.model.predict(
            gesture_features(landmarks), actions=actions
        )
        if action is None or confidence < CUSTOM_CONFIDENCE:
            self.reset()
            return None
        if not self.active:
            self.active = True
            self.controller.release()
        if action != self.last_action:
            self.last_action = action
            self.streak = 0
            self.latched = False
        if not self.latched:
            self.streak += 1
            if self.streak >= CUSTOM_HOLD_FRAMES and now - self.last_trigger >= CUSTOM_COOLDOWN:
                if action != "close_window" or self.close_armed:
                    self.controller.trigger(action)
                    self.last_trigger = now
                self.latched = True
        return action


class TrainingSession:
    COUNTDOWN_SECONDS = 2.5
    RECORD_SECONDS = 2.0
    VERIFY_TIMEOUT = 6.0
    VERIFY_FRAMES = 8
    MIN_CONFIDENCE = 0.25

    def __init__(self, model, action):
        self.model = model
        self.action = action
        self.phase = "countdown"
        self.phase_start = time.monotonic()
        self.batch = []
        self.verify_hits = 0
        self.message = ""
        self.last_confidence = 0.0

    @property
    def label(self):
        return ACTION_LABELS.get(self.action, self.action)

    def _set_phase(self, phase):
        self.phase = phase
        self.phase_start = time.monotonic()
        self.batch.clear()
        self.verify_hits = 0

    def handle_landmarks(self, landmarks):
        if landmarks is None:
            return
        if self.phase == "record":
            self.batch.append(gesture_features(landmarks))
        elif self.phase == "verify":
            actions = [self.action] + [
                action
                for action in self.model.validated_actions()
                if action != self.action
            ]
            action, confidence, _ = self.model.predict(
                gesture_features(landmarks), actions=actions
            )
            self.last_confidence = confidence
            if action == self.action and confidence >= self.MIN_CONFIDENCE:
                self.verify_hits += 1
            else:
                self.verify_hits = max(0, self.verify_hits - 1)

    def tick(self):
        now = time.monotonic()
        if self.phase == "countdown":
            if now - self.phase_start >= self.COUNTDOWN_SECONDS:
                self._set_phase("record")
        elif self.phase == "record":
            if now - self.phase_start >= self.RECORD_SECONDS:
                self._finish_recording()
        elif self.phase == "verify":
            if self.verify_hits >= self.VERIFY_FRAMES:
                self.phase = "done"
                self.message = "Harika! Hareket ogrenildi."
                self.model.mark_validated(self.action)
                self.model.save()
            elif now - self.phase_start >= self.VERIFY_TIMEOUT:
                self.phase = "retry"
                self.message = "Hareket henuz taninmiyor. Tekrar deneyelim."

    def _finish_recording(self):
        if len(self.batch) < MIN_SAMPLES:
            self.phase = "retry"
            self.message = f"Yeterli ornek yok ({len(self.batch)}/{MIN_SAMPLES})."
            return
        self.model.add_samples(self.action, self.batch)
        ok, reason = self.model.evaluate(self.action)
        if ok:
            self._set_phase("verify")
            self.message = "Simdi ayni hareketi tekrar yapin."
        else:
            self.phase = "retry"
            self.message = reason

    def retry(self):
        self._set_phase("countdown")
        self.message = ""

    def status_text(self):
        if self.phase == "countdown":
            remaining = max(
                1,
                int(self.COUNTDOWN_SECONDS - (time.monotonic() - self.phase_start) + 0.999),
            )
            return f"Hazir olun: {remaining}"
        if self.phase == "record":
            return "Hareketi yapin ve sabit tutun"
        if self.phase == "verify":
            return f"Dogrulama: {self.verify_hits}/{self.VERIFY_FRAMES}"
        if self.phase == "retry":
            return "Tekrar gerekli"
        return "Tamamlandi"


def main():
    parser = argparse.ArgumentParser(description="FingerMouse kamera ile fare kontrolu")
    parser.add_argument("--camera", type=int, default=0, help="Kamera indeksi (0 veya 1)")
    args = parser.parse_args()
    download_model()
    pyautogui.PAUSE = 0
    pyautogui.FAILSAFE = True
    model = GestureModel(GESTURE_FILE)
    controller = MouseController()
    custom = CustomGestureRuntime(model, controller)
    cap = LatestFrameCamera(open_camera(args.camera))
    paused = False
    menu_open = False
    menu_message = ""
    close_confirm = False
    reset_confirm = False
    training = None
    last_time = time.monotonic()
    last_ts = -1
    fps = 0.0
    status = "EL BEKLENIYOR"
    print("Kamera acildi. ESC: cikis, SPACE: duraklat, T: hareket tanimla.")

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.55,
        min_tracking_confidence=0.55,
    )
    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
            cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW_NAME, FRAME_WIDTH, FRAME_HEIGHT)
            while True:
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("Kameradan goruntu alinamiyor. Kamerayi yeniden baglayin.")
                frame = cv2.flip(frame, 1)
                if frame.shape[1] != FRAME_WIDTH or frame.shape[0] != FRAME_HEIGHT:
                    frame = cv2.resize(
                        frame, (FRAME_WIDTH, FRAME_HEIGHT), interpolation=cv2.INTER_LINEAR
                    )
                current = time.monotonic()
                delta = current - last_time
                last_time = current
                if delta > 0:
                    instant = 1.0 / max(0.001, delta)
                    fps = instant if fps <= 0 else fps * 0.9 + instant * 0.1

                landmarks = None
                if not paused and not menu_open:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                    timestamp_ms = max(int(current * 1000), last_ts + 1)
                    last_ts = timestamp_ms
                    result = landmarker.detect_for_video(mp_image, timestamp_ms)
                    if result.hand_landmarks:
                        landmarks = result.hand_landmarks[0]
                        draw_landmarks(frame, landmarks)

                if training is not None:
                    training.handle_landmarks(landmarks)
                    training.tick()
                    status = f"EGITIM: {training.label}"
                    draw_training(frame, training)
                elif menu_open:
                    status = "HAREKET TANIMLAMA"
                    draw_menu(frame, custom, model, menu_message)
                elif paused:
                    status = "DURAKLATILDI"
                elif landmarks is not None:
                    try:
                        controller.complete_pending_click(current)
                        custom_action = custom.update(landmarks, current)
                        if custom_action is not None:
                            status = f"OZEL: {ACTION_LABELS[custom_action]}"
                            if custom_action == "close_window" and not custom.close_armed:
                                status = "PENCERE KAPATMA: KAPALI"
                        elif controller.pending_double_click is not None:
                            status = "SOL CIFT TIK"
                        else:
                            status = controller.update(landmarks)
                    except pyautogui.FailSafeException:
                        controller.release()
                        custom.reset()
                        paused = True
                        status = "EMNIYET DURDURMA"
                else:
                    controller.release()
                    custom.reset()
                    status = "EL BEKLENIYOR"

                draw_hud(frame, status, "PASIF" if paused else "AKTIF", fps, paused)
                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(1) & 0xFF

                if key == 255:
                    pass
                elif training is not None:
                    if key == 27:
                        training = None
                        menu_open = True
                        menu_message = "Egitim iptal edildi."
                        controller.release()
                        custom.reset()
                    elif key in (10, 13):
                        if training.phase == "retry":
                            training.retry()
                        elif training.phase == "done":
                            training = None
                            menu_open = True
                            menu_message = ""
                    elif key in (ord("r"), ord("R")) and training.phase == "retry":
                        model.clear(training.action)
                        model.save()
                        training.retry()
                elif key == 27:
                    if menu_open:
                        menu_open = False
                        close_confirm = False
                        reset_confirm = False
                        menu_message = ""
                    else:
                        break
                elif key in (ord("t"), ord("T")):
                    menu_open = not menu_open
                    close_confirm = False
                    reset_confirm = False
                    menu_message = ""
                    if menu_open:
                        controller.release()
                        custom.reset()
                elif key == 32 and not menu_open:
                    paused = not paused
                    if paused:
                        controller.release()
                        custom.reset()
                        status = "DURAKLATILDI"
                    else:
                        last_time = time.monotonic()
                elif menu_open:
                    if close_confirm and key != ord("3"):
                        close_confirm = False
                        menu_message = ""
                    if reset_confirm and key != ord("4"):
                        reset_confirm = False
                        menu_message = ""
                    if key in TRAINING_KEYS:
                        training = TrainingSession(model, TRAINING_KEYS[key])
                        menu_open = False
                        paused = False
                        controller.release()
                        custom.reset()
                    elif key == ord("3"):
                        if custom.close_armed:
                            training = TrainingSession(model, "close_window")
                            menu_open = False
                            paused = False
                            controller.release()
                            custom.reset()
                        elif close_confirm:
                            custom.close_armed = True
                            close_confirm = False
                            if model.is_validated("close_window"):
                                menu_message = "Pencere kapatma acildi."
                            else:
                                training = TrainingSession(model, "close_window")
                                menu_open = False
                                paused = False
                                controller.release()
                                custom.reset()
                        else:
                            close_confirm = True
                            menu_message = "Pencere kapatma riskli. Onay icin 3'e tekrar basin."
                    elif key == ord("4"):
                        if reset_confirm:
                            model.clear()
                            model.save()
                            custom.reset()
                            close_confirm = False
                            reset_confirm = False
                            menu_message = "Tum egitim silindi."
                        else:
                            reset_confirm = True
                            menu_message = "Emin misiniz? Silmek icin 4'e tekrar basin."
                    elif key in (ord("x"), ord("X")):
                        custom.enabled = not custom.enabled
                        if not custom.enabled:
                            custom.reset()
                        menu_message = (
                            f"Ozel hareketler {'acik' if custom.enabled else 'kapali'}."
                        )
                    elif key == ord("5"):
                        custom.close_armed = False
                        custom.reset()
                        menu_message = "Pencere kapatma devre disi."

                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        model.save()
        controller.release()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nHATA:", exc, file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
