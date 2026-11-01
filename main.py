"""
Master Multiprocess Launcher for Context-Aware Smart Glasses System
Integrates Module 1 (Sensor), Module 2 (Vision), and Module 3 (Haptics)
via bounded inter-process queues.
"""

import sys
import os
import time
import signal
import argparse
from multiprocessing import Process, Queue, Event

import config
from module1_sensor.main_sensor import run_sensor_module
from module2_vision.main_vision import run_vision_module
from module3_haptic.main_haptic import run_haptic_module


def main():
    parser = argparse.ArgumentParser(description="Context-Aware Smart Glasses Pipeline")
    parser.add_argument("--real", action="store_true", help="(Default) Physical hardware I2C mode on Raspberry Pi 4")
    parser.add_argument("--low-power", action="store_true", help="Run low-power mode (ToF depth + haptics only, camera & AI sleep)")
    parser.add_argument("--high-power", action="store_true", help="Run high-power mode (ToF + Camera + YOLOv8n vehicle classification)")
    parser.add_argument("--dashboard", action="store_true", help="Launch local dashboard web server alongside pipeline")
    parser.add_argument("--duration", type=float, default=None, help="Run for N seconds then shut down cleanly (useful for tests)")
    args = parser.parse_args()

    if args.low_power:
        config.POWER_MODE = "LOW"
        os.environ["POWER_MODE"] = "LOW"
    elif args.high_power:
        config.POWER_MODE = "HIGH"
        os.environ["POWER_MODE"] = "HIGH"

    print("=" * 78)
    print(" CONTEXT-AWARE SMART GLASSES - EDGE EMBEDDED SYSTEM")
    print(f" Mode:       HARDWARE (Raspberry Pi 4)")
    print(f" Power Mode: {config.POWER_MODE} ({'Ultra-Low 0.5W ToF-Only' if config.POWER_MODE == 'LOW' else 'Full ToF + Camera ROI + YOLOv8n'})")
    print(" Target:     IEEE Sensors / MDPI Sensors Journal")
    print("=" * 78)

    # Inter-process queues with bounded buffers to prevent memory bloat and guarantee real-time latency
    queue_sensor_to_vision = Queue(maxsize=10)
    queue_vision_to_haptic = Queue(maxsize=10)
    queue_video_feed = Queue(maxsize=2)  # Low buffer to keep video real-time and prevent memory issues
    queue_depth_grid = Queue(maxsize=2)  # Live 8x8 depth matrix for dashboard grid widget

    # Inter-process cancellation event
    stop_event = Event()

    processes = []

    # Process 1: Andrea A. (Sensor Fusion & Ego-Motion Engine)
    p1 = Process(
        target=run_sensor_module,
        args=(queue_sensor_to_vision, stop_event, queue_video_feed, queue_depth_grid),
        name="Module1_SensorProcess",
        daemon=True,
    )
    processes.append(p1)

    # Process 2: Dhivyashree G J. (Dual-Stage AI Vision & TTC Engine)
    p2 = Process(
        target=run_vision_module,
        args=(queue_sensor_to_vision, queue_vision_to_haptic, stop_event, queue_video_feed),
        name="Module2_VisionProcess",
        daemon=True,
    )
    processes.append(p2)

    # Process 3: Tejaswi E. (Spatio-Tactile Haptics & Cloud Telemetry)
    p3 = Process(
        target=run_haptic_module,
        args=(queue_vision_to_haptic, stop_event),
        name="Module3_HapticProcess",
        daemon=True,
    )
    processes.append(p3)

    # Optional Dashboard Process
    p_dash = None
    if args.dashboard:
        from dashboard.server import run_dashboard_server
        p_dash = Process(
            target=run_dashboard_server,
            args=(stop_event, queue_video_feed, queue_depth_grid),
            name="DashboardServerProcess",
            daemon=True,
        )
        processes.append(p_dash)

    main_pid = os.getpid()

    def signal_handler(sig, frame):
        if os.getpid() != main_pid:
            return
        print("\n\n[SYSTEM] Received shutdown signal. Gracefully stopping all processes...")
        stop_event.set()
        time.sleep(0.5)
        for p in processes:
            try:
                if p.is_alive():
                    p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start all concurrent processes
    for p in processes:
        p.start()
        print(f"[SYSTEM] Spawned {p.name} (PID: {p.pid})")
        time.sleep(0.5)

    print("=" * 78)
    print(" ✅ ALL MODULES ACTIVE & RUNNING IN REAL TIME")
    print(f" 🌐 WEB DASHBOARD URL: http://192.168.137.172:{config.DASHBOARD_PORT}")
    print(" 🔑 LOGIN:             researcher  /  Glasses2026!")
    print(" 📡 Streaming live sensor, camera ROI, and haptic actuation.")
    print(" Press Ctrl+C to terminate.")
    print("=" * 78)
    start_time = time.time()

    try:
        while True:
            # Check duration limit if specified
            if args.duration is not None and (time.time() - start_time) >= args.duration:
                print(f"\n[SYSTEM] Target test duration ({args.duration}s) reached. Shutting down...")
                signal_handler(None, None)

            # Monitor process health
            for p in processes:
                if not p.is_alive() and not stop_event.is_set():
                    print(f"[SYSTEM WARNING] Process {p.name} exited unexpectedly.")
            time.sleep(0.5)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
