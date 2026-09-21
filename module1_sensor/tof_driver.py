"""
tof_driver.py
ST VL53L5CX 8x8 multizone Time-of-Flight LiDAR driver (I2C address 0x29).

Wraps the official VL53L5CX ULD (User Level Driver) via the
`vl53l5cx-ctypes` Python bindings (pip install vl53l5cx-ctypes). The
sensor requires ST's proprietary firmware blob to be uploaded into its
onboard RAM at init time and driven through ST's ranging state
machine — that is not something to reimplement from raw I2C registers,
so this module owns the acquisition + shaping layer on top of the
vendor bindings, matching the pattern used for the other two I2C
peripherals (imu_driver.py, and Module 3's drv2605l_driver.py).

Exposes get_frame() -> 8x8 numpy array of distances in mm, row-major
(row 0 = top of FoV, col 0 = left of FoV), matching the zone layout
assumed by ego_motion.py and zone_classifier.py.
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import time
import numpy as np

from config import TOF_GRID_SIZE, TOF_RATE_HZ

try:
    from vl53l5cx_ctypes import VL53L5CX, RANGING_MODE_CONTINUOUS
except ImportError:  # allows this module to import cleanly off-Pi / in SIMULATION_MODE
    VL53L5CX = None
    RANGING_MODE_CONTINUOUS = None

# ST's "target status" code for a valid, high-confidence return
_STATUS_VALID = 5
_MAX_RANGE_MM = 4000.0  # per BOM spec (Section 3, PROJECT_PLAN.md)


class VL53L5CXDriver:
    def __init__(self, resolution=TOF_GRID_SIZE * TOF_GRID_SIZE, rate_hz=TOF_RATE_HZ):
        if VL53L5CX is None:
            raise RuntimeError(
                "vl53l5cx_ctypes not installed. Run with config.SIMULATION_MODE=True, "
                "or `pip install vl53l5cx-ctypes` on the Pi."
            )
        self.grid = TOF_GRID_SIZE
        self.sensor = VL53L5CX()
        self.sensor.set_resolution(resolution)
        self.sensor.set_ranging_frequency_hz(rate_hz)
        self.sensor.set_ranging_mode(RANGING_MODE_CONTINUOUS)
        self.sensor.start_ranging()

    def frame_ready(self):
        return self.sensor.data_ready()

    def get_frame(self):
        """Blocks until a frame is ready. Returns (distance_mm, status),
        both (N, N) arrays. Zones with an unreliable return are clamped
        to MAX_RANGE (treated as 'clear') rather than left as garbage."""
        while not self.sensor.data_ready():
            time.sleep(0.002)  # Avoid 100% CPU busy-wait spin on Pi
        data = self.sensor.get_data()
        dist = np.array(data.distance_mm, dtype=np.float32).reshape(self.grid, self.grid)
        status = np.array(data.target_status, dtype=np.uint8).reshape(self.grid, self.grid)
        dist[status != _STATUS_VALID] = _MAX_RANGE_MM
        return dist, status

    def close(self):
        self.sensor.stop_ranging()


if __name__ == "__main__":
    # Hardware smoke test — run directly on the Pi with the sensor wired
    # to confirm I2C comms + firmware upload succeed before integrating.
    drv = VL53L5CXDriver()
    print("[tof_driver] VL53L5CX ranging started, printing 5 frames...")
    try:
        for i in range(5):
            d, s = drv.get_frame()
            print(f"frame {i}: min={d.min():.0f}mm max={d.max():.0f}mm "
                  f"valid_zones={(s == _STATUS_VALID).sum()}/{d.size}")
    finally:
        drv.close()
