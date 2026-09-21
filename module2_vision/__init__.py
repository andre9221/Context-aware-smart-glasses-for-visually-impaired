"""
Module 2: Dual-Stage AI Vision & Time-to-Collision (TTC) Engine
Lead: Dhivyashree G J. (24BCE1516)

Components:
- ToFDepthGate: Stage 1 spatial interrupt gate & dynamic ROI frame cropper
- CameraDriver: Unified camera capture wrapper with synthetic fallback
- YOLOEngine: YOLOv8 Nano inference engine on cropped ROI
- TTCEngine: Rolling approach rate & Time-to-Collision calculator
- ClassMap: Hazard classification and severity weighting
- sim_vision: Interactive visual simulation testbed with HUD
- main_vision: Inter-process worker connecting Queue A to Queue B
"""

from .tof_gate import ToFDepthGate, GatingDecision
from .camera_driver import CameraDriver
from .yolo_engine import YOLOEngine, Detection
from .ttc_engine import TTCEngine, TTCResult
from .class_map import ClassMap, HazardSeverity

__all__ = [
    "ToFDepthGate",
    "GatingDecision",
    "CameraDriver",
    "YOLOEngine",
    "Detection",
    "TTCEngine",
    "TTCResult",
    "ClassMap",
    "HazardSeverity",
]
