#!/usr/bin/env python3
"""
Unified Hardware Test for Smart Glasses (Raspberry Pi 4)
Tests ALL physical hardware concurrently in terminal:
1. ST VL53L7CX 8x8 Depth Grid (in cm)
2. InvenSense MPU6050 6-Axis IMU (Yaw, Pitch, Roll)
3. 3x TI DRV2605L Haptic Motors (Left, Center, Right) via PCA9548A MUX
"""

import sys
import os
import time
from pathlib import Path
import numpy as np

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from module1_sensor.tof_driver import VL53L7CXDriver
from module1_sensor.imu_driver import MPU6050Driver
from module3_haptic.drv2605l_driver import DRV2605LDriver

def main():
    print("=" * 70)
    print(" SMART GLASSES — FULL HARDWARE BENCH TEST")
    print("=" * 70)
    print("Connecting to physical I2C bus...")

    # 1. Initialize IMU (MPU6050)
    print("\n[1/3] Initializing MPU6050 IMU (0x68)...")
    imu = MPU6050Driver(force_hardware=True)
    if imu.is_connected:
        print("      ✅ MPU6050 Connected and Calibrated!")
    else:
        print("      ⚠️ MPU6050 not detected at 0x68")

    # 2. Initialize Haptics (3x DRV2605L via PCA9548A)
    print("\n[2/3] Initializing 3x DRV2605L Haptics via PCA9548A (0x70)...")
    haptic = DRV2605LDriver(force_hardware=True)
    if haptic.is_connected:
        print("      ✅ DRV2605L Haptic Drivers Ready!")
        print("      >>> Self-testing LRA motors (Feel for vibrations)...")
        print(f"          Buzzing LEFT motor (CH{config.PCA9548A_CHANNELS[config.MOTOR_LEFT]})...", end="", flush=True)
        haptic.trigger_waveform(config.MOTOR_LEFT, 47)  # Buzz 1 - 100%
        time.sleep(0.5)
        print(" [OK]")
        print(f"          Buzzing CENTER motor (CH{config.PCA9548A_CHANNELS[config.MOTOR_CENTER]})...", end="", flush=True)
        haptic.trigger_waveform(config.MOTOR_CENTER, 47)
        time.sleep(0.5)
        print(" [OK]")
        print(f"          Buzzing RIGHT motor (CH{config.PCA9548A_CHANNELS[config.MOTOR_RIGHT]})...", end="", flush=True)
        haptic.trigger_waveform(config.MOTOR_RIGHT, 47)
        time.sleep(0.5)
        print(" [OK]")
    else:
        print("      ⚠️ Haptic drivers not detected at 0x70 / 0x5A")

    # 3. Initialize ToF (VL53L7CX)
    print("\n[3/3] Initializing VL53L7CX 8x8 ToF Sensor (0x29)...")
    tof = VL53L7CXDriver(force_hardware=True)
    if tof.is_connected:
        print("      ✅ VL53L7CX 8x8 Ranging Active!")
    else:
        print("      ❌ VL53L7CX failed to initialize!")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(" ALL HARDWARE ACTIVE! Wave hand over sensor to test.")
    print(" Left columns (0-2) trigger LEFT motor.")
    print(" Center columns (3-4) trigger CENTER motor.")
    print(" Right columns (5-7) trigger RIGHT motor.")
    print(" Press Ctrl+C to stop.")
    print("=" * 70)
    time.sleep(1.5)

    last_buzz_time = {
        config.MOTOR_LEFT: 0.0,
        config.MOTOR_CENTER: 0.0,
        config.MOTOR_RIGHT: 0.0,
    }

    try:
        frame_idx = 0
        while True:
            # 1. Read IMU
            yaw, pitch, roll = imu.update_orientation()

            # 2. Read ToF Depth Grid
            m = tof.read_distance_matrix()
            cm = m * 100.0  # convert meters to cm

            # 3. Analyze Sectors for Haptic Feedback (<35 cm triggers motor)
            # Left: cols 0..2
            # Center: cols 3..4
            # Right: cols 5..7
            left_sector = cm[:, 0:3]
            center_sector = cm[:, 3:5]
            right_sector = cm[:, 5:8]

            def min_valid(arr):
                v = arr[(arr > 5) & (arr < 400)]
                return float(v.min()) if len(v) > 0 else 999.0

            d_left = min_valid(left_sector)
            d_center = min_valid(center_sector)
            d_right = min_valid(right_sector)

            now = time.time()
            motor_status = []

            # Haptic triggering with 0.3s cooldown
            if d_left < 35.0 and (now - last_buzz_time[config.MOTOR_LEFT]) > 0.3:
                haptic.trigger_waveform(config.MOTOR_LEFT, 47)
                last_buzz_time[config.MOTOR_LEFT] = now
                motor_status.append("\033[91m[LEFT VIBRATING]\033[0m")
            elif d_left < 35.0:
                motor_status.append("\033[93m[LEFT ALERT]\033[0m")

            if d_center < 35.0 and (now - last_buzz_time[config.MOTOR_CENTER]) > 0.3:
                haptic.trigger_waveform(config.MOTOR_CENTER, 47)
                last_buzz_time[config.MOTOR_CENTER] = now
                motor_status.append("\033[91m[CENTER VIBRATING]\033[0m")
            elif d_center < 35.0:
                motor_status.append("\033[93m[CENTER ALERT]\033[0m")

            if d_right < 35.0 and (now - last_buzz_time[config.MOTOR_RIGHT]) > 0.3:
                haptic.trigger_waveform(config.MOTOR_RIGHT, 47)
                last_buzz_time[config.MOTOR_RIGHT] = now
                motor_status.append("\033[91m[RIGHT VIBRATING]\033[0m")
            elif d_right < 35.0:
                motor_status.append("\033[93m[RIGHT ALERT]\033[0m")

            # 4. Render Terminal UI
            print("\033[2J\033[H")  # Clear screen and return cursor to top-left
            print("======================================================================")
            print(f" SMART GLASSES LIVE BENCH TEST | Frame #{frame_idx:04d}")
            print("======================================================================")
            print(f" HEAD KINEMATICS (MPU6050):")
            print(f"   Yaw: \033[96m{yaw:+6.1f}°\033[0m  |  Pitch: \033[96m{pitch:+6.1f}°\033[0m  |  Roll: \033[96m{roll:+6.1f}°\033[0m")
            print("----------------------------------------------------------------------")
            print(" TIME-OF-FLIGHT 8x8 DEPTH MATRIX (cm):")
            print("       <-- LEFT (0-2) -->     < CENTER >     <-- RIGHT (5-7) ->")
            print("      C0    C1    C2          C3    C4          C5    C6    C7")

            for r in range(8):
                row_str = f"R{r}  "
                for c in range(8):
                    val = cm[r, c]
                    if val <= 5.0 or val >= 400.0 or np.isnan(val):
                        cell = " --- "
                    elif val < 30.0:
                        cell = f"\033[91m{val:4.0f}!\033[0m"  # Red = Danger
                    elif val < 100.0:
                        cell = f"\033[93m{val:4.0f} \033[0m"  # Yellow = Caution
                    else:
                        cell = f"\033[92m{val:4.0f} \033[0m"  # Green = Safe
                    row_str += cell + " "
                    if c == 2 or c == 4:
                        row_str += "| "
                print(row_str)

            print("----------------------------------------------------------------------")
            print(f" SECTOR DISTANCES:  Left: {d_left:5.1f} cm | Center: {d_center:5.1f} cm | Right: {d_right:5.1f} cm")
            haptic_display = "  ".join(motor_status) if motor_status else "\033[90m[MOTORS QUIET]\033[0m"
            print(f" HAPTIC FEEDBACK:   {haptic_display}")
            print("======================================================================")
            print(" LEGEND: \033[91m■ <30cm (Danger)\033[0m | \033[93m■ 30-100cm (Caution)\033[0m | \033[92m■ >100cm (Safe)\033[0m")
            print(" Press Ctrl+C to return.")

            frame_idx += 1
            time.sleep(0.15)

    except KeyboardInterrupt:
        print("\nStopping hardware drivers...")
    finally:
        tof.close()
        imu.close()
        haptic.stop()
        print("Hardware closed cleanly. Done.\n")

if __name__ == "__main__":
    main()

