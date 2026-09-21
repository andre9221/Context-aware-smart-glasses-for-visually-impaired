"""
Stage 1 Spatial Interrupt Gate & Dynamic ROI Frame Cropper (Novelty 03 Lead)
Author: Dhivyashree G J. (24BCE1516)

Evaluates 8x8 multizone ToF depth matrices from Module 1.
If no obstacles exist within DEPTH_THRESHOLD_M (default 2.0m), the camera
and AI stay idle, saving >70% compute on Raspberry Pi 4.
When triggered, calculates the dynamic Region of Interest (ROI) bounding box
for selective YOLOv8n inference.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import config


@dataclass
class GatingDecision:
    """Encapsulates the Stage 1 spatial interrupt and ROI projection results."""
    is_triggered: bool
    min_distance_m: float
    nearest_zone: Tuple[int, int]  # (row, col)
    active_zones: List[Tuple[int, int]]  # list of (row, col) <= threshold
    roi_box: Tuple[int, int, int, int]  # (xmin, ymin, xmax, ymax) in pixels
    roi_normalized: Tuple[float, float, float, float]  # (nx1, ny1, nx2, ny2) in [0, 1]
    compute_savings_pct: float
    primary_azimuth: str  # "Left", "Center", "Right"
    primary_elevation: str  # "HeadHazard", "GroundObstacle"


class ToFDepthGate:
    """
    Stage 1 Spatial Pre-Filter & Coordinate Re-Projection Engine.
    Maps 8x8 ToF LiDAR coordinates to 2D optical frame coordinates.
    """

    def __init__(
        self,
        depth_threshold_m: float = config.DEPTH_THRESHOLD_M,
        frame_width: int = config.CAMERA_WIDTH,
        frame_height: int = config.CAMERA_HEIGHT,
        padding_ratio: float = config.ROI_PADDING_RATIO,
    ):
        self.depth_threshold_m = depth_threshold_m
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.padding_ratio = padding_ratio
        self.total_pixels = frame_width * frame_height

    def evaluate(self, depth_data: Any) -> GatingDecision:
        """
        Evaluates incoming depth array or Queue A packet.
        
        Args:
            depth_data: Either an 8x8 list/np.ndarray of floats (depths in meters)
                        or a dictionary from Queue A containing 'depth_matrix'.
        
        Returns:
            GatingDecision dataclass.
        """
        if isinstance(depth_data, dict):
            # Check Andrea's Module 1 fused packet structures
            if "raw" in depth_data and isinstance(depth_data["raw"], dict) and "distance_mm" in depth_data["raw"]:
                matrix = np.array(depth_data["raw"]["distance_mm"], dtype=np.float32)
            elif "distance_mm" in depth_data:
                matrix = np.array(depth_data["distance_mm"], dtype=np.float32)
            elif "depth_matrix" in depth_data:
                matrix = np.array(depth_data["depth_matrix"], dtype=np.float32)
            elif "bins" in depth_data:
                min_bin_dist = min((v for v in depth_data["bins"].values() if v is not None), default=4000.0)
                matrix = np.full((config.TOF_ROWS, config.TOF_COLS), min_bin_dist, dtype=np.float32)
            else:
                raise ValueError(f"Could not find distance array in depth_data keys: {list(depth_data.keys())}")
        elif isinstance(depth_data, (list, np.ndarray)):
            matrix = np.array(depth_data, dtype=np.float32)
        else:
            raise ValueError(f"Unsupported depth data format: {type(depth_data)}")

        # Ensure 8x8 matrix shape
        if matrix.shape != (config.TOF_ROWS, config.TOF_COLS):
            if matrix.size == config.TOF_TOTAL_ZONES:
                matrix = matrix.reshape((config.TOF_ROWS, config.TOF_COLS))
            else:
                raise ValueError(
                    f"Expected 8x8 ({config.TOF_TOTAL_ZONES} zones), got shape {matrix.shape}"
                )

        # Defensive hardware compatibility:
        # If raw ToF driver outputs distance in millimeters (e.g., max range ~4000 mm),
        # auto-convert to meters.
        if np.nanmax(matrix) > 20.0:
            matrix = matrix / 1000.0

        # Replace invalid/negative/near-zero distances with max range
        matrix = np.where((matrix <= 0.05) | np.isnan(matrix), config.TOF_MAX_RANGE_M, matrix)

        # Find minimum distance and nearest zone
        min_distance_m = float(np.min(matrix))
        min_idx_flat = int(np.argmin(matrix))
        min_row, min_col = divmod(min_idx_flat, config.TOF_COLS)

        # Find all zones strictly under the threshold
        active_mask = matrix <= self.depth_threshold_m
        active_indices = np.argwhere(active_mask)  # List of [row, col]

        # Stage 1 Spatial Gating Check
        if len(active_indices) == 0 or min_distance_m > self.depth_threshold_m:
            # Gating condition: No obstacle within threshold -> IDLE state
            # ROI is None/Zero, 100% compute saved
            return GatingDecision(
                is_triggered=False,
                min_distance_m=min_distance_m,
                nearest_zone=(min_row, min_col),
                active_zones=[],
                roi_box=(0, 0, 0, 0),
                roi_normalized=(0.0, 0.0, 0.0, 0.0),
                compute_savings_pct=100.0,
                primary_azimuth=self._resolve_azimuth(min_col),
                primary_elevation=self._resolve_elevation(min_row),
            )

        # Active zones found: Calculate dynamic ROI bounding box
        rows = active_indices[:, 0]
        cols = active_indices[:, 1]
        r_min, r_max = int(np.min(rows)), int(np.max(rows))
        c_min, c_max = int(np.min(cols)), int(np.max(cols))

        # Map 8x8 grid bounds to normalized camera FoV [0.0, 1.0]
        # Column 0 is left, Column 7 is right; Row 0 is top, Row 7 is bottom
        nx1 = c_min / float(config.TOF_COLS)
        nx2 = (c_max + 1) / float(config.TOF_COLS)
        ny1 = r_min / float(config.TOF_ROWS)
        ny2 = (r_max + 1) / float(config.TOF_ROWS)

        # Add safety margin padding
        width_norm = nx2 - nx1
        height_norm = ny2 - ny1
        pad_x = width_norm * self.padding_ratio
        pad_y = height_norm * self.padding_ratio

        nx1 = max(0.0, nx1 - pad_x)
        ny1 = max(0.0, ny1 - pad_y)
        nx2 = min(1.0, nx2 + pad_x)
        ny2 = min(1.0, ny2 + pad_y)

        # Convert to absolute pixel coordinates
        x1 = int(nx1 * self.frame_width)
        y1 = int(ny1 * self.frame_height)
        x2 = int(nx2 * self.frame_width)
        y2 = int(ny2 * self.frame_height)

        # Ensure non-zero minimum dimensions (at least 32x32 pixels for YOLO)
        if (x2 - x1) < 32:
            mid_x = (x1 + x2) // 2
            x1 = max(0, mid_x - 16)
            x2 = min(self.frame_width, mid_x + 16)
        if (y2 - y1) < 32:
            mid_y = (y1 + y2) // 2
            y1 = max(0, mid_y - 16)
            y2 = min(self.frame_height, mid_y + 16)

        # Compute compute savings metric
        roi_area = float((x2 - x1) * (y2 - y1))
        compute_savings_pct = max(0.0, (1.0 - (roi_area / self.total_pixels)) * 100.0)

        active_zone_tuples = [(int(r), int(c)) for r, c in active_indices]

        return GatingDecision(
            is_triggered=True,
            min_distance_m=min_distance_m,
            nearest_zone=(min_row, min_col),
            active_zones=active_zone_tuples,
            roi_box=(x1, y1, x2, y2),
            roi_normalized=(nx1, ny1, nx2, ny2),
            compute_savings_pct=compute_savings_pct,
            primary_azimuth=self._resolve_azimuth(min_col),
            primary_elevation=self._resolve_elevation(min_row),
        )

    def _resolve_azimuth(self, col: int) -> str:
        """Determines spatial sector from grid column index."""
        if col in config.AZIMUTH_SECTOR_MAP["Left"]:
            return "Left"
        elif col in config.AZIMUTH_SECTOR_MAP["Center"]:
            return "Center"
        else:
            return "Right"

    def _resolve_elevation(self, row: int) -> str:
        """Determines elevation hazard category from grid row index."""
        if row in config.ELEVATION_MAP["HeadHazard"]:
            return "HeadHazard"
        else:
            return "GroundObstacle"
