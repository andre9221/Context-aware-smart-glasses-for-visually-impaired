"""
Global configuration for the Context-Aware Smart Glasses project.
Shared across module1_sensor, module2_vision, module3_haptic and dashboard.

Only Module 1's (Andrea's) constants are filled in with real values here.
Dhivyashree and Tejaswi should extend this file with their own sections
(vision thresholds, haptic waveform maps, Firebase keys, etc.) as they
build Modules 2 and 3, without touching the Module 1 block below.
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
