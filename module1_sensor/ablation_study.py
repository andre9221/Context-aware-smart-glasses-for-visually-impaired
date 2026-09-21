"""
ablation_study.py
Automated data-logging script for the paper's Experimental Results
section: quantifies azimuth error WITH vs WITHOUT ego-motion
compensation during controlled 45deg and 90deg head-yaw sweeps
(Section 4, PROJECT_PLAN.md).

For each sweep amplitude, a stationary obstacle is placed at a known
torso-frame azimuth. As the simulated head sweeps, we compare:
  - RAW (no compensation): azimuth read straight off the static zone
    table (ego_motion.compensate_frame_raw), i.e. as if the head never
    turned.
  - CORRECTED (with compensation): azimuth from ego_motion.compensate_frame,
    using the current IMU yaw/pitch.
against the known ground-truth obstacle azimuth, and logs the angular
error over time to a CSV plus a console summary for the manuscript.

Usage:
    python ablation_study.py --amplitude 45
    python ablation_study.py --amplitude 90
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import argparse
import csv
import time

import numpy as np

import ego_motion
from sim_sensor import SimSensor

_CLEAR_SENTINEL_MM = 3999.0  # matches sim_sensor's 4000mm "clear" reading


def _nearest_hit_azimuth(fused_frame):
    """Azimuth of the closest (minimum-distance) zone in a fused frame,
    or None if nothing is within range."""
    dist = fused_frame["distance_mm"]
    idx = np.unravel_index(np.argmin(dist), dist.shape)
    if dist[idx] >= _CLEAR_SENTINEL_MM:
        return None
    return float(fused_frame["azimuth_deg"][idx])


def run_ablation(amplitude_deg, obstacle_azimuth_deg=20.0, duration_s=None,
                  sample_hz=30, out_csv=None):
    duration_s = duration_s if duration_s is not None else 6.0  # one full sweep period
    sim = SimSensor(sweep_amplitude_deg=amplitude_deg,
                     sweep_period_s=duration_s,
                     obstacle_azimuth_deg=obstacle_azimuth_deg)

    rows = []
    n_samples = int(duration_s * sample_hz)
    t0 = time.monotonic()

    for _ in range(n_samples):
        distance_mm, yaw, pitch = sim.get_frame()

        raw_frame = ego_motion.compensate_frame_raw(distance_mm)
        corr_frame = ego_motion.compensate_frame(distance_mm, yaw, pitch)

        raw_az = _nearest_hit_azimuth(raw_frame)
        corr_az = _nearest_hit_azimuth(corr_frame)

        raw_err = None if raw_az is None else abs(raw_az - obstacle_azimuth_deg)
        corr_err = None if corr_az is None else abs(corr_az - obstacle_azimuth_deg)

        rows.append({
            "t_s": round(time.monotonic() - t0, 4),
            "head_yaw_deg": round(yaw, 3),
            "ground_truth_az_deg": obstacle_azimuth_deg,
            "raw_measured_az_deg": raw_az,
            "raw_abs_error_deg": raw_err,
            "corrected_measured_az_deg": corr_az,
            "corrected_abs_error_deg": corr_err,
        })
        time.sleep(1.0 / sample_hz)

    out_csv = out_csv or f"ablation_{int(amplitude_deg)}deg.csv"
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    raw_errs = [r["raw_abs_error_deg"] for r in rows if r["raw_abs_error_deg"] is not None]
    corr_errs = [r["corrected_abs_error_deg"] for r in rows if r["corrected_abs_error_deg"] is not None]

    print(f"\n[Ablation] {amplitude_deg} deg sweep -> {out_csv}")
    if raw_errs:
        print(f"  WITHOUT compensation: mean |error| = {np.mean(raw_errs):5.2f} deg  "
              f"(max {np.max(raw_errs):5.2f} deg, n={len(raw_errs)})")
    if corr_errs:
        print(f"  WITH compensation:    mean |error| = {np.mean(corr_errs):5.2f} deg  "
              f"(max {np.max(corr_errs):5.2f} deg, n={len(corr_errs)})")

    return out_csv


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ego-motion ablation study")
    parser.add_argument("--amplitude", type=float, default=45.0,
                         choices=[45.0, 90.0],
                         help="Head-yaw sweep amplitude in degrees (45 or 90)")
    parser.add_argument("--obstacle-az", type=float, default=20.0,
                         help="Ground-truth obstacle azimuth in the torso frame (deg)")
    args = parser.parse_args()

    run_ablation(args.amplitude, obstacle_azimuth_deg=args.obstacle_az)
