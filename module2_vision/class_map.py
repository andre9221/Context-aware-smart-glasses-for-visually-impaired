"""
Class Mapping, Hazard Severity & Tactile Texture Translation
Author: Dhivyashree G J. (24BCE1516)

Maps YOLO COCO classes and ToF elevation tags to semantic hazard categories,
severity ratings, and recommended DRV2605L haptic vibration profiles.
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class HazardSeverity:
    category: str              # PEDESTRIAN, VEHICLE, OVERHEAD_HAZARD, GROUND_OBSTACLE, GENERAL
    severity_score: int        # 1 (lowest) to 5 (highest)
    texture_type: str          # "soft", "sharp", "prolonged"
    default_waveform_id: int   # DRV2605L ROM waveform index
    description: str


class ClassMap:
    """Translates raw visual detections into prioritized hazard entities."""

    # Pre-defined semantic hazard categories
    CATEGORY_PEDESTRIAN = "PEDESTRIAN"
    CATEGORY_VEHICLE = "VEHICLE"
    CATEGORY_OVERHEAD = "OVERHEAD_HAZARD"
    CATEGORY_GROUND = "GROUND_OBSTACLE"
    CATEGORY_GENERAL = "GENERAL_OBSTACLE"

    # COCO Class ID to Hazard mapping
    COCO_HAZARD_MAP: Dict[int, HazardSeverity] = {
        0: HazardSeverity(
            category=CATEGORY_PEDESTRIAN,
            severity_score=4,
            texture_type="soft",
            default_waveform_id=12,  # Double Click 100%
            description="Pedestrian or moving person",
        ),
        1: HazardSeverity(
            category=CATEGORY_VEHICLE,
            severity_score=4,
            texture_type="sharp",
            default_waveform_id=47,  # Strong Buzz 100%
            description="Bicycle or micromobility",
        ),
        2: HazardSeverity(
            category=CATEGORY_VEHICLE,
            severity_score=5,
            texture_type="sharp",
            default_waveform_id=47,  # Strong Buzz 100%
            description="Automobile / Car",
        ),
        3: HazardSeverity(
            category=CATEGORY_VEHICLE,
            severity_score=5,
            texture_type="sharp",
            default_waveform_id=47,  # Strong Buzz 100%
            description="Motorcycle / High-speed vehicle",
        ),
        5: HazardSeverity(
            category=CATEGORY_VEHICLE,
            severity_score=5,
            texture_type="sharp",
            default_waveform_id=47,  # Strong Buzz 100%
            description="Bus / Heavy vehicle",
        ),
        7: HazardSeverity(
            category=CATEGORY_VEHICLE,
            severity_score=5,
            texture_type="sharp",
            default_waveform_id=47,  # Strong Buzz 100%
            description="Truck / Large vehicle",
        ),
    }

    # Fallback hazard profile when detected by ToF depth without visual classification
    TOF_FALLBACK_HAZARD = HazardSeverity(
        category=CATEGORY_GENERAL,
        severity_score=3,
        texture_type="prolonged",
        default_waveform_id=1,  # Gentle Pulsing Buzz
        description="Unclassified depth obstacle",
    )

    OVERHEAD_HAZARD = HazardSeverity(
        category=CATEGORY_OVERHEAD,
        severity_score=4,
        texture_type="prolonged",
        default_waveform_id=14,  # Pulsing Alert
        description="Head-height overhanging branch or low beam",
    )

    GROUND_HAZARD = HazardSeverity(
        category=CATEGORY_GROUND,
        severity_score=3,
        texture_type="soft",
        default_waveform_id=10,  # Single Click
        description="Ground-level trip hazard or steps",
    )

    @classmethod
    def get_coco_ids(cls) -> list[int]:
        """Returns list of monitored COCO class IDs."""
        return list(cls.COCO_HAZARD_MAP.keys())

    @classmethod
    def resolve_hazard(
        cls,
        coco_class_id: Optional[int] = None,
        elevation_sector: Optional[str] = None,
    ) -> HazardSeverity:
        """
        Resolves the comprehensive hazard profile based on visual classification
        and physical elevation context from the ToF sensor.
        """
        if coco_class_id is not None and coco_class_id in cls.COCO_HAZARD_MAP:
            return cls.COCO_HAZARD_MAP[coco_class_id]

        if elevation_sector == "HeadHazard":
            return cls.OVERHEAD_HAZARD
        elif elevation_sector == "GroundObstacle":
            return cls.GROUND_HAZARD

        return cls.TOF_FALLBACK_HAZARD

    @classmethod
    def select_waveform_by_urgency(
        cls,
        base_hazard: HazardSeverity,
        urgency: str,
    ) -> int:
        """
        Selects DRV2605L waveform ID modulated by urgency (Novelty 02).
        - IMMINENT: Always high-urgency buzz (#47)
        - APPROACHING: Hazard-specific tactile texture
        - SAFE: Low-intensity gentle alert (#1)
        """
        if urgency == "IMMINENT":
            return 47  # High-intensity sharp buzz
        elif urgency == "APPROACHING":
            return base_hazard.default_waveform_id
        else:  # SAFE or general awareness
            return 1   # Soft gentle pulse
