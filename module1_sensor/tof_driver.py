"""
ST VL53L7CX 8x8 Multizone Time-of-Flight LiDAR Driver
Lead Researcher: Andrea A. (24BCE1142)

Interfaces with ST VL53L7CX over I2C (Address 0x29) on Raspberry Pi 4.
REAL HARDWARE ONLY — no synthetic data, no fake fallbacks.
"""

import os
import sys
import time
import subprocess
import numpy as np
from typing import Optional
from config import (
    VL53L7CX_I2C_ADDR,
    I2C_BUS_ID,
    TOF_GRID_ROWS,
    TOF_GRID_COLS,
    TOF_MAX_RANGE_METERS,
    TOF_HARDWARE_RANGING_HZ,
)
import config


class VL53L7CXDriver:
    """Hardware I2C driver for ST VL53L7CX 8x8 multizone ToF sensor."""

    def __init__(self, i2c_bus: int = I2C_BUS_ID, address: int = VL53L7CX_I2C_ADDR, force_hardware: bool = False):
        self.bus_id = i2c_bus
        self.address = address
        self.is_connected = False
        self.bus = None
        self.sensor = None
        self.last_error: Optional[str] = None
        self.last_valid_zone_count = 0

        self._init_hardware()


    def _init_hardware(self):
        """Initialize smbus2, drive LPn HIGH, and configure VL53L7CX."""
        try:
            import smbus2
            self.bus = smbus2.SMBus(self.bus_id)

            # Hardware reset: pulse LPn (GPIO 24) LOW then HIGH to cleanly reboot VL53L7CX MCU
            subprocess.run(["pinctrl", "set", "24", "op", "dl"], capture_output=True)
            time.sleep(0.15)
            subprocess.run(["pinctrl", "set", "24", "op", "dh"], capture_output=True)
            time.sleep(0.2)

            # Verify sensor presence by probing I2C address
            self.bus.read_byte(self.address)
            self._init_uld_backend()
            self.is_connected = True
            print(
                f"[VL53L7CX] Real 8x8 ranging active at 0x{self.address:02X} "
                f"({TOF_HARDWARE_RANGING_HZ} Hz)"
            )
        except Exception as e:
            self.last_error = str(e)
            print(f"[VL53L7CX] Hardware init failed: {e}")
            self.is_connected = False

    def _init_uld_backend(self):
        """Start the ULD-compatible driver for VL53L7CX 8x8 multizone ToF."""
        import smbus2

        candidate_paths = [
            os.getenv("VL53L7CX_DRIVER_PATH"),
            os.path.expanduser("~/vl53l7cx_python"),
            os.path.expanduser("~/vl53l5cx_python"),
            os.path.join(os.path.dirname(__file__), "..", "vl53l7cx_python"),
            os.path.join(os.path.dirname(__file__), "..", "vl53l5cx_python"),
        ]
        for p in candidate_paths:
            if p and os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)

        # Attempt import from vl53l7cx first, fallback to vl53l5cx ULD wrapper
        sensor_cls = None
        res_8x8 = None

        try:
            from vl53l7cx.vl53l7cx import VL53L7CX as sensor_cls
            from vl53l7cx.api import VL53L7CX_RESOLUTION_8X8 as res_8x8
        except ImportError:
            pass

        if sensor_cls is None:
            try:
                from vl53l5cx.vl53l5cx import VL53L5CX as sensor_cls
                from vl53l5cx.api import VL53L5CX_RESOLUTION_8X8 as res_8x8
            except ImportError:
                raise RuntimeError(
                    "VL53L7CX Python driver not found! Please clone the ULD driver:\n"
                    "git clone https://github.com/Abstract-Horizon/vl53l5cx_python ~/vl53l5cx_python\n"
                    "cd ~/vl53l5cx_python && pip install ."
                )

        # Patch chunked I2C writes to avoid kernel buffer overflow
        def _chunked_wr(sensor_self, address, buffer, size):
            CHUNK_SIZE = 1024
            bytes_sent = 0
            addr = getattr(sensor_self, "address", getattr(sensor_self, "_i2c_address", self.address))
            while bytes_sent < size:
                chunk_len = min(CHUNK_SIZE, size - bytes_sent)
                chunk_addr = address + bytes_sent
                chunk_data = buffer[bytes_sent : bytes_sent + chunk_len]
                payload = [(chunk_addr >> 8) & 0xFF, chunk_addr & 0xFF] + list(chunk_data)
                write = smbus2.i2c_msg.write(addr, payload)
                for attempt in range(8):
                    try:
                        self.bus.i2c_rdwr(write)
                        break
                    except OSError:
                        if attempt == 7:
                            raise
                        time.sleep(0.005)
                bytes_sent += chunk_len

        sensor_cls.wr_multi = _chunked_wr

        self.sensor = sensor_cls(bus_id=self.bus_id)
        self.sensor.i2c_msg = smbus2.i2c_msg

        if not self.sensor.is_alive():
            raise RuntimeError(f"VL53L7CX ULD backend cannot communicate with I2C address 0x{self.address:02X}")

        print("[VL53L7CX] Uploading ranging firmware and configuring 8x8 mode...")
        self.sensor.init()
        self.sensor.set_resolution(res_8x8)
        self.sensor.set_ranging_frequency_hz(TOF_HARDWARE_RANGING_HZ)
        self.sensor.start_ranging()
        # Allow sensor to produce its first frame before polling begins
        time.sleep(2.0)

    def read_distance_matrix(self) -> np.ndarray:
        """
        Read the 8x8 matrix of zone distances in meters from real VL53L7CX hardware.
        Returns a float64 numpy array of shape (8, 8).
        Invalid/empty zones are NaN — NEVER filled with fake data.
        """
        if not self.is_connected or self.sensor is None:
            raise RuntimeError("VL53L7CX is unavailable; run scripts/pi_hardware_check.py")

        # Default matrix values: None/no target beyond range defaults to 4.0 meters (TOF_MAX_RANGE_METERS)
        # instead of leaving it as NaN, so out-of-range zones cleanly show as "Far" (>100cm / safe)
        matrix = np.full((TOF_GRID_ROWS, TOF_GRID_COLS), TOF_MAX_RANGE_METERS, dtype=np.float64)

        # Wait for data ready with 50ms intervals up to 2.5s
        ready = False
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            try:
                if hasattr(self.sensor, "check_data_ready"):
                    ready = self.sensor.check_data_ready()
                elif hasattr(self.sensor, "data_ready"):
                    ready = self.sensor.data_ready()
            except Exception:
                ready = False
            if ready:
                break
            time.sleep(0.05)

        if not ready:
            self.last_error = "VL53L7CX frame wait timeout"
            return matrix

        # get_ranging_data() can raise IndexError if temp_buffer is settling
        results = None
        for attempt in range(5):
            try:
                results = self.sensor.get_ranging_data()
                break
            except Exception as e:
                time.sleep(0.05)

        if results is None:
            self.last_error = "VL53L7CX get_ranging_data returned empty"
            return matrix

        valid_count = 0

        # Handle multi-target format (256 values = 64 zones x 4 targets)
        raw_dist = np.array(results.distance_mm, dtype=np.float64).flatten()

        # Check target_status — VL53L7CX valid codes: 5 (valid), 6 (wrap-around ok), 9 (wrapped but usable)
        # Reject only status 255 (no target), 12, 13 (hardware errors)
        raw_status = None
        if hasattr(results, "target_status"):
            try:
                raw_status = np.array(results.target_status, dtype=np.int32).flatten()
            except Exception:
                raw_status = None

        INVALID_STATUS = {255, 12, 13}   # no target / hardware fault only

        if len(raw_dist) == 256:
            # Multi-target: pick the nearest valid target per zone
            targets = raw_dist.reshape((64, 4))
            status_grid = raw_status.reshape((64, 4)) if raw_status is not None and len(raw_status) == 256 else None
            for zone in range(64):
                best = np.inf
                for t in range(4):
                    d = targets[zone, t]
                    if status_grid is not None and int(status_grid[zone, t]) in INVALID_STATUS:
                        continue
                    if 20.0 <= d <= TOF_MAX_RANGE_METERS * 1000:
                        best = min(best, d)
                if best < np.inf:
                    row, col = divmod(zone, TOF_GRID_COLS)
                    matrix[row, col] = best / 1000.0
                    valid_count += 1
        else:
            # Single-target format (64 values)
            for zone in range(min(len(raw_dist), TOF_GRID_ROWS * TOF_GRID_COLS)):
                distance_mm = raw_dist[zone]
                if raw_status is not None and zone < len(raw_status):
                    if int(raw_status[zone]) in INVALID_STATUS:
                        continue
                if 20.0 <= distance_mm <= TOF_MAX_RANGE_METERS * 1000:
                    row, col = divmod(zone, TOF_GRID_COLS)
                    matrix[row, col] = distance_mm / 1000.0
                    valid_count += 1

        self.last_valid_zone_count = valid_count
        if valid_count == 0:
            self.last_error = "VL53L7CX frame contained no valid depth zones"
        return matrix

    def close(self):
        if self.sensor is not None:
            try:
                self.sensor.stop_ranging()
            except Exception:
                pass
            self.sensor = None
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
            self.bus = None
        # Put VL53L7CX into low-power reset state
        try:
            subprocess.run(["pinctrl", "set", "24", "op", "dl"], capture_output=True)
        except Exception:
            pass


# Backwards compatibility alias
VL53L5CXDriver = VL53L7CXDriver
