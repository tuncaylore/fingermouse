"""Kullanici tanimli hareketlerin kaydedilmesi ve siniflandirilmasi."""
from __future__ import annotations

import json
from math import sqrt
from pathlib import Path

import numpy as np

ACTION_LABELS = {
    "left_click": "Sol Tik",
    "right_click": "Sag Tik",
    "close_window": "Pencereyi Kapat",
    "double_click": "Sol Cift Tik",
}
ACTION_ORDER = ("left_click", "right_click", "close_window", "double_click")

MIN_SAMPLES = 15
MAX_SPREAD = 0.55
MIN_CLASS_MARGIN = 0.15
MIN_PREDICTION_MARGIN = 0.05
MAX_NORMALIZED_DISTANCE = 2.6
RADIUS_FLOOR = 0.10
MAX_SAMPLES_PER_ACTION = 150


class GestureModel:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.samples = {}
        self.validated = set()
        self._stats_cache = {}
        if self.path is not None:
            self.load()

    def load(self):
        if self.path is None or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, dict):
            return
        actions = payload.get("actions", {})
        if not isinstance(actions, dict):
            return
        self.samples = {}
        for action, rows in actions.items():
            if action not in ACTION_LABELS or not isinstance(rows, list):
                continue
            clean = []
            for row in rows:
                if isinstance(row, list) and row and all(
                    isinstance(value, (int, float)) for value in row
                ):
                    clean.append([float(value) for value in row])
            if clean:
                self.samples[action] = clean[-MAX_SAMPLES_PER_ACTION:]
        validated = payload.get("validated", [])
        if not isinstance(validated, list):
            validated = []
        self.validated = {
            action
            for action in validated
            if action in ACTION_LABELS and len(self.samples.get(action, [])) >= MIN_SAMPLES
        }
        self._stats_cache.clear()

    def save(self):
        if self.path is None:
            return
        payload = {
            "version": 1,
            "validated": sorted(self.validated),
            "actions": {
                action: [
                    [round(float(value), 6) for value in row]
                    for row in rows
                ]
                for action, rows in self.samples.items()
                if action in ACTION_LABELS
            },
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError:
            pass

    def add_sample(self, action, features):
        if action not in ACTION_LABELS:
            return
        rows = self.samples.setdefault(action, [])
        rows.append([float(value) for value in features])
        if len(rows) > MAX_SAMPLES_PER_ACTION:
            del rows[: len(rows) - MAX_SAMPLES_PER_ACTION]
        self.validated.discard(action)
        self._stats_cache.pop(action, None)

    def add_samples(self, action, features_list):
        for features in features_list:
            self.add_sample(action, features)

    def clear(self, action=None):
        if action is None:
            self.samples.clear()
            self.validated.clear()
            self._stats_cache.clear()
        else:
            self.samples.pop(action, None)
            self.validated.discard(action)
            self._stats_cache.pop(action, None)

    def mark_validated(self, action):
        if action in ACTION_LABELS and len(self.samples.get(action, [])) >= MIN_SAMPLES:
            self.validated.add(action)

    def is_validated(self, action):
        return action in self.validated

    def count(self, action):
        return len(self.samples.get(action, []))

    def trained_actions(self):
        return [
            action
            for action in ACTION_ORDER
            if len(self.samples.get(action, [])) >= MIN_SAMPLES
        ]

    def validated_actions(self):
        return [
            action
            for action in ACTION_ORDER
            if action in self.validated
            and len(self.samples.get(action, [])) >= MIN_SAMPLES
        ]

    def _stats_for(self, action):
        cached = self._stats_cache.get(action)
        if cached is not None:
            return cached
        rows = self.samples.get(action, [])
        if not rows:
            return None
        data = np.asarray(rows, dtype=np.float32)
        centroid = data.mean(axis=0)
        spread = float(np.linalg.norm(data - centroid, axis=1).mean())
        radius = max(RADIUS_FLOOR, spread)
        result = (centroid, radius, spread)
        self._stats_cache[action] = result
        return result

    def evaluate(self, action):
        count = self.count(action)
        if count < MIN_SAMPLES:
            return False, f"Yeterli ornek yok ({count}/{MIN_SAMPLES}). Tekrar deneyin."
        stats = self._stats_for(action)
        if stats is None:
            return False, "Ornek bulunamadi. Tekrar deneyin."
        _, radius, spread = stats
        if spread > MAX_SPREAD:
            return False, "Hareket kararsiz. Ayni hareketi daha sabit tekrar yapin."
        centroid = stats[0]
        for other in self.validated_actions():
            if other == action:
                continue
            other_stats = self._stats_for(other)
            if other_stats is None:
                continue
            other_centroid, other_radius, _ = other_stats
            gap = float(np.linalg.norm(centroid - other_centroid))
            margin = (gap - (radius + other_radius)) / (
                gap + radius + other_radius + 1e-6
            )
            if margin < MIN_CLASS_MARGIN:
                return False, "Hareket baska bir hareketle cok benzer. Farkli bir hareket deneyin."
        return True, "Hareket ogrenildi."

    def predict(self, features, actions=None):
        if actions is None:
            actions = self.trained_actions()
        if not actions:
            return None, 0.0, 0.0
        vector = np.asarray(features, dtype=np.float32)
        scored = []
        for action in actions:
            stats = self._stats_for(action)
            if stats is None:
                continue
            centroid, radius, _ = stats
            delta = vector - centroid
            normalized = sqrt(float(np.dot(delta, delta))) / radius
            scored.append((normalized, action))
        if not scored:
            return None, 0.0, 0.0
        scored.sort(key=lambda item: item[0])
        best_distance, best_action = scored[0]
        if best_distance > MAX_NORMALIZED_DISTANCE:
            return None, 0.0, 0.0
        if len(scored) > 1:
            second_distance = scored[1][0]
            margin = (second_distance - best_distance) / (
                second_distance + best_distance + 1e-6
            )
            if margin < MIN_PREDICTION_MARGIN:
                return None, 0.0, margin
        else:
            margin = 1.0
        fit = max(0.0, 1.0 - best_distance / MAX_NORMALIZED_DISTANCE)
        if len(scored) > 1:
            margin_score = max(0.0, min(1.0, margin / 0.30))
            confidence = 0.6 * fit + 0.4 * margin_score
        else:
            confidence = fit
        return best_action, float(confidence), float(margin)
