"""
Interactive Vision Simulation HUD Testbed
Author: Dhivyashree G J. (24BCE1516)

Visualizes Dhivyashree's dual-stage perception pipeline in real time:
- 8x8 ToF LiDAR Depth Grid Overlay
- Dynamic Cropped ROI Bounding Box
- Real-time YOLOv8n detections
- HUD Telemetry Panel: Gating Status, Approach Speed, TTC, Urgency & Compute Savings %
"""

import time
from typing import Optional, Tuple
import numpy as np

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config
from module2_vision.tof_gate import ToFDepthGate, GatingDecision
from module2_vision.camera_driver import CameraDriver, OPENCV_AVAILABLE
from module2_vision.yolo_engine import YOLOEngine
from module2_vision.ttc_engine import TTCEngine
from module2_vision.class_map import ClassMap

if OPENCV_AVAILABLE:
    import cv2


class VisionSimulatorHUD:
    """Renders real-time augmented HUD overlays for testing and demonstrations."""

    def __init__(
        self,
        width: int = config.CAMERA_WIDTH,
        height: int = config.CAMERA_HEIGHT,
    ):
        self.width = width
        self.height = height
        self.gate = ToFDepthGate(frame_width=width, frame_height=height)
        self.camera = CameraDriver(width=width, height=height)
        self.yolo = YOLOEngine()
        self.ttc = TTCEngine()

    def generate_simulated_depth(
        self,
        step: int,
        scenario: str = "approaching_person",
    ) -> np.ndarray:
        """
        Generates realistic 8x8 depth matrix simulating different real-world scenarios:
        - "approaching_person": Pedestrian walking directly toward user (Center)
        - "side_vehicle": Fast vehicle on the Left closing in
        - "clear_path": All zones > 3.0m (IDLE state)
        """
        depth = np.full((config.TOF_ROWS, config.TOF_COLS), 3.5, dtype=np.float32)

        if scenario == "clear_path":
            return depth

        if scenario == "approaching_person":
            # Obstacle moves from 2.8m down to 0.5m over 60 steps
            progress = (step % 60) / 60.0
            dist = 2.8 - progress * 2.3  # 2.8m -> 0.5m
            # Pedestrian spans rows 1..5, cols 3..4 (Center, head + torso)
            for r in range(1, 6):
                for c in range(3, 5):
                    depth[r, c] = dist + np.random.uniform(-0.05, 0.05)

        elif scenario == "side_vehicle":
            # Vehicle approaching rapidly from Left (cols 0..2, rows 3..7)
            progress = (step % 40) / 40.0
            dist = 3.2 - progress * 2.7  # 3.2m -> 0.5m
            for r in range(3, 8):
                for c in range(0, 3):
                    depth[r, c] = dist + np.random.uniform(-0.08, 0.08)

        return depth

    def render_frame(
        self,
        frame: np.ndarray,
        gating: GatingDecision,
        detections: list,
        ttc_res,
        waveform_id: int,
    ) -> np.ndarray:
        """Draws the complete smart glasses augmented vision interface."""
        canvas = frame.copy()

        if not OPENCV_AVAILABLE:
            return canvas

        h, w = canvas.shape[:2]

        # -------------------------------------------------------------
        # 1. Draw 8x8 ToF Spatial Grid Overlay
        # -------------------------------------------------------------
        cell_w = w / float(config.TOF_COLS)
        cell_h = h / float(config.TOF_ROWS)

        # Draw subtle grid lines
        for c in range(config.TOF_COLS + 1):
            x = int(c * cell_w)
            cv2.line(canvas, (x, 0), (x, h), (50, 50, 50), 1)
        for r in range(config.TOF_ROWS + 1):
            y = int(r * cell_h)
            cv2.line(canvas, (0, y), (w, y), (50, 50, 50), 1)

        # Highlight active ToF zones
        for r, c in gating.active_zones:
            x1 = int(c * cell_w)
            y1 = int(r * cell_h)
            x2 = int((c + 1) * cell_w)
            y2 = int((r + 1) * cell_h)
            # Amber semi-transparent fill for active depth cells
            overlay = canvas.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 140, 255), -1)
            cv2.addWeighted(overlay, 0.25, canvas, 0.75, 0, canvas)

        # -------------------------------------------------------------
        # 2. Draw Dynamic Cropped ROI Box (Novelty 03)
        # -------------------------------------------------------------
        if gating.is_triggered:
            rx1, ry1, rx2, ry2 = gating.roi_box
            # Draw glowing Cyan ROI border
            cv2.rectangle(canvas, (rx1, ry1), (rx2, ry2), (255, 240, 0), 2)
            cv2.putText(
                canvas,
                f"DYNAMIC ROI [Compute Saved: {gating.compute_savings_pct:.1f}%]",
                (rx1 + 5, max(20, ry1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 240, 0),
                1,
            )

        # -------------------------------------------------------------
        # 3. Draw YOLO Detections
        # -------------------------------------------------------------
        for det in detections:
            gx1, gy1, gx2, gy2 = det.global_box
            color = (0, 255, 120) if det.hazard_info.category == "PEDESTRIAN" else (0, 70, 255)
            cv2.rectangle(canvas, (gx1, gy1), (gx2, gy2), color, 2)
            label = f"{det.class_name.upper()} ({det.confidence*100:.0f}%)"
            cv2.putText(canvas, label, (gx1, gy1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # -------------------------------------------------------------
        # 4. Draw HUD Telemetry Header & Metrics Panel
        # -------------------------------------------------------------
        # Header banner
        cv2.rectangle(canvas, (0, 0), (w, 55), (15, 15, 20), -1)
        cv2.line(canvas, (0, 55), (w, 55), (0, 240, 255), 1)

        # Status indicator
        if gating.is_triggered:
            status_color = (0, 0, 255) if ttc_res.urgency_level == "IMMINENT" else (0, 180, 255)
            status_text = f"STAGE 1 INTERRUPT ACTIVE [< {config.DEPTH_THRESHOLD_M}m]"
        else:
            status_color = (0, 255, 0)
            status_text = f"STAGE 1 IDLE [LOW-POWER MODE > {config.DEPTH_THRESHOLD_M}m]"

        cv2.circle(canvas, (20, 27), 7, status_color, -1)
        cv2.putText(canvas, status_text, (35, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        # Telemetry stats on bottom panel
        cv2.rectangle(canvas, (0, h - 75), (w, h), (15, 15, 20), -1)
        cv2.line(canvas, (0, h - 75), (w, h - 75), (80, 80, 80), 1)

        col1 = f"DIST: {gating.min_distance_m:.2f}m | SECTOR: {gating.primary_azimuth} ({gating.primary_elevation})"
        col2 = f"V_APP: {ttc_res.approach_velocity_mps:+.2f} m/s | TTC: {ttc_res.ttc_seconds:.2f}s [{ttc_res.urgency_level}]"
        col3 = f"WAVEFORM: #{waveform_id} | COMPUTE SAVINGS: {gating.compute_savings_pct:.1f}%"

        cv2.putText(canvas, col1, (15, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
        cv2.putText(canvas, col2, (15, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
        cv2.putText(canvas, col3, (15, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 255, 100), 1)

        return canvas

    def run_sim_loop(
        self,
        num_frames: int = 60,
        show_window: bool = False,
        save_sample_image: bool = True,
    ):
        """Executes simulation visual loop."""
        print(f"[sim_vision] Starting visual simulation ({num_frames} frames, show_window={show_window})...")

        last_rendered_canvas = None

        for step in range(num_frames):
            t_now = time.time() + (step * 0.033)
            # Alternating simulation scenario
            scenario_idx = (step // 20) % 3
            scenarios = ["approaching_person", "side_vehicle", "clear_path"]
            scenario = scenarios[scenario_idx]
            depth_matrix = self.generate_simulated_depth(step, scenario)

            # Step 1: Stage 1 Gate
            gating = self.gate.evaluate(depth_matrix)

            # Step 2: Optical acquisition
            _, frame = self.camera.read_frame()

            detections = []
            if gating.is_triggered:
                roi = self.camera.crop_roi(frame, gating.roi_box)
                detections = self.yolo.infer_roi(roi, gating.roi_box, gating.primary_elevation)

            # Step 3: TTC
            ttc_res = self.ttc.update(
                distance_m=gating.min_distance_m,
                sector=gating.primary_azimuth,
                timestamp=t_now,
            )

            # Step 4: Waveform
            base_hazard = detections[0].hazard_info if detections else ClassMap.resolve_hazard(elevation_sector=gating.primary_elevation)
            waveform_id = ClassMap.select_waveform_by_urgency(base_hazard, ttc_res.urgency_level)

            # Step 5: Render
            canvas = self.render_frame(frame, gating, detections, ttc_res, waveform_id)
            last_rendered_canvas = canvas

            if show_window and OPENCV_AVAILABLE and cv2 is not None:
                try:
                    cv2.imshow("Context-Aware Smart Glasses - Module 2 HUD", canvas)
                    key = cv2.waitKey(33) & 0xFF
                    if key == ord("q"):
                        break
                except Exception:
                    show_window = False

            if step % 15 == 0:
                print(
                    f"Frame {step:3d} [{scenario:18s}]: Dist={gating.min_distance_m:.2f}m | "
                    f"V_app={ttc_res.approach_velocity_mps:+.2f} m/s | "
                    f"TTC={ttc_res.ttc_seconds:.2f}s [{ttc_res.urgency_level:11s}] | "
                    f"Savings={gating.compute_savings_pct:.1f}%"
                )

        if show_window and OPENCV_AVAILABLE and cv2 is not None:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass

        # Save an image artifact if requested
        if save_sample_image and last_rendered_canvas is not None:
            out_path = os.path.join(os.path.dirname(__file__), "..", "sim_hud_sample.png")
            try:
                from PIL import Image
                # Convert BGR to RGB for PIL
                rgb_canvas = last_rendered_canvas[:, :, ::-1] if last_rendered_canvas.ndim == 3 else last_rendered_canvas
                img = Image.fromarray(rgb_canvas)
                img.save(out_path)
                print(f"[sim_vision] Saved sample HUD frame to: {os.path.abspath(out_path)}")
            except Exception as e:
                print(f"[sim_vision] Notice: Could not save HUD image: {e}")

        self.camera.release()
        print("[sim_vision] Visual simulation completed successfully.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Context-Aware Smart Glasses - Vision HUD Simulator")
    parser.add_argument("--window", action="store_true", help="Display live OpenCV window")
    parser.add_argument("--frames", type=int, default=60, help="Number of frames to simulate")
    args = parser.parse_args()

    simulator = VisionSimulatorHUD()
    simulator.run_sim_loop(num_frames=args.frames, show_window=args.window)
