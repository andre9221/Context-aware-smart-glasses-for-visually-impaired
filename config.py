"""
Global configuration for the Context-Aware Smart Glasses project.
Shared across module1_sensor, module2_vision, module3_haptic and dashboard.
"""

# ---------------------------------------------------------------------------
# Global run mode
# ---------------------------------------------------------------------------
SIMULATION_MODE = True  # Flip to False once the Pi 4 + sensors are wired up

# ---------------------------------------------------------------------------
# I2C bus addresses (locked BOM, Section 3 of PROJECT_PLAN.md)
# ---------------------------------------------------------------------------
I2C_BUS_NUM = 1
VL53L5CX_I2C_ADDR = 0x29
MPU6050_I2C_ADDR = 0x68
DRV2605L_I2C_ADDR = 0x5A  # used by Module 3

# ---------------------------------------------------------------------------
# Module 1 — Sensor Fusion & Ego-Motion (Andrea)
# ---------------------------------------------------------------------------
TOF_GRID_SIZE = 8                # 8x8 = 64 zones
TOF_FOV_DEG = 90.0                # VL53L5CX field of view
TOF_RATE_HZ = 30
IMU_RATE_HZ = 100
FUSION_LOOP_HZ = 100              # main_sensor.py loop rate (IMU-paced; ToF frame held between updates)

# Zone binning thresholds (kept for reference; zone_classifier.py bins by
# CORRECTED angle, not raw row/col, but these show the raw-grid intuition)
AZIMUTH_LEFT_COLS = (0, 1, 2)
AZIMUTH_CENTER_COLS = (3, 4)
AZIMUTH_RIGHT_COLS = (5, 6, 7)
ELEVATION_HEAD_ROWS = (0, 1, 2, 3)     # top half of the 8x8 grid = head-height hazards
ELEVATION_GROUND_ROWS = (4, 5, 6, 7)   # bottom half = ground obstacles

# Complementary filter
COMPLEMENTARY_ALPHA = 0.98  # weight on gyro integration vs accel correction

# Inter-process queues (used by main.py / main_sensor.py)
QUEUE_MAXSIZE = 10

# ---------------------------------------------------------------------------
# Module 2 — Dual-Stage AI Vision & Time-to-Collision (Dhivyashree)
# ---------------------------------------------------------------------------
# Stage 1: Spatial Interrupt Depth Gating (Novelty 03)
DEPTH_THRESHOLD_M = 2.0  # meters. If all 64 zones > 2.0m, camera & AI sleep
TOF_MAX_RANGE_M = 4.0    # ST VL53L5CX max physical distance (meters)

TOF_ROWS = 8
TOF_COLS = 8
TOF_TOTAL_ZONES = 64

# Azimuth sector mapping (0..7 columns)
AZIMUTH_SECTOR_MAP = {
    "Left": list(range(0, 3)),     # cols 0, 1, 2
    "Center": list(range(3, 5)),   # cols 3, 4
    "Right": list(range(5, 8)),    # cols 5, 6, 7
}

# Elevation binning (0..7 rows)
ELEVATION_MAP = {
    "HeadHazard": list(range(0, 4)),     # top 4 rows
    "GroundObstacle": list(range(4, 8)), # bottom 4 rows
}

# Camera & Dynamic ROI Cropping Configuration
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30
CAMERA_INDEX = 0
ROI_PADDING_RATIO = 0.15

# Time-to-Collision (TTC) Kinematics (Novelty 02)
TTC_WINDOW_SIZE = 5
TTC_IMMINENT_THRESHOLD_S = 0.8     # TTC < 0.8s: High urgency imminent collision
TTC_APPROACHING_THRESHOLD_S = 2.0  # 0.8s <= TTC <= 2.0s: Approaching hazard
MIN_APPROACH_VELOCITY_MPS = 0.05

# YOLOv8 Nano Inference Configuration
YOLO_MODEL_NAME = "yolov8n.pt"
YOLO_CONFIDENCE_THRESHOLD = 0.35
YOLO_IMG_SIZE = 320

# Navigation hazard target COCO classes
TARGET_COCO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# ---------------------------------------------------------------------------
# Module 3 — Spatio-Tactile Haptics & Firebase Telemetry (Tejaswi)
# ---------------------------------------------------------------------------
MOTOR_INDEX_LEFT = 0
MOTOR_INDEX_CENTER = 1
MOTOR_INDEX_RIGHT = 2

AZIMUTH_TO_MOTOR = {"L": 0, "C": 1, "R": 2}
VALID_AZIMUTHS = {"L", "C", "R"}
VALID_ELEVATIONS = {"head", "ground"}
REQUIRED_PACKET_KEYS = {"ts", "azimuth", "distance", "ttc", "class", "elevation"}

URGENCY_IMMINENT = "imminent"
URGENCY_APPROACHING = "approaching"
URGENCY_SAFE = "safe"
SUPPORTED_URGENCIES = {"imminent", "approaching", "safe"}
SUPPORTED_CLASSES = {"person", "vehicle", "overhead", "wall"}

TTC_SENTINEL_SAFE = float("inf")
TTC_MIN_VALID = 0.0
TTC_MAX_VALID = 60.0
TTC_IMMINENT_THRESHOLD = 0.8
TTC_APPROACHING_MAX = 2.0

HAZARD_TIMEOUT_MS = 500
DEFAULT_MIN_PLAY_TIME_MS = 150
EFFECT_MIN_DURATION_MS = {15: 750, 16: 1000}

# DRV2605L Library 6 (LRA) ROM Waveforms: (effect_id, repeat_interval_ms)
WAVEFORM_TABLE = {
    "person": {
        "imminent": (7, 250),    # Soft Bump 100%
        "approaching": (8, 500), # Soft Bump 60%
        "safe": (9, 1000),       # Soft Bump 30%
    },
    "vehicle": {
        "imminent": (4, 200),    # Sharp Click 100%
        "approaching": (5, 400), # Sharp Click 60%
        "safe": (6, 800),        # Sharp Click 30%
    },
    "overhead": {
        "imminent": (16, 1100),  # 1000ms Alert 100%
        "approaching": (15, 850),# 750ms Alert 100%
        "safe": (10, 1000),      # Double Click 100%
    },
    "wall": {
        "imminent": (10, 300),   # Double Click 100%
        "approaching": (11, 600),# Double Click 60%
        "safe": (3, 1000),       # Strong Click 30%
    },
}

# DRV2605L Hardware Registers
REG_MODE = 0x01
MODE_INTERNAL_TRIGGER = 0x00
REG_LIBRARY_SEL = 0x03
DRV2605L_LIBRARY = 0x06
REG_WAVEFORM_SEQ_1 = 0x04
REG_GO = 0x0C
GO_FIRE = 0x01
REG_FEEDBACK_CTRL = 0x1A
FEEDBACK_LRA_BIT = 0x80

# Firebase Telemetry Configuration
SESSION_ID = "session_001"
FIREBASE_CRED_PATH = "serviceAccountKey.json"
FIREBASE_DB_URL = "https://context-smart-glasses-default-rtdb.firebaseio.com"
