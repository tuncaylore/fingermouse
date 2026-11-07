"""FingerMouse: 21 nokta tabanli, harici kutuphane gerektirmeyen gesture helpers."""
from __future__ import annotations

from math import atan2, cos, hypot, sin

# MediaPipe el eklem numaralari
WRIST = 0
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_TIP = 12
RING_PIP = 14
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_TIP = 20


def xy(point):
    """MediaPipe landmark veya (x,y) tuple kabul eder."""
    if hasattr(point, "x"):
        return float(point.x), float(point.y)
    return float(point[0]), float(point[1])


def distance(a, b):
    x1, y1 = xy(a)
    x2, y2 = xy(b)
    return hypot(x1 - x2, y1 - y2)


def palm_width(landmarks):
    return max(0.04, distance(landmarks[INDEX_MCP], landmarks[PINKY_MCP]))


def normalized_pinch(landmarks, finger_tip):
    return distance(landmarks[THUMB_TIP], landmarks[finger_tip]) / palm_width(landmarks)


def gesture_features(landmarks):
    """42 boyutlu, konum/olcek/donme bagimsiz ozellik vektoru."""
    wx, wy = xy(landmarks[WRIST])
    mx, my = xy(landmarks[MIDDLE_MCP])
    scale = palm_width(landmarks)
    angle = atan2(my - wy, mx - wx)
    ca, sa = cos(-angle), sin(-angle)
    features = []
    for point in landmarks:
        px, py = xy(point)
        dx = (px - wx) / scale
        dy = (py - wy) / scale
        features.append(dx * ca - dy * sa)
        features.append(dx * sa + dy * ca)
    return features


def extended(landmarks, tip, pip):
    """Parmagin ucunun bilege, orta ekleminden daha uzak olmasi."""
    return distance(landmarks[WRIST], landmarks[tip]) > distance(landmarks[WRIST], landmarks[pip]) * 1.10


def motion_mode(landmarks):
    """'move', 'scroll' veya 'idle' -- isaret ve orta parmak durumuna gore."""
    index_up = extended(landmarks, INDEX_TIP, INDEX_PIP)
    middle_up = extended(landmarks, MIDDLE_TIP, MIDDLE_PIP)
    ring_up = extended(landmarks, RING_TIP, RING_PIP)
    pinky_up = extended(landmarks, PINKY_TIP, PINKY_PIP)
    if index_up and middle_up and not ring_up and not pinky_up:
        return "scroll"
    if index_up and not middle_up and not ring_up and not pinky_up:
        return "move"
    return "idle"


def map_to_screen(x, y, width, height, margin=0.12):
    """Aynali kamera koordinatlarini ekranin guvenli bolgesine haritalar."""
    usable = 1.0 - 2.0 * margin
    fx = max(0.0, min(1.0, (x - margin) / usable))
    fy = max(0.0, min(1.0, (y - margin) / usable))
    # PyAutoGUI failsafe: ekranin mutlak kosesine hic gitme.
    return 8 + fx * (width - 16), 8 + fy * (height - 16)


class Hysteresis:
    """Enter/exit esikleriyle pinç titremesini onler."""

    def __init__(self, enter=0.32, exit=0.46):
        assert enter < exit
        self.enter = enter
        self.exit = exit
        self.active = False

    def update(self, value):
        if self.active and value > self.exit:
            self.active = False
        elif not self.active and value < self.enter:
            self.active = True
        return self.active

    def reset(self):
        self.active = False
