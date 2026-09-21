"""haptic_encoder.py

Core Spatio-Tactile Haptic Encoding Engine for Module 3.
Converts classified hazard packets from Queue B into 3-axis tactile actuation commands:
- Axis 1 (Azimuth): Left (motor 0), Center (motor 1), Right (motor 2)
- Axis 2 (Urgency): Imminent (<0.8s), Approaching (0.8s - 2.0s), Safe (>2.0s or invalid)
- Axis 3 (Class Texture): DRV2605L Library 6 ROM waveforms & repeat intervals

Target: IEEE Sensors Journal.
"""

from __future__ import annotations

import math
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure config can be imported whether run from root or inside module3_haptic/
try:
    import config
    from module3_haptic import waveform_map
except ImportError:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    import config
    from module3_haptic import waveform_map


class HapticEncoder:
    """Encodes Queue B obstacle packets into tactile motor commands."""

    def __init__(self) -> None:
        self._dropped_count: int = 0
        self._lock: threading.Lock = threading.Lock()

    def get_dropped_count(self) -> int:
        """Return cumulative count of dropped or malformed packets."""
        with self._lock:
            return self._dropped_count

    def reset_dropped_count(self) -> None:
        """Reset the dropped packet counter to 0."""
        with self._lock:
            self._dropped_count = 0

    def increment_dropped_count(self) -> None:
        """Increment dropped packet counter safely."""
        with self._lock:
            self._dropped_count += 1

    def compute_urgency(self, ttc: Optional[float]) -> str:
        """Compute urgency category from Time-to-Collision (TTC) in seconds.

        Rules:
        - Treat ttc None, NaN, negative, or > 60 s as "safe".
        - < 0.8 s: imminent
        - 0.8 <= ttc <= 2.0: approaching (0.8 and 2.0 both count as approaching)
        - > 2.0 s: safe
        """
        if ttc is None:
            return config.URGENCY_SAFE

        try:
            val = float(ttc)
        except (ValueError, TypeError):
            return config.URGENCY_SAFE

        if math.isnan(val) or val < config.TTC_MIN_VALID or val > config.TTC_MAX_VALID:
            return config.URGENCY_SAFE

        if val < config.TTC_IMMINENT_THRESHOLD:
            return config.URGENCY_IMMINENT
        elif val <= config.TTC_APPROACHING_MAX:
            return config.URGENCY_APPROACHING
        else:
            return config.URGENCY_SAFE

    def _get_effective_ttc(self, ttc: Optional[float]) -> float:
        """Calculate effective TTC for sorting priority.

        Lower TTC = higher priority.
        None, NaN, negative, or > 60s are treated as safe (lowest priority -> inf).
        """
        if ttc is None:
            return config.TTC_SENTINEL_SAFE

        try:
            val = float(ttc)
        except (ValueError, TypeError):
            return config.TTC_SENTINEL_SAFE

        if math.isnan(val) or val < config.TTC_MIN_VALID or val > config.TTC_MAX_VALID:
            return config.TTC_SENTINEL_SAFE

        return val

    def validate_packet(self, packet: Any) -> bool:
        """Validate packet structure, types, and values against Queue B specification.

        Expected schema:
        {
            "ts": float,
            "azimuth": "L" | "C" | "R",
            "distance": float (m),
            "ttc": float | None (s),
            "class": "person" | "vehicle" | "overhead" | "wall",
            "elevation": "head" | "ground"
        }
        """
        if not isinstance(packet, dict):
            return False

        # Required fields presence
        for key in config.REQUIRED_PACKET_KEYS:
            if key not in packet:
                return False

        # Timestamp validation
        ts = packet["ts"]
        if not isinstance(ts, (int, float)) or (isinstance(ts, float) and math.isnan(ts)):
            return False

        # Distance validation
        dist = packet["distance"]
        if not isinstance(dist, (int, float)) or (isinstance(dist, float) and math.isnan(dist)):
            return False

        # Elevation validation
        if packet["elevation"] not in config.VALID_ELEVATIONS:
            return False

        # Azimuth validation (Axis 1)
        if packet["azimuth"] not in config.VALID_AZIMUTHS:
            return False

        # Class validation: Unknown class must NOT default to person; drop packet
        hazard_class = packet["class"]
        if not isinstance(hazard_class, str) or not waveform_map.is_valid_hazard_class(hazard_class):
            return False

        # TTC validation (numeric or None)
        ttc = packet["ttc"]
        if ttc is not None:
            if not isinstance(ttc, (int, float)):
                return False

        return True

    def encode(
        self, packet_or_list: Union[Dict[str, Any], List[Dict[str, Any]], None]
    ) -> Optional[Tuple[int, int, int, str]]:
        """Encode a hazard packet or list of packets into a tactile actuation command.

        Parameters:
            packet_or_list: A single Queue B packet dict, or a list of packet dicts.

        Returns:
            (motor_index, effect_id, repeat_ms, urgency)
            or None if the packet is dropped, malformed, or no valid hazard exists.
        """
        if packet_or_list is None:
            self.increment_dropped_count()
            return None

        # Handle list of hazard packets
        if isinstance(packet_or_list, list):
            if len(packet_or_list) == 0:
                return None

            valid_packets = []
            for item in packet_or_list:
                if self.validate_packet(item):
                    valid_packets.append(item)
                else:
                    self.increment_dropped_count()

            if not valid_packets:
                return None

            # Pick hazard with lowest effective TTC (None = inf / highest TTC)
            chosen_packet = min(
                valid_packets, key=lambda p: self._get_effective_ttc(p.get("ttc"))
            )
            return self._encode_single_valid_packet(chosen_packet)

        # Handle single hazard packet
        if not self.validate_packet(packet_or_list):
            self.increment_dropped_count()
            return None

        return self._encode_single_valid_packet(packet_or_list)

    def _encode_single_valid_packet(
        self, packet: Dict[str, Any]
    ) -> Optional[Tuple[int, int, int, str]]:
        """Encode a pre-validated packet into a tactile tuple."""
        azimuth = packet["azimuth"]
        hazard_class = packet["class"]
        ttc = packet["ttc"]

        # Axis 1: Motor routing
        motor_index = config.AZIMUTH_TO_MOTOR[azimuth]

        # Axis 2: Urgency classification
        urgency = self.compute_urgency(ttc)

        # Axis 3: Tactile waveform lookup
        effect_pair = waveform_map.resolve_haptic_effect(hazard_class, urgency)
        if effect_pair is None:
            self.increment_dropped_count()
            return None

        effect_id, repeat_ms = effect_pair
        return (motor_index, effect_id, repeat_ms, urgency)


# Global singleton instance for functional module-level API
_DEFAULT_ENCODER = HapticEncoder()


def encode(
    packet_or_list: Union[Dict[str, Any], List[Dict[str, Any]], None]
) -> Optional[Tuple[int, int, int, str]]:
    """Encode packet or list using global encoder instance."""
    return _DEFAULT_ENCODER.encode(packet_or_list)


def validate_packet(packet: Any) -> bool:
    """Validate packet structure against Queue B specification."""
    return _DEFAULT_ENCODER.validate_packet(packet)


def get_dropped_count() -> int:
    """Return count of dropped packets from global encoder."""
    return _DEFAULT_ENCODER.get_dropped_count()


def reset_dropped_count() -> None:
    """Reset dropped packet count on global encoder."""
    _DEFAULT_ENCODER.reset_dropped_count()
