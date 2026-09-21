"""
Camera Capture Driver & ROI Cropping Wrapper
Author: Dhivyashree G J. (24BCE1516)

Provides a unified interface for optical acquisition:
- OpenCV USB / Laptop webcam (cv2.VideoCapture)
- Raspberry Pi Camera Module CSI (picamera2 / libcamera)
- Synthetic scene generator for offline simulation, unit testing, and headless execution
"""

import time
from typing import Optional, Tuple
import numpy as np

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config

# Optional OpenCV and Picamera2 imports with graceful fallbacks
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False

try:
    from picamera2 import Picamera2
    PICAM2_AVAILABLE = True
except ImportError:
    Picamera2 = None
    PICAM2_AVAILABLE = False


class CameraDriver:
    """Hardware-agnostic camera driver with dynamic ROI cropping capabilities."""

    def __init__(
        self,
        camera_index: int = config.CAMERA_INDEX,
        width: int = config.CAMERA_WIDTH,
        height: int = config.CAMERA_HEIGHT,
        fps: int = config.CAMERA_FPS,
        force_simulation: bool = False,
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.force_simulation = force_simulation or config.SIMULATION_MODE

        self.cap = None
        self.picam2 = None
        self.is_opened = False
        self._sim_step = 0

        self._initialize_device()

    def _initialize_device(self):
        """Attempts to open physical camera (Pi Camera CSI or OpenCV USB); falls back to synthetic mode."""
        if not self.force_simulation:
            # 1. Attempt Raspberry Pi Camera CSI initialization
            if PICAM2_AVAILABLE and Picamera2 is not None:
                try:
                    self.picam2 = Picamera2()
                    config_cam = self.picam2.create_video_configuration(
                        main={"size": (self.width, self.height), "format": "BGR888"}
                    )
                    self.picam2.configure(config_cam)
                    self.picam2.start()
                    self.is_opened = True
                    print("[CameraDriver] Raspberry Pi Camera CSI initialized via Picamera2.")
                    return
                except Exception as e:
                    print(f"[CameraDriver] Picamera2 init notice: {e}")
                    self.picam2 = None

            # 2. Attempt USB / Webcam initialization via OpenCV
            if OPENCV_AVAILABLE and cv2 is not None:
                try:
                    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
                    self.cap = cv2.VideoCapture(self.camera_index, backend)
                    if self.cap.isOpened():
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
                        self.is_opened = True
                        print(f"[CameraDriver] OpenCV Camera (index {self.camera_index}) initialized.")
                        return
                except Exception as e:
                    print(f"[CameraDriver] Warning: Physical camera initialization failed: {e}")

        # Fallback to simulation mode
        self.is_opened = False
        self.cap = None

    def read_frame(self) -> Tuple[bool, np.ndarray]:
        """
        Captures the next full camera frame (BGR format).
        Returns: (success_bool, frame_array)
        """
        # Picamera2 frame acquisition
        if self.is_opened and self.picam2 is not None:
            try:
                frame = self.picam2.capture_array()
                if frame is not None:
                    return True, frame
            except Exception as e:
                print(f"[CameraDriver] Picamera2 capture error: {e}")

        # OpenCV VideoCapture acquisition
        if self.is_opened and self.cap is not None:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                if frame.shape[1] != self.width or frame.shape[0] != self.height:
                    if OPENCV_AVAILABLE and cv2 is not None:
                        frame = cv2.resize(frame, (self.width, self.height))
                return True, frame

        # Generate synthetic simulation frame
        return True, self._generate_synthetic_frame()

    def crop_roi(
        self,
        frame: np.ndarray,
        roi_box: Tuple[int, int, int, int],
    ) -> np.ndarray:
        """
        Extracts cropped sub-image corresponding to the dynamic ToF ROI box.
        Args:
            frame: Full BGR image (H, W, 3)
            roi_box: (x1, y1, x2, y2)
        Returns:
            Cropped BGR image
        """
        x1, y1, x2, y2 = roi_box
        h, w = frame.shape[:2]

        # Bounds safety clamping
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))

        cropped = frame[y1:y2, x1:x2]
        return cropped

    def _generate_synthetic_frame(self) -> np.ndarray:
        """
        Generates a realistic synthetic test scene (e.g. urban sidewalk with moving hazard)
        for simulation and automated testing without requiring webcam hardware.
        """
        self._sim_step += 1
        # Create dark outdoor / road backdrop
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Horizon & ground gradient
        frame[: self.height // 2, :] = (40, 35, 30)   # Sky / building tone
        frame[self.height // 2 :, :] = (60, 60, 60)   # Pavement / road

        # Draw road perspective guidelines
        cx = self.width // 2
        cy = self.height // 2

        # Draw a synthetic moving obstacle (representing an approaching pedestrian)
        phase = (self._sim_step % 60) / 60.0
        obs_w = int(40 + phase * 80)
        obs_h = int(80 + phase * 160)
        obs_x = cx - obs_w // 2
        obs_y = cy + int(phase * 40) - obs_h // 2

        ox1 = max(0, obs_x)
        oy1 = max(0, obs_y)
        ox2 = min(self.width, obs_x + obs_w)
        oy2 = min(self.height, obs_y + obs_h)

        # Draw simulated obstacle / target
        frame[oy1:oy2, ox1:ox2] = (180, 140, 50)

        # If OpenCV is available, draw simulated text watermark
        if OPENCV_AVAILABLE and cv2 is not None:
            cv2.putText(
                frame,
                f"SIMULATED SCENE (Step {self._sim_step})",
                (20, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 240, 255),
                2,
            )

        return frame

    def release(self):
        """Releases camera resources cleanly."""
        if self.picam2 is not None:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None

        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.is_opened = False
