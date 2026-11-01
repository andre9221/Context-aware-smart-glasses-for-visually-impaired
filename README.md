# Context-Aware Smart Glasses for Visually Impaired Navigation
### An Edge-to-Cloud Assistive System with Kinematic Ego-Motion Compensation & Spatio-Tactile Haptics

**Research Team:**
- **Andrea A.** (24BCE1142) — Sensor Fusion, Kinematics & Ego-Motion Engine (*Novelty 01 Lead*)
- **Dhivyashree G J.** (24BCE1516) — Dual-Stage AI Vision & Time-to-Collision (TTC) Pipeline (*Novelty 02 & 03 Co-Lead*)
- **Tejaswi E.** (24BCE5518) — 3-Axis Spatio-Tactile Haptic Engine & Caregiver Web Dashboard (*Novelty 02 Co-Lead & IoT Lead*)

**Target Journal:** *IEEE Sensors Journal* / *MDPI Sensors* / *IEEE Access*

---

## 1. System Overview & Core Novelties

This repository contains the complete physical edge software ecosystem for context-aware smart glasses designed for assistive pedestrian navigation. It solves three major limitations found in commercial assistive glasses ($2,500+) and academic prototypes:

1. **Novelty 01: Head-to-Torso Kinematic Transform ($R(\theta_{\text{head}})$):**
   - Head-mounted sensors (8×8 ToF) rotate when the user turns their head, which in traditional systems causes false alerts (e.g., turning to check a crosswalk falsely buzzes the "forward" motor for a shop window).
   - An onboard **quaternion rotation matrix at 100 Hz** re-projects all 64 depth vectors from the head-mounted sensor frame into the fixed torso reference frame, yielding **100% azimuth routing accuracy** across the operational field-of-view (vs. 14.3% uncompensated).
2. **Novelty 02: Multi-Axis Spatio-Tactile Encoding:**
   - Simultaneously conveys **Azimuth** (Left/Center/Right LRA) × **Urgency** (Distance Colour Zones & Time-to-Collision $TTC = \frac{d}{\Delta d/\Delta t}$) × **Tactile Texture** (TI DRV2605L ROM waveforms) without acoustic sensory deprivation.
   - Dynamically mapped colour zones:
     - 🔴 **RED (< 15 cm):** Waveform 49 (60% Buzz) — Imminent collision alert.
     - 🟠 **ORANGE (15 – 35 cm):** Waveform 52 (Pulsing Strong) — Approaching obstacle.
     - 🟡 **YELLOW (35 – 70 cm):** Waveform 2 (Strong Click 60%) — Gentle awareness pulse.
     - 🟢 **GREEN (> 70 cm):** Silent — Clear walking corridor.
3. **Novelty 03: Dual-Stage Spatial Depth-Interrupt Gating:**
   - The ST VL53L7CX 8×8 ToF operates as a low-power hardware depth pre-filter.
   - **Smart Wake-up Condition**: Camera and YOLOv8n neural networks wake up **ONLY** if:
     - At least **1 RED cell** (< 30 cm) is detected, OR
     - At least **7 YELLOW cells** (30 cm – 100 cm) are detected (filtering out single-cell transient noise).
   - When awake, YOLOv8n infers only on a dynamic cropped **Region of Interest (ROI)** around the obstacle cluster, saving **>70% compute power** and drastically reducing thermal load on Raspberry Pi 4.

---

## 2. Hardware Wiring & Architecture (Raspberry Pi 4)

All sensors communicate over Raspberry Pi I2C Bus 1 (`/dev/i2c-1`):

| Device | Model | I2C Address | Notes |
|---|---|---|---|
| **8×8 Multizone ToF** | ST VL53L7CX | `0x29` | 64 zones up to 4m, LPn on GPIO 24 |
| **6-Axis IMU** | InvenSense MPU6050 | `0x68` | WHO_AM_I `0x70` (MPU6500 silicon rev) |
| **I2C Multiplexer** | TI PCA9548A | `0x70` | 8-channel multiplexer |
| **Left Haptic Driver** | TI DRV2605L | `0x5A` (Mux CH6) | Left Temple LRA Motor |
| **Center Haptic Driver** | TI DRV2605L | `0x5A` (Mux CH1) | Center Bridge LRA Motor |
| **Right Haptic Driver** | TI DRV2605L | `0x5A` (Mux CH2) | Right Temple LRA Motor |
| **CSI Camera** | Sony IMX219 / Pi Cam | CSI Ribbon | 640×480 @ 30 FPS Dynamic ROI |

---

## 3. Repository Architecture

```text
ES_Software/
├── config.py                      # Global hardware pinouts, addresses, and thresholds
├── main.py                        # Multi-process orchestrator (Sensors, Vision, Haptics, Dashboard)
├── requirements.txt               # Dependencies
├── .env.example                   # Telemetry & Firebase environment template
│
├── module1_sensor/                # Andrea A. (Sensor Fusion & Ego-Motion)
│   ├── tof_driver.py              # ST VL53L7CX hardware driver with status filtering
│   ├── imu_driver.py              # MPU6050 14-byte atomic read & stationary gyro calibration
│   ├── ego_motion.py              # Novelty 01: Quaternion R(θ) head-to-torso re-projection
│   ├── zone_classifier.py         # Spatial binning & smart depth gating (1 Red / 7 Yellow)
│   └── main_sensor.py             # Process entry: runs fusion loop and pushes to Queue A
│
├── module2_vision/                # Dhivyashree G J. (AI Vision & TTC)
│   ├── tof_gate.py                # Novelty 03: Dual-stage interrupt gating & ROI mapper
│   ├── camera_driver.py           # Picamera2 hardware CSI wrapper (640x480)
│   ├── yolo_engine.py             # YOLOv8n inference on dynamic cropped ROI
│   ├── ttc_engine.py              # Novelty 02: Approach velocity & Time-To-Collision
│   ├── class_map.py               # COCO hazard priority filtering
│   └── main_vision.py             # Process entry: Queue A -> AI/TTC -> Queue B + Live Video Queue
│
├── module3_haptic/                # Tejaswi E. (Haptics & Telemetry)
│   ├── drv2605l_driver.py         # TI DRV2605L multiplexed driver & auto-calibration
│   ├── haptic_encoder.py          # Novelty 02: 3-axis spatio-tactile mapping
│   ├── waveform_map.py            # DRV2605L 123-waveform library mapping
│   ├── firebase_logger.py         # Realtime DB streamer + local research logger
│   └── main_haptic.py             # Process entry: Queue B -> Multi-sector LRA actuation
│
├── dashboard/                     # Tejaswi E. (Caregiver & Researcher Web App)
│   ├── index.html                 # Glassmorphic UI: live camera feed, 8x8 radar, LRA pulses
│   ├── style.css                  # Obsidian dark theme (#0B0F19), cyan/emerald glows
│   ├── app.js                     # Real-time WebSockets / SSE telemetry client
│   └── server.py                  # Local HTTP + MJPEG video feed server (FastAPI/Uvicorn)
│
└── scripts/                       # Research Validation & Hardware Utility Suite
    ├── ablation_study.py          # Automated evaluation: WITH vs WITHOUT ego-motion
    ├── latency_benchmark.py       # End-to-end pipeline latency profiling
    ├── test_all_hardware.py       # Unified bench test for all sensors & motors
    ├── scan_all_8_channels.py     # Live diagnostic I2C bus scanner
    └── cycle_all_motors.py        # Independent LRA motor buzz test
```

---

## 4. Running the System on Raspberry Pi 4

### Step 1: Activate Environment & Reset Sensors
```bash
cd ~/smart_glasses
source venv/bin/activate
pinctrl set 24 op dh
```

### Step 2: Launch Full Hardware Pipeline
```bash
python3 main.py --real --dashboard
```

### Step 3: Access Live Guardian / Researcher Dashboard
Open your browser on any laptop or phone connected to the same Wi-Fi:
- **URL:** `http://<PI_IP_ADDRESS>:8080` (e.g., `http://192.168.137.172:8080`)
- **Login Credentials:**
  - Researcher: `researcher` / `Glasses2026!`
  - Caregiver: `caregiver` / `Caregiver2026!`

---

## 5. Paper Reproducibility & Benchmarks

### 1. Novelty 01 Ablation Study (Ego-Motion Compensation)
```bash
python3 scripts/ablation_study.py
```
- **Azimuth Routing Accuracy WITHOUT Ego-Motion:** 14.3% (Baseline)
- **Azimuth Routing Accuracy WITH Ego-Motion:** 100.0% (Novelty 01)
- **Mean Angular Error Reduction:** 86.0% (from 24.91° to 3.48°)

### 2. Latency & Real-Time Profiler
```bash
python3 scripts/latency_benchmark.py
```
- **Total Pipeline Latency:** ~1.06 ms (Throughput: >900 Hz)
- Fully satisfies real-time human perception threshold ($\le 30.0\text{ ms}$).
