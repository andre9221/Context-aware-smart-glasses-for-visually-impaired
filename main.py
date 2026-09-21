"""
main.py
Root entry point for the Context-Aware Smart Glasses pipeline.
Spawns all 3 modules as separate processes connected by inter-process queues.

Usage:
    python main.py

Currently only Module 1 (Andrea) is implemented.
Module 2 (Dhivyashree) and Module 3 (Tejaswi) are placeholders that will
be wired in once their code is ready.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multiprocessing import Process, Queue
from config import SIMULATION_MODE, QUEUE_MAXSIZE
from module1_sensor.main_sensor import run_sensor_module


def _placeholder_vision(in_queue, out_queue):
    """Placeholder for Module 2 (Dhivyashree): drains Queue A and
    forwards raw packets to Queue B until her code is ready."""
    import queue as q
    print("[Module2] PLACEHOLDER -- forwarding Queue A -> Queue B")
    while True:
        try:
            packet = in_queue.get(timeout=2.0)
            try:
                out_queue.put_nowait(packet)
            except q.Full:
                pass
        except Exception:
            break
    print("[Module2] PLACEHOLDER stopped.")


def _placeholder_haptic(in_queue):
    """Placeholder for Module 3 (Tejaswi): drains Queue B and prints
    a summary of each packet until her code is ready."""
    print("[Module3] PLACEHOLDER -- printing Queue B packets")
    while True:
        try:
            packet = in_queue.get(timeout=2.0)
            bins = packet.get("bins", {})
            nearest = min((v for v in bins.values() if v is not None), default=None)
            if nearest and nearest < 3999:
                sector = [k for k, v in bins.items() if v == nearest][0]
                print(f"  [Module3] Nearest obstacle: {nearest:.0f} mm @ {sector}")
        except Exception:
            break
    print("[Module3] PLACEHOLDER stopped.")


if __name__ == '__main__':
    print(f"[SYSTEM] Context-Aware Smart Glasses Pipeline")
    print(f"[SYSTEM] SIMULATION_MODE = {SIMULATION_MODE}")
    print(f"[SYSTEM] Starting 3 processes...\n")

    queue_a = Queue(maxsize=QUEUE_MAXSIZE)  # Sensor → Vision
    queue_b = Queue(maxsize=QUEUE_MAXSIZE)  # Vision → Haptic

    p1 = Process(target=run_sensor_module,
                 args=(queue_a,),
                 kwargs={"run_seconds": 5.0},
                 name="SensorProcess")
    p2 = Process(target=_placeholder_vision,
                 args=(queue_a, queue_b),
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
