"""
Process Entry Point: Dual-Stage AI Vision & TTC Pipeline (Module 2)
Author: Dhivyashree G J. (24BCE1516)

Consumes: Queue A (Sensor Fusion & Ego-Motion from Andrea A.)
Executes: Stage 1 ToF Depth Gating -> Dynamic ROI Cropping -> YOLOv8n AI -> Rolling TTC
Produces: Queue B (Classified Hazards, TTC & Haptic Directives to Tejaswi E.)
"""

import multiprocessing
import queue
import time
from typing import Any, Dict, Optional

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config
from module2_vision.tof_gate import ToFDepthGate, GatingDecision
from module2_vision.camera_driver import CameraDriver
from module2_vision.yolo_engine import YOLOEngine
from module2_vision.ttc_engine import TTCEngine
from module2_vision.class_map import ClassMap


def run_vision_module(
    queue_sensor_to_vision: multiprocessing.Queue,
    queue_vision_to_haptic: multiprocessing.Queue,
    stop_event: Optional[multiprocessing.Event] = None,
    max_iterations: Optional[int] = None,
):
    """
    Continuous worker loop for Module 2: AI Vision & Time-to-Collision Engine.
    
    Args:
        queue_sensor_to_vision: Queue A (incoming 64-zone depth arrays & IMU yaw)
        queue_vision_to_haptic: Queue B (outgoing hazard alerts with TTC & motor commands)
        stop_event: Optional multiprocessing Event to request graceful termination
        max_iterations: Optional iteration limit for benchmarking and unit testing
    """
    print("[Module 2: Vision & TTC] Initializing perception pipeline...")

    # Initialize sub-components
    tof_gate = ToFDepthGate()
    camera = CameraDriver()
    yolo = YOLOEngine()
    ttc = TTCEngine()

    print("[Module 2: Vision & TTC] Ready. Listening on Queue A...")

    iteration = 0
    idle_heartbeat_counter = 0

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                print("[Module 2: Vision & TTC] Stop event received. Shutting down.")
                break

            if max_iterations is not None and iteration >= max_iterations:
                print(f"[Module 2: Vision & TTC] Reached max iterations ({max_iterations}). Exiting loop.")
                break

            try:
                # Non-blocking fetch with 100ms timeout
                sensor_packet = queue_sensor_to_vision.get(timeout=0.1)
            except queue.Empty:
                continue

            iteration += 1
            t_start = time.time()

            # Extract IMU head orientation angles from Andrea's Module 1 (Queue A)
            head_yaw_deg = 0.0
            head_pitch_deg = 0.0
            if isinstance(sensor_packet, dict):
                head_yaw_deg = float(sensor_packet.get("yaw_deg", sensor_packet.get("head_yaw_deg", 0.0)))
                head_pitch_deg = float(sensor_packet.get("pitch_deg", sensor_packet.get("head_pitch_deg", 0.0)))

            # -------------------------------------------------------------
            # Step 1: Stage 1 Spatial Interrupt Depth Gating (Novelty 03)
            # -------------------------------------------------------------
            gating: GatingDecision = tof_gate.evaluate(sensor_packet)

            if not gating.is_triggered:
                # DEPTH > 2.0m: Low-power idle state. No optical capture or AI inference.
                idle_heartbeat_counter += 1
                if idle_heartbeat_counter >= 15:  # Periodic heartbeat every ~0.5s
                    idle_heartbeat_counter = 0
                    idle_packet = {
                        "timestamp": t_start,
                        "triggered": False,
                        "head_yaw_deg": round(head_yaw_deg, 1),
                        "head_pitch_deg": round(head_pitch_deg, 1),
                        "min_distance_m": round(gating.min_distance_m, 2),
                        "azimuth": gating.primary_azimuth,
                        "elevation": gating.primary_elevation,
                        "roi_compute_savings_pct": 100.0,
                        "urgency": "SAFE",
                        "latency_ms": round((time.time() - t_start) * 1000, 2),
                    }
                    try:
                        queue_vision_to_haptic.put_nowait(idle_packet)
                    except queue.Full:
                        pass
                continue

            # -------------------------------------------------------------
            # Step 2: Spatial Interrupt Activated (< 2.0m)
            # Dynamic ROI Frame Capture and Selective Cropping
            # -------------------------------------------------------------
            idle_heartbeat_counter = 0
            ret, full_frame = camera.read_frame()
            if not ret or full_frame is None:
                continue

            # Crop sub-image strictly to ToF flagged bounding box
            cropped_roi = camera.crop_roi(full_frame, gating.roi_box)

            # -------------------------------------------------------------
            # Step 3: YOLOv8n Inference on Cropped ROI
            # -------------------------------------------------------------
            detections = yolo.infer_roi(
                cropped_roi=cropped_roi,
                roi_box=gating.roi_box,
                elevation_hint=gating.primary_elevation,
            )

            # -------------------------------------------------------------
            # Step 4: Time-to-Collision (TTC) & Approach Rate Calculation
            # -------------------------------------------------------------
            packet_time = sensor_packet.get("timestamp", t_start) if isinstance(sensor_packet, dict) else t_start
            ttc_result = ttc.update(
                distance_m=gating.min_distance_m,
                sector=gating.primary_azimuth,
                timestamp=packet_time,
            )

            # -------------------------------------------------------------
            # Step 5: Hazard Profile & Haptic Waveform Synthesis
            # -------------------------------------------------------------
            if detections:
                top_det = detections[0]
                primary_class = top_det.class_name
                hazard_info = top_det.hazard_info
            else:
                primary_class = "obstacle"
                hazard_info = ClassMap.resolve_hazard(
                    coco_class_id=None,
                    elevation_sector=gating.primary_elevation,
                )

            waveform_id = ClassMap.select_waveform_by_urgency(
                base_hazard=hazard_info,
                urgency=ttc_result.urgency_level,
            )

            # Compute total processing latency
            t_end = time.time()
            latency_ms = (t_end - t_start) * 1000.0

            # -------------------------------------------------------------
            # Step 6: Package & Forward to Queue B (for Tejaswi E.)
            # -------------------------------------------------------------
            # Spatial mapping for Module 3 compatibility
            az_m3 = "C"
            if gating.primary_azimuth == "Left":
                az_m3 = "L"
            elif gating.primary_azimuth == "Right":
                az_m3 = "R"

            el_m3 = "head" if gating.primary_elevation == "HeadHazard" else "ground"

            # Class mapping for Module 3 (must be: 'person', 'vehicle', 'overhead', 'wall')
            p_lower = primary_class.lower()
            if any(v in p_lower for v in ["vehicle", "car", "bus", "truck", "motorcycle", "bicycle"]):
                class_m3 = "vehicle"
            elif "overhead" in p_lower or (gating.primary_elevation == "HeadHazard" and p_lower in ["obstacle", "branch"]):
                class_m3 = "overhead"
            elif "wall" in p_lower or p_lower == "obstacle":
                class_m3 = "wall"
            else:
                class_m3 = "person"

            effective_ttc = ttc_result.ttc_seconds if ttc_result.is_approaching else None

            hazard_packet: Dict[str, Any] = {
                # Module 3 standard keys
                "ts": t_end,
                "azimuth": az_m3,
                "distance": round(gating.min_distance_m, 2),
                "ttc": effective_ttc,
                "class": class_m3,
                "elevation": el_m3,

                # Rich Module 2 telemetry and paper benchmark fields
                "timestamp": t_end,
                "triggered": True,
                "head_yaw_deg": round(head_yaw_deg, 1),
                "head_pitch_deg": round(head_pitch_deg, 1),
                "azimuth_name": gating.primary_azimuth,
                "elevation_name": gating.primary_elevation,
                "min_distance_m": round(gating.min_distance_m, 2),
                "nearest_zone": gating.nearest_zone,
                "roi_box": gating.roi_box,
                "detected_classes": [d.class_name for d in detections],
                "primary_class": primary_class,
                "hazard_category": hazard_info.category,
                "hazard_severity": hazard_info.severity_score,
                "approach_velocity_mps": ttc_result.approach_velocity_mps,
                "ttc_seconds": ttc_result.ttc_seconds,
                "urgency": ttc_result.urgency_level,
                "suggested_waveform_id": waveform_id,
                "roi_compute_savings_pct": round(gating.compute_savings_pct, 1),
                "vision_latency_ms": round(latency_ms, 2),
            }

            try:
                queue_vision_to_haptic.put(hazard_packet, timeout=0.05)
            except queue.Full:
                pass

    finally:
        camera.release()
        print("[Module 2: Vision & TTC] Camera released and module shutdown complete.")


if __name__ == "__main__":
    # Standalone test runner with dummy queues
    print("[Standalone Test] Launching Module 2 test runner...")
    q_in = multiprocessing.Queue()
    q_out = multiprocessing.Queue()

    # Push a simulated obstacle within 1.2m (Center sector)
    mock_sensor_packet = {
        "timestamp": time.time(),
        "depth_matrix": [[3.5] * 8 for _ in range(8)],
        "head_yaw_deg": 0.0,
        "head_pitch_deg": 0.0,
    }
    # Place obstacle at (row 2, col 4) -> Head hazard, Center
    mock_sensor_packet["depth_matrix"][2][4] = 1.15
    q_in.put(mock_sensor_packet)

    # Run for 2 iterations
    run_vision_module(q_in, q_out, max_iterations=1)

    if not q_out.empty():
        output = q_out.get()
        print("[Standalone Test] Successfully produced Queue B output packet:")
        for k, v in output.items():
            print(f"  {k}: {v}")
    else:
        print("[Standalone Test] Queue B was empty.")
