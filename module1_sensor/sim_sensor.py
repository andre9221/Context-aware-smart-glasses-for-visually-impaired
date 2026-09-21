"""
sim_sensor.py
Hardware-free simulator for Module 1. Lets Dhivyashree and Tejaswi build
and test Modules 2/3 without a Pi + VL53L5CX + MPU6050 wired up, and lets
Andrea generate repeatable head-sweep datasets for the ablation study.

Produces the same shapes tof_driver.get_frame() and imu_driver.update()
would: an (N, N) distance_mm array and a (yaw_deg, pitch_deg) pair.
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import time
import math

import numpy as np

from config import TOF_GRID_SIZE
from ego_motion import _ZONE_AZ_DEG, _ZONE_EL_DEG  # reuse the real zone table


class SimSensor:
    def __init__(self, sweep_amplitude_deg=45.0, sweep_period_s=6.0,
                 obstacle_azimuth_deg=20.0, obstacle_distance_mm=1200.0,
                 obstacle_width_deg=15.0, grid=TOF_GRID_SIZE):
        """
        obstacle_azimuth_deg is defined in the TORSO frame (i.e. a fixed
        real-world obstacle). As the simulated head sweeps, the obstacle
        appears to move across the raw sensor frame — exactly the effect
        ego_motion.py is meant to correct for.
        """
        self.t0 = time.monotonic()
        self.amp = sweep_amplitude_deg
        self.period = sweep_period_s
        self.obstacle_az = obstacle_azimuth_deg
        self.obstacle_dist = obstacle_distance_mm
        self.obstacle_width = obstacle_width_deg
        self.grid = grid
        self._zone_az = _ZONE_AZ_DEG
        self._zone_el = _ZONE_EL_DEG

    def _sim_head_yaw(self, t):
        """Sinusoidal +/-amplitude yaw sweep, matching the ablation
        study's 45deg / 90deg sweep protocol (Section 4, PROJECT_PLAN.md)."""
        return self.amp * math.sin(2 * math.pi * t / self.period)

    def get_frame(self):
        """Returns (distance_mm[N,N], yaw_deg, pitch_deg) for the current
        simulated instant, mimicking one synchronized read of both sensors."""
        t = time.monotonic() - self.t0
        yaw = self._sim_head_yaw(t)
        pitch = 3.0 * math.sin(2 * math.pi * t / (self.period * 2.3))  # small nod noise

        # Obstacle's apparent azimuth in the SENSOR (head) frame = its real
        # torso-frame azimuth minus the current head yaw.
        apparent_az = self.obstacle_az - yaw

        dist = np.full((self.grid, self.grid), 4000.0, dtype=np.float32)  # max range = "clear"
        hit = np.abs(self._zone_az - apparent_az) < (self.obstacle_width / 2.0)
        dist[hit] = self.obstacle_dist

        return dist, yaw, pitch


if __name__ == "__main__":
    sim = SimSensor()
    for _ in range(10):
        d, y, p = sim.get_frame()
        near = int(np.min(d))
        print(f"yaw={y:6.1f} deg  pitch={p:5.1f} deg  nearest_zone={near} mm")
        time.sleep(0.3)
