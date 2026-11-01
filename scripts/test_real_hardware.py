#!/usr/bin/env python3
"""
Real Hardware Verification Script for VL53L7CX, MPU6050, and 3x DRV2605L
Lead Researcher: Andrea A. (24BCE1142)

Tests physical MPU6050 and VL53L7CX sensor readings directly over I2C,
and verifies haptic feedback pulses on Left, Center, and Right LRAs.
"""

import time
import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

from config import (
    VL53L7CX_I2C_ADDR,
    MPU6050_I2C_ADDR,
    PCA9548A_I2C_ADDR,
    MOTOR_LEFT,
    MOTOR_CENTER,
    MOTOR_RIGHT,
)
from module1_sensor.imu_driver import MPU6050Driver
from module1_sensor.tof_driver import VL53L7CXDriver
from module3_haptic.drv2605l_driver import DRV2605LDriver


def main():
    print("=" * 68)
    print(" REAL HARDWARE SENSOR & HAPTIC PROBE (Raspberry Pi 4 / 5)")
    print(f" [*] VL53L7CX ToF LiDAR: 0x{VL53L7CX_I2C_ADDR:02X}")
    print(f" [*] MPU6050 6-Axis IMU: 0x{MPU6050_I2C_ADDR:02X}")
    print(f" [*] PCA9548A Multiplex: 0x{PCA9548A_I2C_ADDR:02X} (Left/Center/Right Haptics)")
    print("=" * 68)

    imu = MPU6050Driver(force_hardware=True)
    tof = VL53L7CXDriver(force_hardware=True)
    haptics = DRV2605LDriver(force_hardware=True)

    print(f"\n-> MPU6050 Status     : {'CONNECTED (Active)' if imu.is_connected else 'FAILED TO CONNECT'}")
    print(f"-> VL53L7CX Status    : {'CONNECTED (Active)' if tof.is_connected else 'FAILED TO CONNECT'}")
    print(f"-> Haptic PCA9548A    : {'CONNECTED (3 Channels Active)' if haptics.is_connected else 'NOT DETECTED'}")

    # Quick test buzz on Left, Middle, Right motors
    if haptics.is_connected:
        print("\n[Testing Haptic Pulse Sequence]...")
        for ch in [MOTOR_LEFT, MOTOR_CENTER, MOTOR_RIGHT]:
            print(f"  * Pulsing {ch} motor...")
            haptics.trigger_waveform(ch, 1)  # Strong Click
            time.sleep(0.4)

    print("\nReading physical sensors in real-time (Press Ctrl+C to stop)...\n")

    try:
        while True:
            # Read real IMU
            yaw, pitch, roll = imu.update_orientation()
            ax, ay, az, gx, gy, gz = imu.read_raw_sensors()

            # Read real ToF 8x8 matrix
            depth_matrix = tof.read_distance_matrix()
            center_dist = depth_matrix[3:5, 3:5].mean()
            min_dist = depth_matrix.min()

            # Live terminal print
            sys.stdout.write(
                f"\r[REAL IMU] Yaw: {yaw:6.1f} deg | Pitch: {pitch:6.1f} deg | Roll: {roll:6.1f} deg   "
                f"[REAL VL53L7CX] Min Dist: {min_dist:4.2f}m | Center: {center_dist:4.2f}m   "
            )
            sys.stdout.flush()
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n\nTest stopped cleanly.")
    finally:
        imu.close()
        tof.close()
        haptics.close()


if __name__ == "__main__":
    main()
