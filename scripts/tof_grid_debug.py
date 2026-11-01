#!/usr/bin/env python3
"""Quick 8x8 grid diagnostic - shows what every zone reads in CM."""
import sys, time
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
import config
from module1_sensor.tof_driver import VL53L7CXDriver

tof = VL53L7CXDriver(force_hardware=True)
if not tof.is_connected:
    print("VL53L7CX not connected!")
    sys.exit(1)

print("\nHold an object at different distances. Ctrl+C to stop.\n")
try:
    while True:
        m = tof.read_distance_matrix()
        cm = m * 100.0  # convert meters -> cm

        print("\033[2J\033[H")  # clear screen
        print("=== VL53L7CX 8x8 DEPTH GRID (cm) — LEFT col 0, RIGHT col 7 ===\n")
        print("     C0      C1      C2      C3      C4      C5      C6      C7")
        for row in range(8):
            vals = []
            for col in range(8):
                v = cm[row, col]
                if v >= 400.0 or v <= 0:
                    vals.append(" ---- ")
                elif v < 30:
                    vals.append(f"\033[91m{v:5.1f}!\033[0m")  # red  = very close < 30cm
                elif v < 100:
                    vals.append(f"\033[93m{v:5.1f} \033[0m")  # yellow = 30-100cm
                else:
                    vals.append(f"\033[92m{v:5.1f} \033[0m")  # green  = > 100cm
            print(f"R{row}  " + "  ".join(vals))

        valid = ((cm > 5) & (cm < 400)).sum()
        min_valid = cm[(cm > 5) & (cm < 400)]
        min_cm = min_valid.min() if len(min_valid) > 0 else 0
        center_cm = cm[3:5, 3:5].mean()

        print(f"\nNearest zone : {min_cm:.1f} cm")
        print(f"Center avg   : {center_cm:.1f} cm")
        print(f"Valid zones  : {valid}/64")
        print("\n[RED < 30cm] [YELLOW 30-100cm] [GREEN > 100cm] [---- out of range]")
        time.sleep(0.3)
except KeyboardInterrupt:
    tof.close()
    print("\nDone.")

