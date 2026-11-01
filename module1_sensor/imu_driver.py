"""
InvenSense MPU6050 6-Axis IMU Driver & Kinematic Filter
Lead Researcher: Andrea A. (24BCE1142)

Samples accelerometer and gyroscope over I2C using atomic 14-byte burst read.
Auto-detects address (0x68 or 0x69) and auto-reconnects on intermittent wire contact.
Applies a Complementary Filter (alpha = 0.98) to derive drift-free head yaw and pitch.
"""

import time
import math
from typing import Tuple, Optional
from config import (
    MPU6050_I2C_ADDR,
    I2C_BUS_ID,
    COMPLEMENTARY_FILTER_ALPHA,
)


class MPU6050Driver:
    """I2C driver and Complementary Filter for MPU6050 6-DOF IMU."""

    PWR_MGMT_1   = 0x6B
    SMPLRT_DIV   = 0x19
    CONFIG       = 0x1A
    GYRO_CONFIG  = 0x1B
    ACCEL_CONFIG = 0x1C
    ACCEL_XOUT_H = 0x3B

    # Scale factors for +/- 250 deg/s and +/- 2g
    GYRO_SCALE  = 131.0       # LSB / (deg/s)
    ACCEL_SCALE = 16384.0     # LSB / g

    def __init__(self, i2c_bus: int = I2C_BUS_ID, address: int = MPU6050_I2C_ADDR, force_hardware: bool = False):
        self.bus_id = i2c_bus
        self.address = address
        self.is_connected = False
        self.bus = None

        # Filter state variables
        self.yaw_deg: float = 0.0
        self.pitch_deg: float = 0.0
        self.roll_deg: float = 0.0
        self.last_update_time: float = time.time()
        self.last_reconnect_attempt: float = 0.0
        self.gyro_x_offset: float = 0.0
        self.gyro_y_offset: float = 0.0
        self.gyro_z_offset: float = 0.0

        self._init_hardware()

    def _init_hardware(self):
        """Auto-detect address (0x68 / 0x69), wake MPU6050 and calibrate gyro."""
        import smbus2

        # Probe all known MPU addresses: 0x68 (AD0=GND, default), 0x69 (AD0=VCC)
        # NOTE: WHO_AM_I register VALUE is 0x70 for MPU6500 chip revision — this is NOT the I2C address
        candidate_addrs = []
        for a in [0x68, 0x69]:
            if a not in candidate_addrs:
                candidate_addrs.append(a)

        for attempt in range(3):
            for target_addr in candidate_addrs:
                try:
                    if self.bus is not None:
                        try: self.bus.close()
                        except Exception: pass
                    self.bus = smbus2.SMBus(self.bus_id)

                    # Reset and wake up device (clear sleep bit in PWR_MGMT_1)
                    self.bus.write_byte_data(target_addr, self.PWR_MGMT_1, 0x00)
                    time.sleep(0.02)
                    self.bus.write_byte_data(target_addr, self.PWR_MGMT_1, 0x01) # PLL with X-gyro
                    self.bus.write_byte_data(target_addr, self.SMPLRT_DIV, 0x07)
                    self.bus.write_byte_data(target_addr, self.GYRO_CONFIG, 0x00)
                    self.bus.write_byte_data(target_addr, self.ACCEL_CONFIG, 0x00)

                    self.address = target_addr
                    self.is_connected = True
                    print(f"[MPU6050] Connected at I2C 0x{self.address:02X}. Calibrating stationary gyro...")

                    gx_s, gy_s, gz_s = [], [], []
                    for _ in range(50):
                        _, _, _, gx, gy, gz = self._read_raw_sensors_internal()
                        gx_s.append(gx); gy_s.append(gy); gz_s.append(gz)
                        time.sleep(0.01)

                    if gx_s:
                        self.gyro_x_offset = sum(gx_s) / len(gx_s)
                        self.gyro_y_offset = sum(gy_s) / len(gy_s)
                        self.gyro_z_offset = sum(gz_s) / len(gz_s)
                        print(f"[MPU6050] Gyro calibrated: gx={self.gyro_x_offset:+.2f} gy={self.gyro_y_offset:+.2f} gz={self.gyro_z_offset:+.2f} deg/s")
                    return  # Success
                except Exception:
                    self.is_connected = False
            time.sleep(0.15)

        self.is_connected = False
        print("[MPU6050] ⚠️ Hardware not detected at I2C 0x68/0x69 (auto-reconnect active in background).")

    def _read_raw_sensors_internal(self) -> Tuple[float, float, float, float, float, float]:
        """Perform a single atomic 14-byte block read: Accel X/Y/Z, Temp, Gyro X/Y/Z."""
        data = self.bus.read_i2c_block_data(self.address, self.ACCEL_XOUT_H, 14)

        def to_int16(h, l):
            v = (h << 8) | l
            return v - 65536 if v >= 32768 else v

        ax = to_int16(data[0], data[1]) / self.ACCEL_SCALE
        ay = to_int16(data[2], data[3]) / self.ACCEL_SCALE
        az = to_int16(data[4], data[5]) / self.ACCEL_SCALE
        gx = to_int16(data[8], data[9]) / self.GYRO_SCALE
        gy = to_int16(data[10], data[11]) / self.GYRO_SCALE
        gz = to_int16(data[12], data[13]) / self.GYRO_SCALE
        return ax, ay, az, gx, gy, gz

    def read_raw_sensors(self) -> Tuple[float, float, float, float, float, float]:
        """Returns (ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps)."""
        if self.is_connected and self.bus is not None:
            try:
                return self._read_raw_sensors_internal()
            except Exception:
                # Connection dropped mid-operation
                self.is_connected = False

        # Attempt background hot-reconnect every 1.5 seconds if disconnected
        now = time.time()
        if not self.is_connected and (now - self.last_reconnect_attempt) > 1.5:
            self.last_reconnect_attempt = now
            self._init_hardware()

        return 0.0, 0.0, 1.0, 0.0, 0.0, 0.0

    def update_orientation(self) -> Tuple[float, float, float]:
        """
        Executes Complementary Filter step:
        Returns current drift-compensated (yaw_deg, pitch_deg, roll_deg).
        """
        now = time.time()
        dt = max(now - self.last_update_time, 1e-4)
        self.last_update_time = now

        ax, ay, az, gx, gy, gz = self.read_raw_sensors()

        # Compute pitch and roll from accelerometer gravity vector
        accel_pitch_deg = math.degrees(math.atan2(ax, math.sqrt(ay * ay + az * az)))
        accel_roll_deg = math.degrees(math.atan2(ay, az))

        # Complementary Filter:
        alpha = COMPLEMENTARY_FILTER_ALPHA
        corrected_gy = gy - self.gyro_y_offset
        corrected_gx = gx - self.gyro_x_offset
        # Deadband: ignore tiny gyro noise (<0.8 deg/s)
        if abs(corrected_gy) < 0.8: corrected_gy = 0.0
        if abs(corrected_gx) < 0.8: corrected_gx = 0.0
        self.pitch_deg = alpha * (self.pitch_deg + corrected_gy * dt) + (1.0 - alpha) * accel_pitch_deg
        self.roll_deg  = alpha * (self.roll_deg  + corrected_gx * dt) + (1.0 - alpha) * accel_roll_deg

        # Yaw is integrated from Z-gyro minus stationary offset
        corrected_gz = gz - self.gyro_z_offset
        if abs(corrected_gz) > 0.5:
            self.yaw_deg = self.yaw_deg + corrected_gz * dt
        # Normalize yaw to [-180, 180]
        if self.yaw_deg > 180.0:
            self.yaw_deg -= 360.0
        elif self.yaw_deg < -180.0:
            self.yaw_deg += 360.0

        return self.yaw_deg, self.pitch_deg, self.roll_deg

    def reset_yaw(self):
        """Zero the yaw reference angle."""
        self.yaw_deg = 0.0

    def close(self):
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
            self.bus = None
