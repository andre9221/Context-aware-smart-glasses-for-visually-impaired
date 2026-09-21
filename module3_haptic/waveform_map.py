"""waveform_map.py

Lookup table and helper functions for DRV2605L ROM effect IDs and repeat intervals
based on hazard semantic classification and approach urgency.

Target: IEEE Sensors Journal (Module 3 Spatio-Tactile Haptics).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

# Ensure config can be imported whether run from root or inside module3_haptic/
try:
    from config import (
        SUPPORTED_CLASSES,
        SUPPORTED_URGENCIES,
        URGENCY_APPROACHING,
        URGENCY_IMMINENT,
        URGENCY_SAFE,
        WAVEFORM_TABLE,
    )
except ImportError:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from config import (
        SUPPORTED_CLASSES,
        SUPPORTED_URGENCIES,
        URGENCY_APPROACHING,
        URGENCY_IMMINENT,
        URGENCY_SAFE,
        WAVEFORM_TABLE,
    )


def resolve_haptic_effect(
    hazard_class: Optional[str], urgency: Optional[str]
) -> Optional[Tuple[int, int]]:
    """Resolve DRV2605L effect ID and repeat interval for a given hazard class and urgency.

    Unknown or missing class must NOT default to person; returns None if invalid.
    For alert effects (#15, #16), repeat_ms is guaranteed to be at least the effect duration.

    Parameters:
        hazard_class: Semantic class of obstacle ('person', 'vehicle', 'overhead', 'wall').
        urgency: Urgency category ('imminent', 'approaching', 'safe').

    Returns:
        (effect_id, repeat_ms) if valid, or None if class or urgency is unrecognized/missing.
    """
    if not hazard_class or not urgency:
        return None

    if hazard_class not in WAVEFORM_TABLE:
        return None

    class_table = WAVEFORM_TABLE[hazard_class]
    if urgency not in class_table:
        return None

    return class_table[urgency]


def lookup(hazard_class: str, urgency: str) -> Tuple[int, int]:
    """Lookup DRV2605L tactile effect ID and repeat interval in milliseconds.

    Raises:
        KeyError: If hazard_class or urgency is not supported.
    """
    effect = resolve_haptic_effect(hazard_class, urgency)
    if effect is None:
        if hazard_class not in WAVEFORM_TABLE:
            raise KeyError(
                f"Unsupported hazard class: {hazard_class!r}. "
                f"Expected one of: {SUPPORTED_CLASSES}"
            )
        raise KeyError(
            f"Unsupported urgency level: {urgency!r}. "
            f"Expected one of: {SUPPORTED_URGENCIES}"
        )
    return effect


def get_waveform(hazard_class: str, urgency: str) -> Optional[Tuple[int, int]]:
    """Alias for resolve_haptic_effect for backward compatibility."""
    return resolve_haptic_effect(hazard_class, urgency)


def is_valid_hazard_class(hazard_class: str) -> bool:
    """Check if the provided hazard class is defined in the waveform library."""
    return hazard_class in WAVEFORM_TABLE


def is_valid_urgency(urgency: str) -> bool:
    """Check if the provided urgency level is recognized."""
    return urgency in SUPPORTED_URGENCIES
