# Module 2 — Dual-Stage AI Vision & Time-to-Collision (TTC) Pipeline
**Lead Developer:** Dhivyashree G J. (24BCE1516)  
**Paper Novelties Co-Led:**
- **Novelty 03 (Lead): Dual-Stage Spatial Interrupt Vision Gating** — Uses ST VL53L5CX 8×8 ToF LiDAR as a low-power depth pre-filter (<2.0m interrupt) and dynamically crops camera Region of Interest (ROI) for YOLOv8n inference, cutting compute by >70% on Raspberry Pi 4.
- **Novelty 02 (Co-Lead): 3-Axis Spatio-Tactile Time-to-Collision (TTC) Encoding** — Rolling approach velocity derivation ($v_{\text{approach}} = \frac{\Delta d}{\Delta t}$) and TTC calculation ($\frac{d_t}{\max(v_{\text{approach}}, 0.01)}$) to distinguish closing collision threats from static obstacles.

---

## Directory & File Structure

```text
module2_vision/
├── tof_gate.py         # Stage 1 depth threshold & dynamic ROI bounding box calculator
├── camera_driver.py    # Camera capture wrapper (Pi Camera CSI Picamera2 / OpenCV USB / Synthetic testbed)
├── yolo_engine.py      # YOLOv8n inference on cropped ROI with offline simulation fallback
├── ttc_engine.py       # Rolling approach rate & TTC computation across temporal window
├── class_map.py        # COCO class filtering, hazard categorization & DRV2605L waveform mapping
├── sim_vision.py       # Laptop webcam mock vision testbed with real-time HUD telemetry
├── main_vision.py      # Process entry: Queue A (Andrea) -> AI/TTC -> Queue B (Tejaswi)
├── __init__.py         # Package exports
└── README.md           # Module documentation
```

---

## Data Contracts & Interfaces

### 1. Ingestion from Queue A (Andrea's Module 1)
Consumes sensor packets from `module1_sensor/main_sensor.py`:
- `packet["raw"]["distance_mm"]`: 8×8 ego-motion compensated distance matrix in mm (auto-converted to meters)
- `packet["yaw_deg"]`, `packet["pitch_deg"]`: Drift-free head orientation from IMU filter
- `packet["bins"]`: 3×2 sector min distances

### 2. Output to Queue B (Tejaswi's Module 3 & Dashboard)
Pushes structured event packets:
```python
{
    "timestamp": 1790009104.98,
    "triggered": True,
    "head_yaw_deg": 14.2,
    "head_pitch_deg": -2.1,
    "azimuth": "Center",
    "elevation": "HeadHazard",
    "min_distance_m": 0.65,
    "nearest_zone": (2, 3),
    "roi_box": (204, 93, 516, 327),
    "detected_classes": ["person"],
    "primary_class": "person",
    "hazard_category": "PEDESTRIAN",
    "hazard_severity": 4,
    "approach_velocity_mps": 0.80,
    "ttc_seconds": 0.68,
    "urgency": "IMMINENT",
    "suggested_waveform_id": 47,
    "roi_compute_savings_pct": 76.2,
    "vision_latency_ms": 2.86
}
```

---

## Testing & Verification

Run the automated test suite:
```powershell
python -m unittest discover -s tests -v
```

Run the multi-scenario benchmark demonstration:
```powershell
python demo_dhivyashree.py
```

Run the visual simulation HUD:
```powershell
python module2_vision/sim_vision.py
```
