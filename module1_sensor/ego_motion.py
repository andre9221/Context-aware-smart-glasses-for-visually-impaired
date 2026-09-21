"""
ego_motion.py
Quaternion-based ego-motion compensation engine — Novelty 01.

Re-projects the VL53L5CX's 64 head-frame obstacle vectors into the
torso-fixed reference frame using a real-time quaternion rotation
R(theta_head) built from IMU yaw/pitch (imu_driver.py). This corrects
the azimuth error that would otherwise occur when the wearer turns
their head without turning their torso (e.g. checking a blind
corner), which would fire haptic motors on the wrong side of the
neckband if left uncorrected.

Design:
  1. Build a static "zone direction table": for each of the 64 ToF
     zones, its azimuth/elevation angle within the 90deg FoV, assuming
     the sensor is boresighted straight ahead when head yaw/pitch = 0.
  2. Each frame, build a unit quaternion q = q(yaw, pitch) from the IMU.
  3. Rotate every zone's unit direction vector by q to get its
     direction in the torso frame.
  4. Recompute azimuth/elevation from the rotated vectors and pair
     them back up with the (unchanged) distance measurement.

compensate_frame_raw() reproduces the *uncorrected* baseline (as if
the head never moved) and is used by ablation_study.py to quantify
the WITH-vs-WITHOUT improvement for the paper.
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import numpy as np

from config import TOF_GRID_SIZE, TOF_FOV_DEG

_N = TOF_GRID_SIZE


def _build_zone_directions():
    """Static per-zone (azimuth_deg, elevation_deg) table for an N x N
    grid spanning +/-FOV/2 on both axes, one angle per zone center."""
    half_fov = TOF_FOV_DEG / 2.0
    edges = np.linspace(-half_fov, half_fov, _N + 1)
    centers = (edges[:-1] + edges[1:]) / 2.0       # N zone centers along one axis
    az = np.tile(centers, (_N, 1))                          # columns -> azimuth (same across rows)
    el = np.tile(centers[::-1].reshape(-1, 1), (1, _N))     # rows -> elevation; row 0 = top of FoV = most positive
    return az, el  # each (N, N), degrees


_ZONE_AZ_DEG, _ZONE_EL_DEG = _build_zone_directions()


def _angles_to_unit_vectors(az_deg, el_deg):
    """Spherical (az, el) -> unit vector in the sensor frame.
    Convention: +X forward (boresight), +Y left, +Z up."""
    az = np.radians(az_deg)
    el = np.radians(el_deg)
    x = np.cos(el) * np.cos(az)
    y = np.cos(el) * np.sin(az)
    z = np.sin(el)
    return np.stack([x, y, z], axis=-1)  # (..., 3)


def quat_multiply(q1, q2):
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ])


def quat_from_yaw_pitch(yaw_deg, pitch_deg):
    """Unit quaternion (w, x, y, z) for head yaw (about +Z, up) composed
    with pitch (about +Y, left): q = q_yaw * q_pitch (intrinsic)."""
    yaw = np.radians(yaw_deg) / 2.0
    pitch = np.radians(pitch_deg) / 2.0

    q_yaw = np.array([np.cos(yaw), 0.0, 0.0, np.sin(yaw)])       # rotation about Z
    q_pitch = np.array([np.cos(pitch), 0.0, np.sin(pitch), 0.0])  # rotation about Y
    return quat_multiply(q_yaw, q_pitch)


def quat_to_rotation_matrix(q):
    """R(theta_head): 3x3 rotation matrix from a unit quaternion (w,x,y,z)."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def compensate_frame(distance_mm, yaw_deg, pitch_deg):
    """
    Core Novelty-01 transform: re-projects the 64 head-frame zone
    vectors into the torso frame given the current IMU orientation.

    Args:
      distance_mm: (N, N) raw ToF distances for this frame.
      yaw_deg, pitch_deg: current head orientation from imu_driver.update().

    Returns dict with:
      distance_mm   : unchanged (N, N) raw distances
      azimuth_deg   : (N, N) CORRECTED azimuth in the torso frame
      elevation_deg : (N, N) CORRECTED elevation in the torso frame
      R             : the 3x3 rotation matrix used this frame (for logging)
    """
    q = quat_from_yaw_pitch(yaw_deg, pitch_deg)
    R = quat_to_rotation_matrix(q)

    sensor_vecs = _angles_to_unit_vectors(_ZONE_AZ_DEG, _ZONE_EL_DEG)  # (N, N, 3)
    torso_vecs = sensor_vecs @ R.T                                     # (N, N, 3)

    az_corr = np.degrees(np.arctan2(torso_vecs[..., 1], torso_vecs[..., 0]))
    el_corr = np.degrees(np.arcsin(np.clip(torso_vecs[..., 2], -1.0, 1.0)))

    return {
        "distance_mm": distance_mm,
        "azimuth_deg": az_corr,
        "elevation_deg": el_corr,
        "R": R,
    }


def compensate_frame_raw(distance_mm):
    """The 'WITHOUT ego-motion compensation' baseline for the ablation
    study: azimuth/elevation come straight from the static zone table,
    i.e. exactly as if the head had never moved."""
    return {
        "distance_mm": distance_mm,
        "azimuth_deg": _ZONE_AZ_DEG.copy(),
        "elevation_deg": _ZONE_EL_DEG.copy(),
        "R": np.eye(3),
    }


if __name__ == "__main__":
    # Quick sanity check: a stationary obstacle dead ahead in the SENSOR
    # frame (az=0) should read as az=+yaw in the torso frame once the head
    # turns `yaw` degrees left — turning your head 30 deg left to look
    # straight at something means that something is 30 deg to the left
    # of your torso, which is exactly what R(theta_head) should recover.
    for test_yaw in (0.0, 30.0, 90.0):
        q = quat_from_yaw_pitch(test_yaw, 0.0)
        R = quat_to_rotation_matrix(q)
        v = _angles_to_unit_vectors(np.array(0.0), np.array(0.0))
        v_torso = v @ R.T
        az = np.degrees(np.arctan2(v_torso[1], v_torso[0]))
        print(f"head_yaw={test_yaw:5.1f} deg -> obstacle appears at torso az={az:6.1f} deg")
