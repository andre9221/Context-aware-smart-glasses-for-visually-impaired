"""
Global Configuration and Constants for Context-Aware Smart Glasses System.
Hardware mode ONLY (Raspberry Pi 4) — no simulation, no synthetic data.
"""

import os
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent

# ==============================================================================
# OPERATION & POWER MODES
# ==============================================================================
# Power Mode: "LOW" (ToF depth + haptics only, camera/AI off ~0.5W)
#             "HIGH" (ToF depth + dynamic Camera ROI + YOLOv8n vehicle classification)
POWER_MODE = os.getenv("POWER_MODE", "HIGH").upper()

# ==============================================================================
# HARDWARE I2C & PIN CONFIGURATION (Raspberry Pi 4)
# ==============================================================================
I2C_BUS_ID = 1

# I2C Addresses (Standard default 7-bit addresses)
VL53L7CX_I2C_ADDR = 0x29   # ST VL53L7CX 8x8 Multizone Time-of-Flight LiDAR
VL53L5CX_I2C_ADDR = VL53L7CX_I2C_ADDR  # Backwards compatibility alias
MPU6050_I2C_ADDR = 0x68    # 6-Axis IMU (Gyroscope + Accelerometer) — WHO_AM_I chip ID is 0x70 (MPU6500 revision), I2C address is 0x68
DRV2605L_I2C_ADDR = 0x5A   # TI Haptic Driver (123 ROM Waveforms)
PCA9548A_I2C_ADDR = 0x70   # PCA9548A 8-Channel I2C Multiplexer

# Actuator Channels / LRA Motor Identifiers
MOTOR_LEFT = "LEFT"
MOTOR_CENTER = "CENTER"
MOTOR_RIGHT = "RIGHT"
ALL_MOTORS = [MOTOR_LEFT, MOTOR_CENTER, MOTOR_RIGHT]

# Motor Type: "LRA" (Linear Resonant Actuators) or "ERM" (DC eccentric coin vibration discs)
HAPTIC_MOTOR_TYPE = os.getenv("HAPTIC_MOTOR_TYPE", "LRA").upper()

PCA9548A_CHANNELS = {
    MOTOR_LEFT: 6,    # Channel 6 (SD6/SC6): Left Haptic Driver (0x5B)
    MOTOR_CENTER: 1,  # Channel 1 (SD1/SC1): Middle/Center Haptic Driver (0x5A)
    MOTOR_RIGHT: 2,   # Channel 2 (SD2/SC2): Right Haptic Driver (0x5A)
}

# GPIO Pinout for DRV2605L EN / Trigger pins or Multi-channel PWM (BCM numbering)
GPIO_LRA_LEFT = 17
GPIO_LRA_CENTER = 27
GPIO_LRA_RIGHT = 22

# Optional GPIO wiring for hardware interrupts (BCM numbering)
MPU6050_INT_GPIO = 4          # physical pin 7
VL53L7CX_LPN_GPIO = 24        # physical pin 18 (LPn Low Power / Reset)
VL53L7CX_INT_GPIO = 25        # physical pin 22 (Data Ready Interrupt)

# ==============================================================================
# SENSOR & SAMPLING FREQUENCIES
# ==============================================================================
IMU_SAMPLE_RATE_HZ = 100    # 100 Hz kinematic tracking
TOF_SAMPLE_RATE_HZ = 30     # 30 Hz multizone depth matrix
# The validated Python ULD backend needs about 0.15–0.20 s for a real VL53L7CX
# 8x8 frame on the shared I2C bus. This avoids polling faster than it can respond.
TOF_HARDWARE_RANGING_HZ = int(os.getenv("TOF_HARDWARE_RANGING_HZ", "5"))
VISION_MAX_FPS = 15         # Dynamic ROI YOLOv8n inference cap on Pi 4

TOF_GRID_ROWS = 8
TOF_GRID_COLS = 8
TOF_TOTAL_ZONES = 64
TOF_FOV_HORIZONTAL_DEG = 90.0  # Horizontal Field of View (45 deg either side)
TOF_FOV_VERTICAL_DEG = 90.0    # Vertical Field of View (45 deg elevation span)
TOF_MAX_RANGE_METERS = 4.0     # Maximum physical measurement range

# ==============================================================================
# NOVELTY 01: KINEMATICS & EGO-MOTION PARAMETERS
# ==============================================================================
COMPLEMENTARY_FILTER_ALPHA = 0.98   # Weight for gyro vs accelerometer integration
MAX_COMPENSATED_YAW_DEG = 90.0      # Maximum expected head rotation angle

# Spatial Azimuth Binning (Columns 0 to 7)
# Columns 0-2: Left, Columns 3-4: Center, Columns 5-7: Right
SECTOR_LEFT_COLS = (0, 1, 2)
SECTOR_CENTER_COLS = (3, 4)
SECTOR_RIGHT_COLS = (5, 6, 7)

# Vertical Elevation Binning (Rows 0 to 7)
# Rows 0-3: Head-height & overhanging hazards
# Rows 4-7: Ground-level & descending obstacles
ELEVATION_HEAD_ROWS = (0, 1, 2, 3)
ELEVATION_GROUND_ROWS = (4, 5, 6, 7)

# ==============================================================================
# NOVELTY 03: DUAL-STAGE SPATIAL INTERRUPT GATING
# ==============================================================================
# Depth interrupt threshold: If all zones > 1.0m, camera & YOLOv8 remain idle
DEPTH_INTERRUPT_THRESHOLD_M = 1.0

# Camera Resolution
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# Dynamic ROI Margin (padding added to cropped box in pixels)
ROI_PADDING_PX = 20

# YOLOv8 Target Classes (COCO indices prioritized for pedestrian safety)
# 0: person, 1: bicycle, 2: car, 3: motorcycle, 5: bus, 7: truck
YOLO_TARGET_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
YOLO_MODEL_NAME = os.getenv("YOLO_MODEL_NAME", str(BASE_DIR / "yolov8n.pt"))
YOLO_CONFIDENCE_THRESHOLD = 0.40
YOLO_IMAGE_SIZE = int(os.getenv("YOLO_IMAGE_SIZE", "416"))

# ==============================================================================
# NOVELTY 02: TIME-TO-COLLISION (TTC) & SPATIO-TACTILE ENCODING
# ==============================================================================
TTC_ROLLING_WINDOW_SIZE = 5      # Rolling frame window for approach rate dv/dt
TTC_MIN_VELOCITY_MPS = 0.01      # Minimum approach velocity clamp to avoid div by zero

# TTC Urgency Boundaries
TTC_IMMINENT_THRESHOLD_S = 0.8    # < 0.8s: Imminent collision -> High-rate sharp buzz
TTC_APPROACHING_THRESHOLD_S = 2.0 # 0.8s - 2.0s: Approaching -> Double-click pulse
                                  # > 2.0s: Safe situational awareness -> Gentle pulse

# DRV2605L ROM Waveform Presets (from 123-effect library)
WAVEFORM_SAFE_AWARENESS = 2        # "Strong Click - 60%"
WAVEFORM_APPROACHING_ALERT = 49    # "Buzz 3 - 60% Medium Buzz"
WAVEFORM_IMMINENT_COLLISION = 49   # "Buzz 3 - 60% Medium Buzz"
WAVEFORM_OVERHEAD_HAZARD = 15      # "Medium Click 1 - 100%"
WAVEFORM_PERSON_SOFT = 64          # "Transition Hum 1 - 100%"
WAVEFORM_VEHICLE_SHARP = 49        # "Buzz 3 - 60% Medium Buzz"

# ==============================================================================
# NOVELTY 02: DISTANCE-TO-COLOUR HAPTIC INTENSITY MAPPING
# Matches the terminal depth matrix colour coding:
#   RED    < HAPTIC_ZONE_RED_CM    → strongest buzz (imminent)
#   ORANGE < HAPTIC_ZONE_ORANGE_CM → medium buzz    (close)
#   YELLOW < HAPTIC_ZONE_YELLOW_CM → soft click     (approaching)
#   GREEN  ≥ HAPTIC_ZONE_YELLOW_CM → no buzz        (safe)
# ==============================================================================
HAPTIC_ZONE_RED_CM    = 15   # cm — Red zone threshold
HAPTIC_ZONE_ORANGE_CM = 35   # cm — Orange zone threshold
HAPTIC_ZONE_YELLOW_CM = 70   # cm — Yellow zone threshold

WAVEFORM_ZONE_RED    = 49   # "Buzz 3 - 60% Medium" — reduced from 100% strong
WAVEFORM_ZONE_ORANGE = 52   # "Pulsing Strong 1" — soft pulse
WAVEFORM_ZONE_YELLOW = 2    # "Strong Click - 60%" — very gentle tap
# Green zone: no waveform, motors silent

# ==============================================================================
# TELEMETRY & CLOUD CONFIGURATION
# ==============================================================================
LOCAL_LOG_DIR = BASE_DIR / "logs"
LOCAL_TELEMETRY_FILE = LOCAL_LOG_DIR / "telemetry_events.jsonl"
LOCAL_LOG_DIR.mkdir(exist_ok=True)

# Firebase Realtime Database
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", str(BASE_DIR / "firebase_credentials.json"))
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "https://smart-glasses-telemetry-default-rtdb.firebaseio.com")
FIREBASE_BATCH_INTERVAL_S = 0.2  # 200 ms batch push interval

# Dashboard Local Server
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8080"))