"""
zone_classifier.py
Converts the ego-motion-corrected 64-zone (azimuth, elevation, distance)
field from ego_motion.py into the 3x2 spatial bin structure consumed by
Module 2 (dual-stage AI gating) and Module 3 (haptic azimuth selection):

  Azimuth:   Left / Center / Right   (equal thirds of the 90deg FoV)
  Elevation: Head-height / Ground    (upper vs lower half of the FoV)

Binning is done by the CORRECTED azimuth/elevation angle, not raw
column/row index, so a bin's real-world meaning stays fixed in the
torso frame even as the wearer's head turns — that's the whole point
of Novelty 01 feeding into this step.

IMPORTANT — Out-of-bounds filtering: after ego-motion compensation,
zones whose corrected azimuth falls outside the forward hemicycle
(|az| > 90°) are discarded.  Without this guard, a shoulder-check
head turn could rotate a rear obstacle into a front-facing bin and
fire the wrong neckband motor.
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import numpy as np

from config import TOF_FOV_DEG

_HALF_FOV = TOF_FOV_DEG / 2.0
_AZ_THIRD = TOF_FOV_DEG / 3.0

# Forward hemicycle limit: zones beyond ±90° in the torso frame are
# behind the user and must NOT trigger any front-facing haptic motor.
_FORWARD_LIMIT_DEG = 90.0

AZIMUTH_BINS = ("LEFT", "CENTER", "RIGHT")
ELEVATION_BINS = ("HEAD", "GROUND")


def classify(fused_frame):
    """
    Args:
      fused_frame: dict from ego_motion.compensate_frame(...) or
                   compensate_frame_raw(...).

    Returns a packet ready for Queue A (consumed by Module 2):
      {
        "bins": {
            ("LEFT", "HEAD"): min_distance_mm or None,
            ...  # all 6 (azimuth, elevation) combinations
        },
        "raw": fused_frame,  # full corrected field, in case Module 2/3 need it
      }
    Each bin holds the NEAREST (minimum-distance) zone that falls in it,
    since that's the zone that matters for both the Stage-1 gate
    threshold (Module 2) and haptic urgency (Module 3).

    Zones whose corrected azimuth is outside the forward hemicycle
    (|az| > 90°) are silently dropped — they represent obstacles
    behind the user's torso and must not trigger front-facing haptics.
    """
    az = fused_frame["azimuth_deg"]
    el = fused_frame["elevation_deg"]
    dist = fused_frame["distance_mm"]

    # --- Guard: discard zones that rotated behind the user ---
    forward_mask = np.abs(az) <= _FORWARD_LIMIT_DEG

    # --- Azimuth bins (vectorized) ---
    left_bound = -_HALF_FOV + _AZ_THIRD    # -15° for 90° FoV
    right_bound = _HALF_FOV - _AZ_THIRD    # +15° for 90° FoV

    az_masks = {
        "LEFT":   forward_mask & (az < left_bound),
        "CENTER": forward_mask & (az >= left_bound) & (az <= right_bound),
        "RIGHT":  forward_mask & (az > right_bound),
    }

    # --- Elevation bins (vectorized) ---
    el_masks = {
        "HEAD":   el >= 0,
        "GROUND": el < 0,
    }

    # --- Compute nearest distance per bin ---
    bins = {}
    for a_name, a_mask in az_masks.items():
        for e_name, e_mask in el_masks.items():
            combined = a_mask & e_mask
            subset = dist[combined]
            bins[(a_name, e_name)] = float(np.min(subset)) if subset.size > 0 else None

    return {"bins": bins, "raw": fused_frame}


if __name__ == "__main__":
    import ego_motion

    # Test 1: obstacle at raw grid position LEFT+HEAD, no head rotation
    dist = np.full((8, 8), 4000.0, dtype=np.float32)
    dist[2, 1] = 900.0
    fused = ego_motion.compensate_frame(dist, yaw_deg=0.0, pitch_deg=0.0)
    packet = classify(fused)
    print("=== Test 1: yaw=0° (no rotation) ===")
    for k, v in packet["bins"].items():
        print(f"  {k}: {v} mm")

    # Test 2: extreme head turn — obstacle should be OUT_OF_BOUNDS
    dist2 = np.full((8, 8), 4000.0, dtype=np.float32)
    dist2[4, 4] = 800.0   # center of grid
    fused2 = ego_motion.compensate_frame(dist2, yaw_deg=120.0, pitch_deg=0.0)
    packet2 = classify(fused2)
    print("\n=== Test 2: yaw=120° (extreme turn — obstacle should be filtered) ===")
    for k, v in packet2["bins"].items():
        print(f"  {k}: {v} mm")
    all_none = all(v is None or v >= 3999 for v in packet2["bins"].values())
    print(f"  All bins clear (obstacle behind user filtered): {all_none}")

