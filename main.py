"""
main.py
Root entry point for the Context-Aware Smart Glasses pipeline.
Spawns all 3 modules as separate processes connected by inter-process queues.

Usage:
    python main.py

Module 1 (Andrea) and Module 2 (Dhivyashree) are fully implemented and integrated.
Module 3 (Tejaswi) placeholder will be wired in once her code is ready.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multiprocessing import Process, Queue
from config import SIMULATION_MODE, QUEUE_MAXSIZE
from module1_sensor.main_sensor import run_sensor_module
from module2_vision.main_vision import run_vision_module


def _placeholder_haptic(in_queue):
    """Placeholder for Module 3 (Tejaswi): drains Queue B and prints
    a summary of each packet until her code is ready."""
    print("[Module3] PLACEHOLDER -- printing Queue B packets")
    while True:
        try:
            packet = in_queue.get(timeout=2.0)
            if packet.get("triggered", False):
                cls = packet.get("primary_class", "obstacle")
                dist = packet.get("min_distance_m", 0.0)
                az = packet.get("azimuth", "Center")
                ttc = packet.get("ttc_seconds", 99.9)
                urgency = packet.get("urgency", "SAFE")
                wf = packet.get("suggested_waveform_id", 1)
                savings = packet.get("roi_compute_savings_pct", 0.0)
                yaw = packet.get("head_yaw_deg", 0.0)
                print(f"  [Module3] HAZARD: {cls} @ {dist:.2f}m ({az}, Yaw: {yaw:+.1f}°) | TTC: {ttc:.2f}s [{urgency}] | Waveform: #{wf} | Compute Saved: {savings:.1f}%")
        except Exception:
            break
    print("[Module3] PLACEHOLDER stopped.")


if __name__ == '__main__':
    print(f"[SYSTEM] Context-Aware Smart Glasses Pipeline")
    print(f"[SYSTEM] SIMULATION_MODE = {SIMULATION_MODE}")
    print(f"[SYSTEM] Starting 3 processes (Sensor -> Vision -> Haptic)...\n")

    queue_a = Queue(maxsize=QUEUE_MAXSIZE)  # Sensor → Vision
    queue_b = Queue(maxsize=QUEUE_MAXSIZE)  # Vision → Haptic

    p1 = Process(target=run_sensor_module,
                 args=(queue_a,),
                 kwargs={"run_seconds": 5.0},
                 name="SensorProcess")
    p2 = Process(target=run_vision_module,
                 args=(queue_a, queue_b),
                 kwargs={"max_iterations": 200},
                 name="VisionProcess")
    p3 = Process(target=_placeholder_haptic,
                 args=(queue_b,),
                 name="HapticProcess")

    p1.start()
    p2.start()
    p3.start()

    p1.join()
    p2.join(timeout=3)
    p3.join(timeout=3)

    # Terminate placeholders if they're still blocking on empty queues
    for p in [p2, p3]:
        if p.is_alive():
            p.terminate()

    print("\n[SYSTEM] Pipeline stopped.")
