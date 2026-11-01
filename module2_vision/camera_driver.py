"""
Camera Acquisition Driver (Pi Camera CSI / OpenCV USB)
Lead Researcher: Dhivyashree G J. (24BCE1516)
REAL HARDWARE ONLY — no synthetic frames.
"""

import time
import numpy as np
from typing import Optional, Tuple

from config import (
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_FPS,
)


class CameraDriver:
    """Wrapper supporting Raspberry Pi Camera CSI and OpenCV USB/webcam. No fake frames."""

    def __init__(self, camera_index: int = 0, width: int = CAMERA_WIDTH, height: int = CAMERA_HEIGHT):
        self.width = width
        self.height = height
        self.cap = None
        self._picam2 = None
        self.is_opened = False

        self._init_camera(camera_index)

    def _init_camera(self, camera_index: int):
        """
        Camera init priority:
          1. picamera2 (Pi CSI ribbon, CAM/DISP 0)
          2. OpenCV VideoCapture as last resort
        """
        # ── Raspberry Pi 4 CSI camera via picamera2 ──────────────────────────
        try:
            from picamera2 import Picamera2
            import libcamera

            picam2 = Picamera2()
            cfg = picam2.create_video_configuration(
                main={"size": (self.width, self.height), "format": "RGB888"},
                controls={"FrameRate": float(CAMERA_FPS)},
            )
            picam2.configure(cfg)
            picam2.start()
            self._picam2 = picam2
            self.is_opened = True
            print(f"[CameraDriver] ✅ picamera2 CSI camera started ({self.width}x{self.height} @ {CAMERA_FPS}fps)")
            return
        except Exception as e:
            print(f"[CameraDriver] picamera2 init failed: {e}")

        # ── Last resort: OpenCV ──────────────────────────────────────────────
        try:
            import cv2
            self.cap = cv2.VideoCapture(camera_index)
            if self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                self.cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                self.is_opened = True
                print(f"[CameraDriver] ⚠️  OpenCV fallback camera at index {camera_index}")
                return
        except Exception as e:
            print(f"[CameraDriver] OpenCV fallback also failed: {e}")

        print("[CameraDriver] No physical camera is available.")
        self.is_opened = False

    def capture_frame(self) -> Tuple[bool, np.ndarray]:
        """Captures a BGR image frame (H, W, 3). Returns (False, None) if no camera."""
        if self._picam2 is not None:
            try:
                frame = self._picam2.capture_array("main")
                if frame is None:
                    return False, None
                if frame.ndim == 3 and frame.shape[2] == 3:
                    frame = frame[:, :, ::-1].copy()
                return True, frame
            except Exception as exc:
                print(f"[CameraDriver] CSI capture error: {exc}")
                return False, None

        if self.cap is not None:
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    if frame.shape[0] != self.height or frame.shape[1] != self.width:
                        import cv2
                        frame = cv2.resize(frame, (self.width, self.height))
                    return True, frame
            except Exception:
                pass

        return False, None

    def release(self):
        if self._picam2 is not None:
            try:
                self._picam2.stop()
            except Exception:
                pass
            self._picam2 = None
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.is_opened = False
