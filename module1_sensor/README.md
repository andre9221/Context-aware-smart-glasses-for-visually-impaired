# Module 1 — Sensor Fusion, Kinematics & Ego-Motion (Andrea A., 24BCE1142)

Novelty 01 lead: head-to-torso kinematic transform, Section 3 of the paper.

## Files

| File | Role |
|---|---|
| `tof_driver.py` | VL53L5CX 8×8 ToF acquisition (30 Hz) via `vl53l5cx-ctypes` |
| `imu_driver.py` | MPU6050 accel/gyro acquisition + complementary filter → yaw/pitch (100 Hz) |
| `ego_motion.py` | **Novelty 01 core** — quaternion rotation `R(θ_head)` re-projecting the 64 zone vectors from the sensor (head) frame into the torso frame |
| `zone_classifier.py` | Bins the corrected 64-zone field into Left/Center/Right × Head/Ground |
| `sim_sensor.py` | Hardware-free simulator (synthetic 8×8 depth + sinusoidal yaw sweep) so Modules 2/3 can develop without hardware |
| `main_sensor.py` | Process entry point — runs the fusion loop, pushes classified packets onto **Queue A** |
| `ablation_study.py` | Paper Section 6 data: logs azimuth error WITH vs WITHOUT ego-motion compensation across 45°/90° sweeps |

## Quick start (no hardware needed)

```bash
cd embedded_smart_glasses
pip install -r requirements.txt
python module1_sensor/main_sensor.py        # 5s smoke test in SIMULATION_MODE
python module1_sensor/ablation_study.py --amplitude 45
python module1_sensor/ablation_study.py --amplitude 90
```

Each `ablation_study.py` run writes `ablation_<amplitude>deg.csv` (columns:
timestamp, head yaw, ground-truth azimuth, raw vs corrected measured
azimuth, raw vs corrected absolute error) — plot `corrected_abs_error_deg`
vs `raw_abs_error_deg` for the paper's Fig. (Novelty 01 ablation).

## On real hardware

1. Set `SIMULATION_MODE = False` in `config.py` (root).
2. Wire `VL53L5CX` → I2C `0x29`, `MPU6050` → I2C `0x68` (see BOM, Section 3
   of `PROJECT_PLAN.md`).
3. `python module1_sensor/tof_driver.py` and `python module1_sensor/imu_driver.py`
   each run a standalone smoke test — confirm both independently before
   running the full fusion loop.
4. Re-run `imu_driver.py`'s calibration (glasses held still) if you notice
   yaw drifting faster than expected — it recalibrates gyro bias on every
   `MPU6050()` init.

## Known limitation (flag in the paper's limitations subsection)

Yaw comes from gyro-only integration (no magnetometer on the MPU6050), so
it drifts slowly over time even though pitch/roll are drift-corrected via
gravity. Fine for the short (<10 s) ablation sweeps; worth naming as
future work (magnetometer fusion, or a periodic vision-based yaw reset
from Module 2) rather than glossing over it.

## Integration contract (Queue A → Module 2)

`main_sensor.py` pushes one dict per frame onto `out_queue`:

```python
{
  "bins": {
      ("LEFT", "HEAD"): 1180.0,     # nearest mm in that bin, or None if clear
      ("LEFT", "GROUND"): None,
      ("CENTER", "HEAD"): 3400.0,
      ("CENTER", "GROUND"): None,
      ("RIGHT", "HEAD"): None,
      ("RIGHT", "GROUND"): None,
  },
  "raw": {  # full corrected 8x8 field, if Module 2 needs zone-level detail
      "distance_mm": <8x8 np.ndarray>,
      "azimuth_deg": <8x8 np.ndarray>,
      "elevation_deg": <8x8 np.ndarray>,
      "R": <3x3 np.ndarray>,
  },
  "yaw_deg": -12.4,
  "pitch_deg": 2.1,
  "timestamp": 1758450000.123,
}
```
