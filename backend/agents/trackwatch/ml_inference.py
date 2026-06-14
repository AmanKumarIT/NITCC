"""
TrackWatch Agent — ML Inference Module
PRD FR-02.1: TensorFlow track failure prediction model
- Scores each track segment daily for failure probability
- Performance drift detection
"""

from __future__ import annotations
import logging
import os
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "ml_models", "track_failure")


class TrackFailurePredictor:
    """
    TensorFlow-based track failure probability predictor.
    Input features: vibration trend, thermal stress index, wheel impact cumulative,
    track age, days since maintenance, precipitation exposure, operational load.
    Output: failure probability (0–1) for the next 30-day window.
    """

    def __init__(self):
        self._model = None
        self._model_loaded = False
        self._baseline_accuracy: Optional[float] = None

    async def load_model(self) -> None:
        """Load TensorFlow SavedModel from disk."""
        try:
            import tensorflow as tf
            saved_model_path = os.path.join(MODEL_PATH, "saved_model")
            if os.path.exists(saved_model_path):
                self._model = tf.saved_model.load(saved_model_path)
                self._model_loaded = True
                logger.info(f"TrackWatch ML model loaded from {saved_model_path}")
            else:
                # Model not trained yet — use statistical fallback
                logger.warning(
                    "Track failure model not found. Using rule-based fallback. "
                    "Run ml/track_failure/train.py to generate the model."
                )
                self._model_loaded = False
        except ImportError:
            logger.warning("TensorFlow not installed. Using rule-based fallback predictor.")
            self._model_loaded = False
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            self._model_loaded = False

    async def predict_failure_probability(self, segment: Dict[str, Any]) -> float:
        """
        Predict 30-day failure probability for a track segment.
        Returns float in [0.0, 1.0].
        """
        features = self._extract_features(segment)

        if self._model_loaded:
            try:
                import tensorflow as tf
                feature_tensor = tf.constant([features], dtype=tf.float32)
                prediction = self._model.signatures["serving_default"](feature_tensor)
                prob = float(list(prediction.values())[0].numpy()[0][0])
                return round(max(0.0, min(1.0, prob)), 4)
            except Exception as e:
                logger.warning(f"ML inference error, falling back to rule-based: {e}")

        # Rule-based fallback (statistical heuristic)
        return self._rule_based_prediction(segment, features)

    def _extract_features(self, segment: Dict[str, Any]) -> list:
        """Extract feature vector from track segment document."""
        comps = segment.get("healthComponents", {})
        last_maint = segment.get("lastMaintenanceDate")
        days_since_maint = 0
        if last_maint:
            if isinstance(last_maint, str):
                try:
                    last_maint = datetime.fromisoformat(last_maint)
                except Exception:
                    last_maint = None
            if last_maint:
                days_since_maint = (datetime.utcnow() - last_maint).days

        return [
            comps.get("structural_integrity", 100) / 100,  # Normalize 0–1
            comps.get("environmental_stress", 100) / 100,
            comps.get("operational_load", 100) / 100,
            comps.get("maintenance_recency", 100) / 100,
            min(segment.get("ageYears", 0) / 100, 1.0),
            min(days_since_maint / 365, 1.0),
            segment.get("healthScore", 100) / 100,
            segment.get("failureProbability", 0.0),  # Previous prediction as feature
        ]

    def _rule_based_prediction(self, segment: dict, features: list) -> float:
        """
        Statistical heuristic when ML model unavailable.
        Higher risk for: low health score + high age + overdue maintenance.
        """
        health_score = segment.get("healthScore", 100)
        age_years = segment.get("ageYears", 0)

        prob = 0.0
        # Base risk from health score
        prob += (100 - health_score) / 100 * 0.5
        # Age factor
        prob += min(age_years / 100, 0.3)
        # Maintenance recency (features[5] = days since maint / 365)
        prob += features[5] * 0.2

        return round(max(0.0, min(1.0, prob)), 4)

    def detect_accuracy_drift(self, current_accuracy: float) -> bool:
        """
        FR-02.1: Detect model performance drift.
        Returns True if drift detected (accuracy dropped significantly).
        """
        if self._baseline_accuracy is None:
            self._baseline_accuracy = current_accuracy
            return False
        drift = self._baseline_accuracy - current_accuracy
        if drift > 0.05:  # >5% accuracy drop
            logger.warning(
                f"Model accuracy drift detected: baseline={self._baseline_accuracy:.3f}, "
                f"current={current_accuracy:.3f}, drift={drift:.3f}"
            )
            return True
        return False
