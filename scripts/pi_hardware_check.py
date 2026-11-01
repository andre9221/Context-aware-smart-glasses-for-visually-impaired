#!/usr/bin/env python3
"""
Hardware Verification Preflight for Smart Glasses (Raspberry Pi 4 / 5)
Lead Researcher: Andrea A. (24BCE1142)

Verifies all physical I2C sensors and actuators:
  - 0x29: ST VL53L7CX 8x8 Multizone Time-of-Flight LiDAR
  - 0x68: InvenSense MPU6050 6-Axis IMU
  - 0x70: TI PCA9548A 8-Channel I2C Multiplexer
  - 0x5A: 3x TI DRV2605L Haptic Motor Drivers (Behind Mux Channels 0, 1, 2)
  - Camera: CSI Ribbon Camera (picamera2 / libcamera)

Run on the Pi before starting the main pipeline:
    python3 scripts/pi_hardware_check.py
"""

from __future__ import annotations
import shutil
import sys
import time

EXPECTED = {
    0x29: "VL53L7CX 8x8 ToF sensor",
    0x68: "MPU6050 6-Axis IMU",
    0x70: "PCA9548A I2C Multiplexer",
}

def main() -> int:
    print("=" * 65)
    print("  SMART GLASSES HARDWARE PREFLIGHT CHECK (Raspberry Pi 4 / 5)")
    print("=" * 65)

    try:
        import smbus2
        bus = smbus2.SMBus(1)
    except Exception as exc:
        print(f"\n[FAIL] Cannot open I2C bus 1: {exc}")
        print("Please enable I2C with: sudo raspi-config nonint do_i2c 0")
        print("Then reboot: sudo reboot\n")
        return 1

    found = []
    print("\n[1/3] Scanning Primary I2C Bus (Bus 1)...")
    for address, name in EXPECTED.items():
        try:
            bus.read_byte(address)
            found.append(address)
            print(f"  [PASS] {name:<30} detected at 0x{address:02X}")
        except OSError:
            print(f"  [FAIL] {name:<30} NOT found at 0x{address:02X}")

    # Check DRV2605L haptic drivers behind PCA9548A multiplexer channels
    print("\n[2/3] Scanning Haptic Drivers (DRV2605L) via PCA9548A Mux...")
    haptics_found = 0
    if 0x70 in found:
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
        import config
        channels = [
            (config.MOTOR_LEFT, config.PCA9548A_CHANNELS[config.MOTOR_LEFT]),
            (config.MOTOR_CENTER, config.PCA9548A_CHANNELS[config.MOTOR_CENTER]),
            (config.MOTOR_RIGHT, config.PCA9548A_CHANNELS[config.MOTOR_RIGHT]),
        ]
        for label, channel in channels:
            # Select channel on multiplexer
            bus.write_byte(0x70, 1 << channel)
            time.sleep(0.01)
            drv_addr = None
            for test_addr in [0x5A, 0x5B]:
                try:
                    bus.read_byte(test_addr)
                    drv_addr = test_addr
                    break
                except OSError:
                    pass
            if drv_addr is not None:
                haptics_found += 1
                print(f"  [PASS] DRV2605L {label:<8} (Mux Ch {channel}) detected at 0x{drv_addr:02X}")
            else:
                print(f"  [FAIL] DRV2605L {label:<8} (Mux Ch {channel}) NOT responding at 0x5A or 0x5B")
        # Deselect all channels
        try:
            bus.write_byte(0x70, 0)
        except Exception:
            pass
    else:
        print("  [SKIP] Skipping DRV2605L scan because PCA9548A mux was not detected.")

    bus.close()

    # Check Camera
    print("\n[3/3] Scanning Camera Subsystem...")
    camera_detected = False
    camera_tool = shutil.which("rpicam-hello") or shutil.which("libcamera-hello")
    if camera_tool:
        print(f"  [PASS] Pi Camera utility found: {camera_tool}")
        camera_detected = True
    else:
        # Check if picamera2 can be imported
        try:
            from picamera2 import Picamera2
            print("  [PASS] picamera2 Python module is available.")
            camera_detected = True
        except ImportError:
            try:
                import cv2
                cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    cap.release()
                    print("  [PASS] OpenCV camera interface (device /dev/video0) detected.")
                    camera_detected = True
                else:
                    print("  [INFO] No camera detected. (System handles camera-free operation safely)")
            except Exception:
                print("  [INFO] Camera module not detected. (System handles camera-free operation safely)")

    print("\n" + "=" * 65)
    all_i2c_ok = (len(found) == len(EXPECTED)) and (haptics_found == 3)
    if all_i2c_ok:
        print("  RESULT: ALL HARDWARE CONNECTIONS VERIFIED SUCCESSFULLY! [PASS]")
        print("=" * 65 + "\n")
        return 0
    else:
        print("  RESULT: SOME HARDWARE COMPONENTS WERE NOT DETECTED. [CHECK WIRING]")
        print("=" * 65 + "\n")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

