"""
Module 1 Sensor Fusion Main Process Entrypoint
Lead Researcher: Andrea A. (24BCE1142)

Orchestrates VL53L7CX acquisition, MPU6050 orientation tracking,
quaternion coordinate re-projection, and pushes packets to Queue A.
REAL HARDWARE ONLY — no simulation, no synthetic data.
"""

import time
import sys
from multiprocessing import Queue
from typing import Optional

from config import (
    TOF_SAMPLE_RATE_HZ,
    IMU_SAMPLE_RATE_HZ,
)
import config
from .tof_driver import VL53L7CXDriver
from .imu_driver import MPU6050Driver
from .ego_motion import EgoMotionEngine
from .zone_classifier import ZoneClassifier


def run_sensor_module(queue_out: Queue, stop_event=None, queue_video_feed=None, queue_depth_grid=None):
    """
    Main loop for Module 1.
    Reads REAL sensors, applies ego-motion transform, bins sectors, pushes to queue_out.
    """
    print("[Module 1: Sensor] Starting Process (HARDWARE MODE)")

    ego_engine = EgoMotionEngine()
    zone_classifier = ZoneClassifier()

    # Init IMU FIRST — before VL53L7CX firmware upload
    imu_hw = MPU6050Driver()
    if imu_hw.is_connected:
        print("[Module 1: Sensor] ✅ MPU6050 hardware tracking active")
    else:
        print("[Module 1: Sensor] ⚠️ MPU6050 not on 0x68 — operating with fixed 0° heading")
    tof_hw = VL53L7CXDriver()

    interval = 1.0 / TOF_SAMPLE_RATE_HZ
    frame_count = 0
    consecutive_failures = 0

    try:
        while stop_event is None or not stop_event.is_set():
            t_start = time.time()

            # 1. Acquire REAL IMU orientation
            yaw_deg, pitch_deg, roll_deg = imu_hw.update_orientation()

            # 2. Acquire REAL depth array — skip frame on transient sensor errors
            try:
                depth_matrix = tof_hw.read_distance_matrix()
                consecutive_failures = 0
            except Exception as read_err:
                consecutive_failures += 1
                if consecutive_failures <= 3 or consecutive_failures % 20 == 0:
                    print(f"[Module 1: Sensor] ToF read skipped (attempt {consecutive_failures}): {read_err}")
                # If sensor fails more than 30 consecutive times, re-init
                if consecutive_failures > 30:
                    print("[Module 1: Sensor] Too many failures — re-initializing VL53L7CX...")
                    try:
                        tof_hw.close()
                        import subprocess
                        subprocess.run(["pinctrl", "set", "24", "op", "dh"], capture_output=True)
                        time.sleep(1.0)
                        tof_hw = VL53L7CXDriver()
                        consecutive_failures = 0
                    except Exception as reinit_err:
                        print(f"[Module 1: Sensor] Re-init failed: {reinit_err}")
                time.sleep(0.2)
                continue

            # 3. Novelty 01: Coordinate re-projection to Torso Frame
            sensor_vecs, torso_vecs = ego_engine.process_frame(depth_matrix, yaw_deg, pitch_deg)

            # 4. Spatial Classification & Depth Gating Assessment
            classif_result = zone_classifier.classify(torso_vecs)

            # 5. Construct Packet for Queue A (Sensor -> Vision)
            packet = {
                "timestamp": t_start,
                "frame_id": frame_count,
                "head_yaw_deg": yaw_deg,
                "head_pitch_deg": pitch_deg,
                "depth_matrix": depth_matrix,
                "sensor_vectors": sensor_vecs,
                "torso_vectors": torso_vecs,
                "sectors": classif_result.sectors,
                "critical_sector": classif_result.critical_sector,
                "min_distance_overall_m": classif_result.min_distance_overall_m,
                "interrupt_triggered": classif_result.interrupt_triggered,
                "data_source": "vl53l7cx_8x8",
                "valid_tof_zones": tof_hw.last_valid_zone_count,
                "ground_truth": {},
            }

            # 6. Push depth matrix to dashboard grid queue (drop if full)
            if queue_depth_grid is not None:
                if queue_depth_grid.full():
                    try:
                        queue_depth_grid.get_nowait()
                    except Exception:
                        pass
                try:
                    queue_depth_grid.put_nowait(depth_matrix.tolist())
                except Exception:
                    pass

            # 7. Push to Queue A (drop oldest if full to guarantee real-time)
            if queue_out is not None:
                if queue_out.full():
                    try:
                        queue_out.get_nowait()
                    except Exception:
                        pass
                try:
                    queue_out.put_nowait(packet)
                except Exception:
                    pass

            # 8. Live Terminal 8x8 Grid Display (every 2 frames ~1 Hz update)
            if frame_count % 2 == 0:
                import numpy as np
                cm = depth_matrix * 100.0
                min_cm = classif_result.min_distance_overall_m * 100.0
                crit = classif_result.critical_sector
                gate_active = classif_result.interrupt_triggered  # True when closest < 1.0 m

                print("======================================================================")
                print(f" SMART GLASSES LIVE  |  Frame #{frame_count:04d}  |  Closest: {min_cm:5.1f} cm ({crit})")
                print("======================================================================")
                print("       <-- LEFT (0-2) -->     < CENTER >     <-- RIGHT (5-7) ->")
                print("      C0    C1    C2          C3    C4          C5    C6    C7")
                for r in range(8):
                    row_str = f"R{r}  "
                    for c in range(8):
                        val = cm[r, c]
                        if np.isnan(val) or val <= 5.0:
                            cell = f"\033[90m Far \033[0m"
                        elif val >= 350.0:
                            cell = f"\033[90m Far \033[0m"   # Grey = Far / out of range
                        elif val < 30.0:
                            cell = f"\033[91m{val:4.0f}!\033[0m"   # Red   = Danger  (<30 cm)
                        elif val < 100.0:
                            cell = f"\033[93m{val:4.0f} \033[0m"   # Yellow = Caution (30-100 cm)
                        else:
                            cell = f"\033[92m{val:4.0f} \033[0m"   # Green  = Safe   (>100 cm)
                        row_str += cell + " "
                        if c == 2 or c == 4:
                            row_str += "| "
                    print(row_str)

                # Sector Distances and Motor Vibrating Feedback
                sec_left   = classif_result.sectors.get("LEFT")
                sec_center = classif_result.sectors.get("CENTER")
                sec_right  = classif_result.sectors.get("RIGHT")
                d_l = (sec_left.min_distance_m   * 100.0) if sec_left   and not np.isinf(sec_left.min_distance_m)   else 999.0
                d_c = (sec_center.min_distance_m * 100.0) if sec_center and not np.isinf(sec_center.min_distance_m) else 999.0
                d_r = (sec_right.min_distance_m  * 100.0) if sec_right  and not np.isinf(sec_right.min_distance_m)  else 999.0

                haptics = []
                if d_l < 35.0:
                    haptics.append("\033[91m[LEFT VIBRATING]\033[0m")
                if d_c < 35.0:
                    haptics.append("\033[91m[CENTER VIBRATING]\033[0m")
                if d_r < 35.0:
                    haptics.append("\033[91m[RIGHT VIBRATING]\033[0m")
                haptic_display = "  ".join(haptics) if haptics else "\033[90m[MOTORS QUIET]\033[0m"

                if gate_active:
                    gate_str = f"\033[91m[STAGE 2: CAM AWAKE  --  obstacle at {min_cm:.0f} cm]\033[0m"
                else:
                    gate_str = "\033[90m[STAGE 1 IDLE: CAM ASLEEP  >100 cm]\033[0m"

                print("----------------------------------------------------------------------")
                print(f" HEAD KINEMATICS:   Yaw: {yaw_deg:+6.1f}deg  |  Pitch: {pitch_deg:+6.1f}deg  |  Roll: {roll_deg:+6.1f}deg")
                print(f" SECTOR DISTANCES:  Left: {d_l:5.1f} cm | Center: {d_c:5.1f} cm | Right: {d_r:5.1f} cm")
                print(f" HAPTIC FEEDBACK:   {haptic_display}")
                print(f" DEPTH GATE:        {gate_str}")
                print(f" WEB DASHBOARD:     http://192.168.137.172:8080")
                print("======================================================================")\

            frame_count += 1

            # Sleep to match target rate
            elapsed = time.time() - t_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("[Module 1: Sensor] Stopping on user interrupt...")
    finally:
        tof_hw.close()
        imu_hw.close()
        print("[Module 1: Sensor] Exited cleanly.")


if __name__ == "__main__":
    print("=== Module 1 (Sensor Fusion & Ego-Motion) — run via main.py --real ===")
