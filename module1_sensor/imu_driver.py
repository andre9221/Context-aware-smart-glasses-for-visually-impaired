"""
imu_driver.py
InvenSense MPU6050 6-axis IMU driver (I2C address 0x68).

Raw accel/gyro sampling at 100 Hz plus a lightweight complementary
filter that outputs head orientation (yaw, pitch) consumed by
ego_motion.py to build the quaternion rotation R(theta_head).

LIMITATION — YAW DRIFT: the MPU6050 has no magnetometer, so yaw is
derived purely by integrating the gyro's Z-axis rate. It is NOT an
absolute reference and will drift over time (typically a few deg/min
with a well-calibrated bias). Pitch and roll ARE drift-corrected
against the gravity vector from the accelerometer, since that's an
absolute reference. For the paper's ablation study this is acceptable
because each sweep trial is short (<10 s); flag this explicitly as a
limitation / future-work item in the manuscript (e.g. adding an
AK8963 magnetometer, or a periodic vision-based yaw reset from
Module 2).
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import time
import math

try:
    import smbus2
except ImportError:  # allows this module to import cleanly off-Pi / in SIMULATION_MODE
    smbus2 = None

from config import I2C_BUS_NUM, MPU6050_I2C_ADDR, COMPLEMENTARY_ALPHA

# MPU6050 register map
_PWR_MGMT_1 = 0x6B
_SMPLRT_DIV = 0x19
_CONFIG = 0x1A
_GYRO_CONFIG = 0x1B
_ACCEL_CONFIG = 0x1C
_ACCEL_XOUT_H = 0x3B
_GYRO_XOUT_H = 0x43

_ACCEL_SCALE = 16384.0   # LSB/g @ +/-2g full-scale range
_GYRO_SCALE = 131.0      # LSB/(deg/s) @ +/-250 deg/s full-scale range


class MPU6050:
    def __init__(self, bus_num=I2C_BUS_NUM, address=MPU6050_I2C_ADDR):
        if smbus2 is None:
            raise RuntimeError(
                "smbus2 not installed. Run with config.SIMULATION_MODE=True, "
                "or `pip install smbus2` on the Pi."
            )
        self.address = address
        self.bus = smbus2.SMBus(bus_num)
        self._init_device()

        # Complementary filter state
        self.pitch = 0.0
        self.yaw = 0.0
        self._last_t = time.monotonic()

        self.gyro_bias = self._calibrate_gyro()

    def _init_device(self):
        self.bus.write_byte_data(self.address, _PWR_MGMT_1, 0x00)    # wake from sleep
        time.sleep(0.05)
        self.bus.write_byte_data(self.address, _SMPLRT_DIV, 0x04)    # 1kHz / (1+4) = 200 Hz base rate
        self.bus.write_byte_data(self.address, _CONFIG, 0x03)         # DLPF ~44 Hz
        self.bus.write_byte_data(self.address, _GYRO_CONFIG, 0x00)    # +/-250 deg/s
        self.bus.write_byte_data(self.address, _ACCEL_CONFIG, 0x00)   # +/-2g

    def _read_word(self, reg):
        high = self.bus.read_byte_data(self.address, reg)
        low = self.bus.read_byte_data(self.address, reg + 1)
        val = (high << 8) | low
        if val >= 0x8000:
            val -= 0x10000
        return val

    def read_raw(self):
        """Returns (ax, ay, az) in g and (gx, gy, gz) in deg/s."""
        ax = self._read_word(_ACCEL_XOUT_H) / _ACCEL_SCALE
        ay = self._read_word(_ACCEL_XOUT_H + 2) / _ACCEL_SCALE
        az = self._read_word(_ACCEL_XOUT_H + 4) / _ACCEL_SCALE
        gx = self._read_word(_GYRO_XOUT_H) / _GYRO_SCALE
        gy = self._read_word(_GYRO_XOUT_H + 2) / _GYRO_SCALE
        gz = self._read_word(_GYRO_XOUT_H + 4) / _GYRO_SCALE
        return ax, ay, az, gx, gy, gz

    def _calibrate_gyro(self, samples=200):
        """Average `samples` gyro readings while stationary to remove
        static bias. Call with the glasses held still (e.g. at boot)."""
        sx = sy = sz = 0.0
        for _ in range(samples):
            _, _, _, gx, gy, gz = self.read_raw()
            sx += gx
            sy += gy
            sz += gz
            time.sleep(0.002)
        n = float(samples)
        return (sx / n, sy / n, sz / n)

    def update(self):
        """Call at IMU_RATE_HZ. Returns (yaw_deg, pitch_deg)."""
        now = time.monotonic()
        dt = max(now - self._last_t, 1e-4)
        self._last_t = now

        ax, ay, az, gx, gy, gz = self.read_raw()
        gx -= self.gyro_bias[0]
        gy -= self.gyro_bias[1]
        gz -= self.gyro_bias[2]

        # Accel-derived pitch (absolute reference, drift-free)
        accel_pitch = math.degrees(math.atan2(-ax, math.sqrt(ay * ay + az * az)))

        # Complementary filter: high-pass gyro integration + low-pass accel correction
        self.pitch = (COMPLEMENTARY_ALPHA * (self.pitch + gy * dt)
                      + (1 - COMPLEMENTARY_ALPHA) * accel_pitch)

        # Yaw: pure gyro integration — see module docstring re: drift
        self.yaw += gz * dt
        self.yaw = ((self.yaw + 180) % 360) - 180  # wrap to [-180, 180]

        return self.yaw, self.pitch

    def zero_yaw(self):
        """Resets the current heading as the new 0° forward reference.
        Call this at boot after the user puts the glasses on and faces
        straight ahead, or periodically to counteract gyro drift.
        Can also be triggered remotely via the caregiver dashboard."""
        self.yaw = 0.0

    def close(self):
        self.bus.close()


if __name__ == "__main__":
    # Hardware smoke test — run directly on the Pi to confirm I2C comms
    # and check the calibrated bias/orientation look sane before integrating.
    imu = MPU6050()
    print(f"[imu_driver] gyro bias (deg/s): {imu.gyro_bias}")
    try:
        for _ in range(20):
            yaw, pitch = imu.update()
            print(f"yaw={yaw:6.1f} deg  pitch={pitch:6.1f} deg")
            time.sleep(0.05)
    finally:
        imu.close()
