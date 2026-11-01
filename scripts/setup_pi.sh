#!/usr/bin/env bash
# ==============================================================================
# Smart Glasses Setup Script for Raspberry Pi 4 / 5 (8GB)
# Lead Researcher: Andrea A. (24BCE1142)
#
# Configures I2C, system dependencies, PyTorch CPU (no CUDA bloat),
# VL53L7CX ULD driver, and the virtual environment.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "================================================================="
echo "   SMART GLASSES - SYSTEM SETUP & DEPENDENCIES (Raspberry Pi 4)  "
echo "================================================================="

# 1. Enable I2C
echo -e "\n[1/6] Enabling Raspberry Pi I2C Bus..."
sudo raspi-config nonint do_i2c 0 || true

# 2. System Packages via apt
echo -e "\n[2/6] Installing required system tools & pre-built libraries..."
sudo apt-get update -y
sudo apt-get install -y \
    i2c-tools \
    python3-smbus \
    python3-pip \
    python3-venv \
    python3-numpy \
    python3-scipy \
    python3-pil \
    python3-opencv \
    python3-picamera2 \
    python3-rpi.gpio \
    git

# 3. Create Virtual Environment with system site packages (enables picamera2 & GPIO)
echo -e "\n[3/6] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv --system-site-packages venv
    echo "Created venv with --system-site-packages."
else
    echo "Virtual environment 'venv' already exists."
fi

# Activate venv
source venv/bin/activate

# 4. Install PyTorch CPU (prevents downloading 500MB+ NVIDIA CUDA drivers)
echo -e "\n[4/6] Installing PyTorch CPU & Ultralytics..."
export TMPDIR="$HOME/tmp"
mkdir -p "$TMPDIR"
pip install --upgrade pip
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics
pip install fastapi uvicorn requests python-dotenv smbus2

# 5. Setup VL53L7CX / VL53L5CX ULD Driver
echo -e "\n[5/6] Checking VL53L7CX ULD Driver..."
if [ ! -d "$HOME/vl53l5cx_python" ]; then
    echo "Cloning VL53L7CX ULD Python wrapper into ~/vl53l5cx_python..."
    git clone https://github.com/Abstract-Horizon/vl53l5cx_python "$HOME/vl53l5cx_python"
    cd "$HOME/vl53l5cx_python"
    pip install .
    cd "$PROJECT_ROOT"
else
    echo "Found ~/vl53l5cx_python. Ensuring installed in venv..."
    cd "$HOME/vl53l5cx_python"
    pip install . || true
    cd "$PROJECT_ROOT"
fi

# 6. Run Hardware Check
echo -e "\n[6/6] Running Hardware Preflight Check..."
python3 scripts/pi_hardware_check.py

echo -e "\n================================================================="
echo "  SETUP COMPLETE! To start the system with live web dashboard:   "
echo "      source venv/bin/activate                                    "
echo "      python3 main.py --real --dashboard                          "
echo "=================================================================\n"

