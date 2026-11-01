"""
Module 2 Vision & TTC Main Process Entrypoint
Lead Researcher: Dhivyashree G J. (24BCE1516)

Consumes Queue A (Sensor Fusion), applies Stage 1 Depth Gating,
runs YOLOv8n on dynamic cropped ROI, computes TTC, and pushes to Queue B.
"""

import time
import sys
from multiprocessing import Queue
from typing import Optional, Dict, Any

import config
from config import (
    VISION_MAX_FPS,
    DEPTH_INTERRUPT_THRESHOLD_M,
    POWER_MODE,
)
from .tof_gate import ToFInterruptGate
from .camera_driver import CameraDriver
from .yolo_engine import YOLOv8ROIEngine
from .ttc_engine import TTCEngine
from .class_map import get_severity_score



def run_vision_module(queue_in: Queue, queue_out: Queue, stop_event=None, queue_video_feed=None):
    """
    Main loop for Module 2.
    Pulls from Queue A (Sensor), applies ROI gate, infers YOLOv8, computes TTC, pushes to Queue B (Haptic).
    """
    print("[Module 2: Vision] Starting Process (HARDWARE MODE)")

    tof_gate = ToFInterruptGate(threshold_m=DEPTH_INTERRUPT_THRESHOLD_M)
    camera = CameraDriver()
    yolo_engine = YOLOv8ROIEngine()
    ttc_engine = TTCEngine()

    interval = 1.0 / VISION_MAX_FPS
    vision_frame_count = 0

    try:
        while stop_event is None or not stop_event.is_set():
            vision_frame_count += 1
            t_start = time.time()

            # 1. Fetch sensor packet from Queue A
            sensor_packet = None
            if queue_in is not None:
                try:
                    sensor_packet = queue_in.get(timeout=0.1)
                except Exception:
                    # Queue empty
                    continue

            if sensor_packet is None:
                continue

            depth_matrix = sensor_packet["depth_matrix"]
            critical_sector = sensor_packet["critical_sector"]
            min_dist = sensor_packet["min_distance_overall_m"]
            head_yaw = sensor_packet["head_yaw_deg"]
            ground_truth = sensor_packet.get("ground_truth", {})

            # 2. Stage 1: Depth Interrupt Gate (Novelty 03)
            is_triggered, roi = tof_gate.evaluate_gate(depth_matrix)

            # Update TTC engine with sector distances
            sector_distances = {
                sec_name: sec_data.min_distance_m
                for sec_name, sec_data in sensor_packet["sectors"].items()
            }
            ttc_results = ttc_engine.process_all_sectors(sector_distances, timestamp=t_start)
            critical_ttc = ttc_results.get(critical_sector)

            detections = []
            ai_gated = False
            primary_hazard_class = "clear"
            primary_confidence = 0.0

            # Low Power check: if LOW_POWER mode, keep camera & YOLO sleeping
            is_low_power = getattr(config, "POWER_MODE", "HIGH") == "LOW"

            if is_low_power:
                ai_gated = True
                # In low-power mode, classify directly by TTC & distance without camera
                if is_triggered:
                    approach_speed = abs(critical_ttc.approach_velocity_mps) if critical_ttc else 0.0
                    primary_hazard_class = "fast_moving_vehicle" if approach_speed > 1.2 else "obstacle"
                    primary_confidence = 0.85
                else:
                    primary_hazard_class = "clear"
            elif is_triggered and roi is not None:
                # High Power: Stage 2 Camera Wakeup & Dynamic ROI Inference
                ret, frame = camera.capture_frame()

                if ret:
                    detections = yolo_engine.infer_roi(frame, roi)

                    if detections:
                        # Find highest severity detection
                        best_det = max(
                            detections,
                            key=lambda d: get_severity_score(d.class_name, roi.min_distance_m)
                        )
                        primary_hazard_class = best_det.class_name
                        primary_confidence = best_det.confidence
                    else:
                        primary_hazard_class = "generic_obstacle"
                        primary_confidence = 0.5

                    if vision_frame_count % 3 == 0:
                        print(f"\033[92m[CAMERA WAKEUP]\033[0m Stage 2 Active | Obstacle at {min_dist*100:.1f}cm | YOLO: {primary_hazard_class} ({primary_confidence:.2f})")

                    # --- Annotate frame and push to caretaker video queue ---
                    if queue_video_feed is not None:
                        import cv2 as _cv2
                        annotated = frame.copy()
                        
                        # Check if camera lens is covered or facing down on desk (mean brightness < 8)
                        if annotated.mean() < 8.0:
                            _cv2.rectangle(annotated, (20, 200), (620, 280), (0, 0, 150), -1)
                            _cv2.putText(annotated, "LENS COVERED / FACING DESK",
                                         (40, 235), _cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
                            _cv2.putText(annotated, "Point camera up at room to see live video",
                                         (60, 265), _cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1)

                        # Yellow ROI bounding box
                        _cv2.rectangle(annotated, (roi.xmin, roi.ymin), (roi.xmax, roi.ymax), (0, 255, 255), 2)
                        _cv2.putText(annotated, f"ROI ({roi.min_distance_m*100:.0f}cm)",
                                     (roi.xmin + 5, roi.ymin + 18),
                                     _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

                        # Green detection boxes + labels
                        for det in detections:
                            x1, y1, x2, y2 = det.bbox_global
                            _cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            _cv2.putText(annotated, f"{det.class_name} {det.confidence:.2f}",
                                         (x1, max(y1 - 8, 12)),
                                         _cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

                        # Red Stage 2 banner placed prominently (bottom bar) so HTML tags don't cover it
                        _h, _w = annotated.shape[:2]
                        _cv2.rectangle(annotated, (0, _h - 36), (_w, _h), (0, 0, 200), -1)
                        _cv2.putText(annotated,
                                     f"STAGE 2: CAM AWAKE | Dist: {min_dist*100:.0f}cm | {primary_hazard_class.upper()} ({primary_confidence:.2f})",
                                     (10, _h - 12), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                        _ret_enc, _jpeg = _cv2.imencode('.jpg', annotated, [_cv2.IMWRITE_JPEG_QUALITY, 80])
                        if _ret_enc:
                            if queue_video_feed.full():
                                try: queue_video_feed.get_nowait()
                                except Exception: pass
                            try: queue_video_feed.put_nowait(_jpeg.tobytes())
                            except Exception: pass
                else:
                    # ToF still protects the user while the dashboard records
                    # the real camera fault. No synthetic object is invented.
                    primary_hazard_class = "camera_unavailable"
                    primary_confidence = 0.0
                    # Push a camera-fault status frame
                    if queue_video_feed is not None:
                        import cv2 as _cv2, numpy as _np
                        _sf = _np.zeros((480, 640, 3), dtype=_np.uint8)
                        _cv2.putText(_sf, "CAMERA FAULT - ToF protecting user",
                                     (60, 240), _cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 80, 200), 2)
                        _ret_enc, _jpeg = _cv2.imencode('.jpg', _sf, [_cv2.IMWRITE_JPEG_QUALITY, 60])
                        if _ret_enc:
                            if queue_video_feed.full():
                                try: queue_video_feed.get_nowait()
                                except Exception: pass
                            try: queue_video_feed.put_nowait(_jpeg.tobytes())
                            except Exception: pass
            else:
                # Gated: Camera & AI sleep, saving >70% compute
                ai_gated = True
                primary_hazard_class = "clear"
                # Push a Stage 1 status placeholder so dashboard feed stays alive
                if queue_video_feed is not None:
                    import cv2 as _cv2, numpy as _np
                    _sf = _np.zeros((480, 640, 3), dtype=_np.uint8)
                    _cv2.rectangle(_sf, (0, 0), (640, 30), (0, 60, 0), -1)
                    _cv2.putText(_sf, "STAGE 1: CAM ASLEEP  |  Monitoring (ToF only)",
                                 (30, 22), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 220, 80), 2)
                    _cv2.putText(_sf, f"Closest: {min_dist*100:.1f} cm  |  threshold 100 cm",
                                 (150, 260), _cv2.FONT_HERSHEY_SIMPLEX, 0.7, (120, 120, 120), 1)
                    _cv2.putText(_sf, "Move hand within 1.0 m to wake camera",
                                 (130, 300), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 80, 80), 1)
                    _ret_enc, _jpeg = _cv2.imencode('.jpg', _sf, [_cv2.IMWRITE_JPEG_QUALITY, 60])
                    if _ret_enc:
                        if queue_video_feed.full():
                            try: queue_video_feed.get_nowait()
                            except Exception: pass
                        try: queue_video_feed.put_nowait(_jpeg.tobytes())
                        except Exception: pass

            # 3. Construct Packet for Queue B (Vision -> Haptics)
            haptic_packet = {
                "timestamp": t_start,
                "frame_id": sensor_packet.get("frame_id", 0),
                "head_yaw_deg": head_yaw,
                "critical_sector": critical_sector,
                "min_distance_m": min_dist,
                "sectors": {
                    sec_name: sec_data.min_distance_m
                    for sec_name, sec_data in sensor_packet.get("sectors", {}).items()
                },
                "is_depth_interrupt": is_triggered,
                "ai_gated": ai_gated,
                "roi_area_ratio": roi.area_ratio if roi else 0.0,
                "primary_class": primary_hazard_class,
                "confidence": primary_confidence,
                "yolo_ready": yolo_engine.is_loaded,
                "yolo_error": yolo_engine.last_error,
                "camera_ready": camera.is_opened,
                "data_source": sensor_packet.get("data_source", "unknown"),
                "valid_tof_zones": sensor_packet.get("valid_tof_zones", 0),
                "ttc_seconds": critical_ttc.ttc_seconds if critical_ttc else 99.0,
                "approach_velocity_mps": critical_ttc.approach_velocity_mps if critical_ttc else 0.0,
                "urgency_level": critical_ttc.urgency_level if critical_ttc else "SAFE",
                "is_head_hazard": sensor_packet["sectors"][critical_sector].is_head_hazard if critical_sector in sensor_packet["sectors"] else False,
            }

            # 4. Push to Queue B
            if queue_out is not None:
                if queue_out.full():
                    try:
                        queue_out.get_nowait()
                    except Exception:
                        pass
                try:
                    queue_out.put_nowait(haptic_packet)
                except Exception:
                    pass

            elapsed = time.time() - t_start
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("[Module 2: Vision] Stopping on user interrupt...")
    finally:
        camera.release()
        print("[Module 2: Vision] Exited cleanly.")


if __name__ == "__main__":
    print("=== Module 2 (Vision Gate, YOLO ROI & TTC) — run via main.py --real ===")
