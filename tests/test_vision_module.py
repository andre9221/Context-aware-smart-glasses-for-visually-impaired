"""
Unit & Integration Test Suite for Module 2: AI Vision & TTC Engine
Author: Dhivyashree G J. (24BCE1516)
"""

import multiprocessing
import time
import unittest
import numpy as np

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from module2_vision.tof_gate import ToFDepthGate, GatingDecision
from module2_vision.camera_driver import CameraDriver
from module2_vision.yolo_engine import YOLOEngine
from module2_vision.ttc_engine import TTCEngine
from module2_vision.class_map import ClassMap
from module2_vision.main_vision import run_vision_module


class TestToFDepthGate(unittest.TestCase):
    """Verifies Stage 1 Spatial Interrupt Gating & Dynamic ROI calculations (Novelty 03)."""

    def setUp(self):
        self.gate = ToFDepthGate(
            depth_threshold_m=2.0,
            frame_width=640,
            frame_height=480,
            padding_ratio=0.1,
        )

    def test_idle_state_when_depth_above_threshold(self):
        """When all 64 zones are > 2.0m, system must stay idle (100% compute savings)."""
        safe_matrix = [[3.5] * 8 for _ in range(8)]
        decision = self.gate.evaluate(safe_matrix)

        self.assertFalse(decision.is_triggered)
        self.assertEqual(decision.compute_savings_pct, 100.0)
        self.assertEqual(decision.roi_box, (0, 0, 0, 0))
        self.assertEqual(len(decision.active_zones), 0)

    def test_spatial_interrupt_trigger(self):
        """When a zone is <= 2.0m, interrupt must trigger with correct active coordinates."""
        matrix = [[3.5] * 8 for _ in range(8)]
        # Place obstacle at row 2, col 3 (Center sector, Head hazard) at 1.2m
        matrix[2][3] = 1.2

        decision = self.gate.evaluate(matrix)

        self.assertTrue(decision.is_triggered)
        self.assertAlmostEqual(decision.min_distance_m, 1.2, places=2)
        self.assertEqual(decision.nearest_zone, (2, 3))
        self.assertEqual(decision.primary_azimuth, "Center")
        self.assertEqual(decision.primary_elevation, "HeadHazard")
        self.assertGreater(decision.compute_savings_pct, 50.0)  # High compute savings

        # Verify pixel bounds are strictly within frame dimensions
        x1, y1, x2, y2 = decision.roi_box
        self.assertGreaterEqual(x1, 0)
        self.assertGreaterEqual(y1, 0)
        self.assertLessEqual(x2, 640)
        self.assertLessEqual(y2, 480)
        self.assertGreater(x2, x1)
        self.assertGreater(y2, y1)

    def test_sector_classification(self):
        """Validates Left, Center, and Right sector binning."""
        # Left sector (col 1)
        m_left = [[3.5] * 8 for _ in range(8)]
        m_left[4][1] = 1.0
        d_left = self.gate.evaluate(m_left)
        self.assertEqual(d_left.primary_azimuth, "Left")
        self.assertEqual(d_left.primary_elevation, "GroundObstacle")

        # Right sector (col 6)
        m_right = [[3.5] * 8 for _ in range(8)]
        m_right[1][6] = 1.0
        d_right = self.gate.evaluate(m_right)
        self.assertEqual(d_right.primary_azimuth, "Right")
        self.assertEqual(d_right.primary_elevation, "HeadHazard")

    def test_millimeter_auto_conversion(self):
        """If raw sensor driver sends depths in millimeters (> 20mm), auto-convert to meters."""
        mm_matrix = [[3500.0] * 8 for _ in range(8)]
        mm_matrix[2][4] = 1200.0  # 1200mm = 1.2m
        decision = self.gate.evaluate(mm_matrix)

        self.assertTrue(decision.is_triggered)
        self.assertAlmostEqual(decision.min_distance_m, 1.2, places=2)
        self.assertEqual(decision.nearest_zone, (2, 4))


class TestTTCEngine(unittest.TestCase):
    """Verifies approach velocity and Time-to-Collision math (Novelty 02)."""

    def setUp(self):
        self.ttc = TTCEngine(
            window_size=5,
            imminent_threshold_s=0.8,
            approaching_threshold_s=2.0,
        )

    def test_approaching_obstacle_kinematics(self):
        """Simulates an approaching target: distance decreasing at 1.0 m/s."""
        t0 = 100.0
        # Frame 1: 2.0m at t=100.0
        self.ttc.update(distance_m=2.0, sector="Center", timestamp=t0)
        # Frame 2: 1.5m at t=100.5 (approaching at 1.0 m/s)
        res = self.ttc.update(distance_m=1.5, sector="Center", timestamp=t0 + 0.5)

        self.assertTrue(res.is_approaching)
        self.assertAlmostEqual(res.approach_velocity_mps, 1.0, delta=0.1)
        # TTC = 1.5m / 1.0m/s = 1.5s -> APPROACHING
        self.assertEqual(res.urgency_level, "APPROACHING")

    def test_imminent_collision_urgency(self):
        """Simulates high-speed closing target resulting in TTC < 0.8s."""
        t0 = 200.0
        self.ttc.update(distance_m=1.2, sector="Center", timestamp=t0)
        self.ttc.update(distance_m=0.8, sector="Center", timestamp=t0 + 0.2)
        # Velocity ~ 2.0 m/s; Distance = 0.5m -> TTC ~ 0.25s
        res = self.ttc.update(distance_m=0.5, sector="Center", timestamp=t0 + 0.35)

        self.assertTrue(res.is_approaching)
        self.assertLess(res.ttc_seconds, 0.8)
        self.assertEqual(res.urgency_level, "IMMINENT")

    def test_static_obstacle_stays_safe(self):
        """Static obstacle with zero approach velocity must have SAFE urgency."""
        t0 = 300.0
        self.ttc.update(distance_m=1.5, sector="Center", timestamp=t0)
        res = self.ttc.update(distance_m=1.5, sector="Center", timestamp=t0 + 0.5)

        self.assertFalse(res.is_approaching)
        self.assertEqual(res.urgency_level, "SAFE")

    def test_receding_obstacle_stays_safe(self):
        """Obstacle moving away must have negative approach rate and SAFE urgency."""
        t0 = 400.0
        self.ttc.update(distance_m=1.0, sector="Center", timestamp=t0)
        res = self.ttc.update(distance_m=1.5, sector="Center", timestamp=t0 + 0.5)

        self.assertFalse(res.is_approaching)
        self.assertEqual(res.urgency_level, "SAFE")


class TestClassMap(unittest.TestCase):
    """Verifies COCO class translations and DRV2605L waveform mapping."""

    def test_coco_mappings(self):
        p_hazard = ClassMap.resolve_hazard(coco_class_id=0)  # person
        self.assertEqual(p_hazard.category, "PEDESTRIAN")
        self.assertEqual(p_hazard.texture_type, "soft")

        v_hazard = ClassMap.resolve_hazard(coco_class_id=2)  # car
        self.assertEqual(v_hazard.category, "VEHICLE")
        self.assertEqual(v_hazard.texture_type, "sharp")

    def test_waveform_modulation_by_urgency(self):
        hazard = ClassMap.resolve_hazard(coco_class_id=0)

        # IMMINENT urgency always commands sharp buzz #47
        w_imminent = ClassMap.select_waveform_by_urgency(hazard, "IMMINENT")
        self.assertEqual(w_imminent, 47)

        # APPROACHING commands class default (#12 for person)
        w_approaching = ClassMap.select_waveform_by_urgency(hazard, "APPROACHING")
        self.assertEqual(w_approaching, 12)

        # SAFE commands gentle pulse #1
        w_safe = ClassMap.select_waveform_by_urgency(hazard, "SAFE")
        self.assertEqual(w_safe, 1)


class TestCameraDriverAndYOLO(unittest.TestCase):
    """Verifies frame generation, ROI cropping and YOLO coordinate re-projection."""

    def setUp(self):
        self.camera = CameraDriver(width=640, height=480, force_simulation=True)
        self.yolo = YOLOEngine(force_simulation=True)

    def tearDown(self):
        self.camera.release()

    def test_frame_read_and_roi_crop(self):
        ret, frame = self.camera.read_frame()
        self.assertTrue(ret)
        self.assertEqual(frame.shape, (480, 640, 3))

        roi_box = (100, 80, 300, 280)
        roi = self.camera.crop_roi(frame, roi_box)
        self.assertEqual(roi.shape, (200, 200, 3))

    def test_yolo_roi_inference(self):
        _, frame = self.camera.read_frame()
        roi_box = (150, 100, 350, 300)
        roi = self.camera.crop_roi(frame, roi_box)

        detections = self.yolo.infer_roi(roi, roi_box, elevation_hint="HeadHazard")
        self.assertGreater(len(detections), 0)

        det = detections[0]
        self.assertIn(det.class_name, ["person", "car", "bicycle"])
        self.assertGreater(det.confidence, 0.5)

        # Verify global box is properly translated by ROI offset
        gx1, gy1, gx2, gy2 = det.global_box
        self.assertGreaterEqual(gx1, 150)
        self.assertGreaterEqual(gy1, 100)


class TestMainVisionPipelineIntegration(unittest.TestCase):
    """Verifies full inter-process queue integration (Queue A -> Vision -> Queue B)."""

    def test_end_to_end_pipeline_execution(self):
        q_a = multiprocessing.Queue()
        q_b = multiprocessing.Queue()

        # Place simulated depth packet into Queue A
        packet_a = {
            "timestamp": time.time(),
            "depth_matrix": [[3.5] * 8 for _ in range(8)],
            "head_yaw_deg": 0.0,
            "head_pitch_deg": 0.0,
        }
        # Place hazard in Center at 1.1m
        packet_a["depth_matrix"][2][4] = 1.1
        q_a.put(packet_a)

        # Run worker for 1 iteration
        run_vision_module(q_a, q_b, max_iterations=1)

        try:
            packet_b = q_b.get(timeout=2.0)
        except Exception:
            packet_b = None
        self.assertIsNotNone(packet_b, "Queue B should have received a hazard packet")

        # Validate Queue B schema matches Tejaswi's Module 3 expectations
        required_keys = [
            "timestamp",
            "triggered",
            "head_yaw_deg",
            "head_pitch_deg",
            "azimuth",
            "elevation",
            "min_distance_m",
            "roi_box",
            "primary_class",
            "hazard_category",
            "approach_velocity_mps",
            "ttc_seconds",
            "urgency",
            "suggested_waveform_id",
            "roi_compute_savings_pct",
            "vision_latency_ms",
        ]
        for k in required_keys:
            self.assertIn(k, packet_b, f"Missing key in Queue B payload: {k}")

        self.assertTrue(packet_b["triggered"])
        self.assertEqual(packet_b["azimuth_name"], "Center")
        self.assertEqual(packet_b["head_yaw_deg"], 0.0)
        self.assertAlmostEqual(packet_b["min_distance_m"], 1.1, places=1)
        self.assertGreater(packet_b["roi_compute_savings_pct"], 50.0)

        # Test interoperability with Module 3 HapticEncoder
        from module3_haptic.haptic_encoder import HapticEncoder
        encoder = HapticEncoder()
        self.assertTrue(
            encoder.validate_packet(packet_b),
            "Queue B packet failed Module 3 HapticEncoder validation schema"
        )
        encoded_cmd = encoder.encode(packet_b)
        self.assertIsNotNone(encoded_cmd, "HapticEncoder failed to encode Queue B packet")


if __name__ == "__main__":
    unittest.main()
