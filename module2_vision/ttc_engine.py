"""
Time-to-Collision (TTC) & Approach Rate Computation Engine (Novelty 02 Co-Lead)
Author: Dhivyashree G J. (24BCE1516)

Calculates dynamic approach velocity and Time-to-Collision across a rolling temporal
window, classifying hazard urgency to drive the 3-axis spatio-tactile feedback.
"""

from collections import deque
from dataclasses import dataclass
import time
from typing import Deque, Dict, Optional, Tuple
import numpy as np

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config


@dataclass
class TTCResult:
    """Encapsulates relative kinematics and urgency classification for a hazard."""
    distance_m: float
    approach_velocity_mps: float  # Positive = approaching, Negative = receding
    ttc_seconds: float            # Time-to-collision in seconds
    urgency_level: str            # "IMMINENT", "APPROACHING", "SAFE"
    is_approaching: bool          # True if approaching faster than minimum velocity
    window_samples: int           # Number of valid temporal points in current window


class TTCEngine:
    """
    Computes rolling relative velocity and Time-to-Collision (TTC) per spatial sector.
    Suppresses sensor jitter using multi-frame temporal regression.
    """

    def __init__(
        self,
        window_size: int = config.TTC_WINDOW_SIZE,
        imminent_threshold_s: float = config.TTC_IMMINENT_THRESHOLD_S,
        approaching_threshold_s: float = config.TTC_APPROACHING_THRESHOLD_S,
        min_approach_velocity_mps: float = config.MIN_APPROACH_VELOCITY_MPS,
    ):
        self.window_size = window_size
        self.imminent_threshold_s = imminent_threshold_s
        self.approaching_threshold_s = approaching_threshold_s
        self.min_approach_velocity_mps = min_approach_velocity_mps

        # Temporal ring buffers per azimuth sector: { "Left": deque([(t, d)]), ... }
        self._history: Dict[str, Deque[Tuple[float, float]]] = {
            "Left": deque(maxlen=window_size),
            "Center": deque(maxlen=window_size),
            "Right": deque(maxlen=window_size),
            "Global": deque(maxlen=window_size),
        }

    def update(
        self,
        distance_m: float,
        sector: str = "Center",
        timestamp: Optional[float] = None,
    ) -> TTCResult:
        """
        Updates tracking buffer with new distance observation and calculates TTC.
        
        Args:
            distance_m: Current distance to obstacle in meters
            sector: Azimuth sector ("Left", "Center", "Right")
            timestamp: Unix timestamp (defaults to time.time())
            
        Returns:
            TTCResult dataclass.
        """
        t = time.time() if timestamp is None else timestamp
        target_sector = sector if sector in self._history else "Global"
        buf = self._history[target_sector]

        # Clamp distance to positive non-zero
        distance_m = max(0.05, float(distance_m))

        # Enforce strictly monotonic timestamps for reliable numerical derivatives
        if len(buf) > 0 and t <= buf[-1][0]:
            t = buf[-1][0] + 0.001

        buf.append((t, distance_m))

        # With only 1 sample, velocity cannot be estimated
        if len(buf) < 2:
            return TTCResult(
                distance_m=distance_m,
                approach_velocity_mps=0.0,
                ttc_seconds=99.9,
                urgency_level="SAFE",
                is_approaching=False,
                window_samples=len(buf),
            )

        # Compute velocity using linear regression slope over the rolling window
        # Distance model: d(t) = d_0 - v_approach * t
        # slope m = Delta d / Delta t; v_approach = -m
        times = np.array([item[0] for item in buf], dtype=np.float64)
        distances = np.array([item[1] for item in buf], dtype=np.float64)

        # Normalize time to avoid numerical instability
        t_rel = times - times[0]

        if len(buf) >= 3:
            # Polyfit degree 1: distances = m * t_rel + c
            slope, _ = np.polyfit(t_rel, distances, 1)
        else:
            dt = t_rel[-1] - t_rel[0]
            if dt <= 0:
                dt = 0.033  # fallback ~30Hz
            slope = (distances[-1] - distances[0]) / dt

        # Approach velocity is negative distance rate (-dd/dt)
        approach_velocity = float(-slope)

        # Threshold check: is target actively closing in?
        is_approaching = approach_velocity >= self.min_approach_velocity_mps

        if is_approaching:
            # Effective TTC = distance / approach_speed
            # Clamped denominator to prevent division by zero
            eff_velocity = max(approach_velocity, 0.01)
            ttc = float(distance_m / eff_velocity)
        else:
            # Obstacle is static or moving away -> collision not imminent
            ttc = 99.9

        # Classify urgency level
        if ttc < self.imminent_threshold_s:
            urgency = "IMMINENT"
        elif ttc <= self.approaching_threshold_s:
            urgency = "APPROACHING"
        else:
            urgency = "SAFE"

        return TTCResult(
            distance_m=distance_m,
            approach_velocity_mps=round(approach_velocity, 3),
            ttc_seconds=round(ttc, 2),
            urgency_level=urgency,
            is_approaching=is_approaching,
            window_samples=len(buf),
        )

    def reset_sector(self, sector: Optional[str] = None):
        """Clears tracking history for a specific sector or all sectors."""
        if sector and sector in self._history:
            self._history[sector].clear()
        else:
            for s in self._history:
                self._history[s].clear()
