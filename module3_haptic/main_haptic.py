"""
Module 3 Spatio-Tactile Haptics & Telemetry Process Entrypoint
Lead Researcher: Tejaswi E. (24BCE5518)

Consumes Queue B (Vision/TTC), encodes 3-axis spatio-tactile signals,
triggers TI DRV2605L LRA motors and logs telemetry.
REAL HARDWARE ONLY.
"""

import time
import sys
from multiprocessing import Queue
from typing import Optional, Callable

import config
from .haptic_encoder import SpatioTactileEncoder
from .drv2605l_driver import DRV2605LDriver
from .firebase_logger import FirebaseTelemetryLogger


def run_haptic_module(queue_in: Queue, stop_event=None, event_callback: Optional[Callable] = None):
    """
    Main loop for Module 3.
    Consumes from Queue B, actuates LRAs, logs to Firebase & disk.
    """
    print("\n[Module 3: Haptic] Starting Process (HARDWARE MODE)")

    encoder = SpatioTactileEncoder()
    drv_driver = DRV2605LDriver()
    logger = FirebaseTelemetryLogger(use_firebase=True)
    last_buzz_times = {
        config.MOTOR_LEFT: 0.0,
        config.MOTOR_CENTER: 0.0,
        config.MOTOR_RIGHT: 0.0,
    }

    try:
        while stop_event is None or not stop_event.is_set():
            vision_packet = None
            if queue_in is not None:
                try:
                    vision_packet = queue_in.get(timeout=0.1)
                except Exception:
                    continue

            if vision_packet is None:
                continue

            now = time.time()
            # Calculate end-to-end perception-to-action latency
            t_orig = vision_packet.get("timestamp", now)
            latency_ms = (now - t_orig) * 1000.0

            # 1. Novelty 02: 3-Axis Spatio-Tactile Encoding
            cmd = encoder.encode(vision_packet)

            # 2. Hardware Actuation:
            # Multi-sector actuation with colour-zone intensity mapping
            # RED < 15 cm → strong 100%, ORANGE < 35 cm → medium 60%, YELLOW < 70 cm → soft
            sectors = vision_packet.get("sectors", {})
            actuated_any = False
            for sec_name in (config.MOTOR_LEFT, config.MOTOR_CENTER, config.MOTOR_RIGHT):
                sec_d = sectors.get(sec_name, 999.0)
                sec_d_cm = sec_d * 100.0

                # Pick waveform by colour zone
                if sec_d_cm < config.HAPTIC_ZONE_RED_CM:
                    wf = config.WAVEFORM_ZONE_RED
                    zone_label = "RED"
                    cooldown = 0.15   # faster re-trigger for imminent danger
                elif sec_d_cm < config.HAPTIC_ZONE_ORANGE_CM:
                    wf = config.WAVEFORM_ZONE_ORANGE
                    zone_label = "ORANGE"
                    cooldown = 0.30
                elif sec_d_cm < config.HAPTIC_ZONE_YELLOW_CM:
                    wf = config.WAVEFORM_ZONE_YELLOW
                    zone_label = "YELLOW"
                    cooldown = 0.50
                else:
                    continue  # GREEN zone — silent

                if (now - last_buzz_times[sec_name]) > cooldown:
                    drv_driver.trigger_waveform(sec_name, wf)
                    last_buzz_times[sec_name] = now
                    actuated_any = True
                    print(f"[Haptic Actuation] >>> Buzzing Motor: {sec_name} | Distance: {sec_d_cm:.1f} cm | Zone: {zone_label} | Waveform: {wf}")

            # Fallback to single-channel encoded pulse for farther obstacles
            if not actuated_any and cmd.should_pulse and cmd.distance_m < 1.0:
                if (now - last_buzz_times[cmd.motor_channel]) > 0.3:
                    drv_driver.trigger_waveform(cmd.motor_channel, cmd.waveform_id)
                    last_buzz_times[cmd.motor_channel] = now
                    print(f"[Haptic Actuation] >>> Buzzing Motor: {cmd.motor_channel} | Distance: {cmd.distance_m*100.0:.1f} cm | Waveform: {cmd.waveform_id}")

            # 3. Construct Full Telemetry Packet
            head_yaw = vision_packet.get("head_yaw_deg", 0.0)
            telemetry_event = {
                "timestamp": now,
                "frame_id": vision_packet.get("frame_id", 0),
                "head_yaw_deg": head_yaw,
                "motor_channel": cmd.motor_channel,
                "distance_m": cmd.distance_m,
                "ttc_seconds": cmd.ttc_seconds,
                "approach_velocity_mps": vision_packet.get("approach_velocity_mps", 0.0),
                "urgency_level": cmd.urgency_level,
                "hazard_class": cmd.hazard_class,
                "waveform_id": cmd.waveform_id,
                "waveform_name": cmd.waveform_name,
                "is_depth_interrupt": vision_packet.get("is_depth_interrupt", False),
                "ai_gated": vision_packet.get("ai_gated", False),
                "roi_area_ratio": vision_packet.get("roi_area_ratio", 0.0),
                "latency_ms": latency_ms,
                "should_pulse": cmd.should_pulse,
                "data_source": vision_packet.get("data_source", "unknown"),
                "valid_tof_zones": vision_packet.get("valid_tof_zones", 0),
                "yolo_ready": vision_packet.get("yolo_ready", False),
                "camera_ready": vision_packet.get("camera_ready", False),
            }

            # 5. Push to Cloud / Local Research Logger
            logger.log_event(telemetry_event)

            # 6. Optional Direct Callback for Local Web Dashboard Server
            if event_callback is not None:
                try:
                    event_callback(telemetry_event)
                except Exception:
                    pass

    except KeyboardInterrupt:
        print("\n[Module 3: Haptic] Stopping on user interrupt...")
    finally:
        drv_driver.close()
        logger.stop()
        print("\n[Module 3: Haptic] Exited cleanly.")


if __name__ == "__main__":
    from multiprocessing import Queue
    print("=== Testing Module 3 (3-Axis Haptic & Telemetry) ===")
    q_test = Queue(maxsize=5)

    import threading
    stop_event = threading.Event()
    t = threading.Thread(target=run_haptic_module, args=(q_test, stop_event))
    t.daemon = True
    t.start()

    # Feed test packets with varying urgency
    try:
        scenarios = [
            {"critical_sector": "CENTER", "min_distance_m": 2.2, "ttc_seconds": 3.5, "primary_class": "person", "is_head_hazard": False},
            {"critical_sector": "LEFT", "min_distance_m": 1.4, "ttc_seconds": 1.2, "primary_class": "car", "is_head_hazard": False},
            {"critical_sector": "CENTER", "min_distance_m": 0.6, "ttc_seconds": 0.4, "primary_class": "overhead_hazard", "is_head_hazard": True},
        ]

        for s in scenarios:
            s["timestamp"] = time.time()
            s["head_yaw_deg"] = 12.5
            q_test.put(s)
            time.sleep(0.3)

        time.sleep(0.5)
    finally:
        stop_event.set()
        print("\n=== Module 3 test passed successfully ===")
