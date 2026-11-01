"""
Dynamic ROI YOLOv8n Inference Engine
Lead Researcher: Dhivyashree G J. (24BCE1516)

Executes neural object detection exclusively on the dynamically cropped ROI
derived from the Stage 1 ToF depth interrupt.
"""

import time
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

from config import (
    YOLO_MODEL_NAME,
    YOLO_CONFIDENCE_THRESHOLD,
    YOLO_TARGET_CLASSES,
    YOLO_IMAGE_SIZE,
)
import config
from .class_map import get_class_name
from .tof_gate import RegionOfInterest


@dataclass
class DetectedObject:
    class_id: int
    class_name: str
    confidence: float
    # Global frame bounding box coordinates
    bbox_global: Tuple[int, int, int, int]  # (xmin, ymin, xmax, ymax)
    # ROI local bounding box coordinates
    bbox_roi: Tuple[int, int, int, int]
    center_x: float
    center_y: float


class YOLOv8ROIEngine:
    """YOLOv8 Nano inference engine running on cropped sub-regions of interest."""

    def __init__(self, model_name: str = YOLO_MODEL_NAME, conf_thresh: float = YOLO_CONFIDENCE_THRESHOLD):
        self.model_name = model_name
        self.conf_thresh = conf_thresh
        self.model = None
        self.is_loaded = False
        self.last_error: Optional[str] = None

        self._init_model()

    def _init_model(self):
        """Attempt to load Ultralytics YOLOv8n model."""
        try:
            from ultralytics import YOLO
            print(f"[YOLOv8] Loading {self.model_name}...")
            self.model = YOLO(self.model_name)
            self.is_loaded = True
            print(f"[YOLOv8] Successfully loaded {self.model_name}")
        except Exception as e:
            self.last_error = str(e)
            print(f"[YOLOv8] Model initialization failed: {e}")
            self.is_loaded = False

    def infer_roi(
        self,
        full_frame: np.ndarray,
        roi: RegionOfInterest,
    ) -> List[DetectedObject]:
        """
        Crop full_frame to roi bounds, run inference on crop, map coordinates back to full_frame.
        """
        h_frame, w_frame = full_frame.shape[:2]
        xmin, ymin, xmax, ymax = roi.xmin, roi.ymin, roi.xmax, roi.ymax

        # Validate crop boundaries
        if xmax <= xmin or ymax <= ymin or xmin >= w_frame or ymin >= h_frame:
            return []

        cropped_roi = full_frame[ymin:ymax, xmin:xmax]
        detections: List[DetectedObject] = []

        if self.is_loaded and self.model is not None:
            try:
                # Run inference specifically on the cropped sub-image
                results = self.model(
                    cropped_roi,
                    conf=self.conf_thresh,
                    classes=list(YOLO_TARGET_CLASSES.keys()),
                    imgsz=YOLO_IMAGE_SIZE,
                    verbose=False,
                )

                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        conf = float(box.conf[0].item())
                        cls_name = YOLO_TARGET_CLASSES.get(cls_id, get_class_name(cls_id))

                        # Local ROI coords
                        rx1, ry1, rx2, ry2 = box.xyxy[0].tolist()

                        # Re-project to global frame coordinates
                        gx1 = int(rx1 + xmin)
                        gy1 = int(ry1 + ymin)
                        gx2 = int(rx2 + xmin)
                        gy2 = int(ry2 + ymin)

                        cx = (gx1 + gx2) / 2.0
                        cy = (gy1 + gy2) / 2.0

                        detections.append(DetectedObject(
                            class_id=cls_id,
                            class_name=cls_name,
                            confidence=conf,
                            bbox_global=(gx1, gy1, gx2, gy2),
                            bbox_roi=(int(rx1), int(ry1), int(rx2), int(ry2)),
                            center_x=cx,
                            center_y=cy,
                        ))
                return detections
            except Exception as e:
                self.last_error = str(e)
                print(f"[YOLOv8] Inference error: {e}")

        # No model available — return empty (no fake detections ever)
        return []
