"""
main_sensor.py
Process entry point for Module 1 (Andrea): runs the sensor fusion loop
and pushes ego-motion-corrected, zone-classified obstacle packets onto
Queue A for Module 2 (Dhivyashree's vision/TTC pipeline).

Runs standalone for testing:  python main_sensor.py
Runs as a subprocess of the root main.py in the full pipeline, given a
real multiprocessing.Queue as `out_queue`.
"""

import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import time
import queue as queue_module

from config import SIMULATION_MODE, FUSION_LOOP_HZ, QUEUE_MAXSIZE
import ego_motion
from zone_classifier import classify

if SIMULATION_MODE:
    from sim_sensor import SimSensor
else:
    from tof_driver import VL53L5CXDriver
    from imu_driver import MPU6050


def run_sensor_module(out_queue, run_seconds=None):
    """
    Args:
      out_queue: multiprocessing.Queue (Queue A). A plain queue.Queue also
                 works for standalone/unit testing.
      run_seconds: stop after this many seconds (None = run forever; used
                   by the root main.py's long-lived subprocess).
    """
    period = 1.0 / FUSION_LOOP_HZ

    if SIMULATION_MODE:
        sim = SimSensor()
    else:
        tof = VL53L5CXDriver()
        imu = MPU6050()
        # Tare: set current heading as 0° forward reference.
        # User should be facing straight ahead at this moment.
        imu.zero_yaw()
        print("[Module1] IMU yaw tared — current heading is now 0° forward.")

    print(f"[Module1] Sensor fusion loop starting "
          f"(SIMULATION_MODE={SIMULATION_MODE}, {FUSION_LOOP_HZ} Hz)")

    start = time.monotonic()
    last_tof_frame = None

    try:
        while True:
            loop_start = time.monotonic()

            if SIMULATION_MODE:
                distance_mm, yaw, pitch = sim.get_frame()
            else:
                # IMU is sampled every loop (100 Hz); ToF only updates at
                # ~30 Hz, so we hold the last frame between ToF updates.
                yaw, pitch = imu.update()
                if tof.frame_ready():
                    last_tof_frame, _status = tof.get_frame()
                distance_mm = last_tof_frame
                if distance_mm is None:
                    time.sleep(period)
                    continue

            fused = ego_motion.compensate_frame(distance_mm, yaw, pitch)
            packet = classify(fused)
            packet["yaw_deg"] = yaw
            packet["pitch_deg"] = pitch
            packet["timestamp"] = time.time()

            try:
                out_queue.put_nowait(packet)
            except queue_module.Full:
                # Module 2 fell behind — skip this frame rather than
                # blocking the real-time fusion loop.
                pass

            if run_seconds is not None and (time.monotonic() - start) > run_seconds:
                break

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, period - elapsed))
    finally:
        if not SIMULATION_MODE:
            tof.close()
            imu.close()
        print("[Module1] Sensor fusion loop stopped.")


if __name__ == "__main__":
    # Standalone test: run the fusion loop for 5s, then inspect one packet.
    import queue as q

    test_queue = q.Queue(maxsize=QUEUE_MAXSIZE)
    run_sensor_module(test_queue, run_seconds=5)

    print(f"\n[Module1] Captured {test_queue.qsize()} packets. Sample:")
    if not test_queue.empty():
        sample = test_queue.get()
        for k, v in sample["bins"].items():
            print(f"  {k}: {v} mm")
