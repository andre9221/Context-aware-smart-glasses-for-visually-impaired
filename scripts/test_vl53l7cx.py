#!/usr/bin/env python3
"""
VL53L7CX 8x8 Grid Diagnostic — shows real distance per zone.
Run: python3 scripts/test_vl53l7cx.py
"""
import smbus2, time, subprocess, sys
import numpy as np
from vl53l5cx.vl53l5cx import VL53L5CX


class VL53L7CX(VL53L5CX):
    pass


def _chunked_wr(self, address, buffer, size):
    CHUNK_SIZE = 1024
    bytes_sent = 0
    addr = getattr(self, "address", getattr(self, "_i2c_address", 0x29))
    while bytes_sent < size:
        chunk_len = min(CHUNK_SIZE, size - bytes_sent)
        chunk_addr = address + bytes_sent
        chunk_data = buffer[bytes_sent : bytes_sent + chunk_len]
        payload = [(chunk_addr >> 8) & 0xff, chunk_addr & 0xff] + list(chunk_data)
        write = self.i2c_msg.write(addr, payload)
        for attempt in range(8):
            try:
                self._i2c_bus.i2c_rdwr(write)
                break
            except OSError:
                if attempt == 7:
                    raise
                time.sleep(0.005)
        bytes_sent += chunk_len


VL53L7CX.wr_multi = _chunked_wr

MIN_RANGE_MM = 50
MAX_RANGE_MM = 4000


def main():
    # Drive LPn HIGH to wake up the sensor
    subprocess.run(["pinctrl", "set", "24", "op", "dh"], capture_output=True)
    time.sleep(0.1)

    bus = smbus2.SMBus(1)
    tof = VL53L7CX(bus)
    tof.i2c_msg = smbus2.i2c_msg

    print("[1] Initializing VL53L7CX firmware...")
    tof.init()
    print("    >>> VL53L7CX READY! <<<")

    if hasattr(tof, "set_ranging_frequency_hz"):
        tof.set_ranging_frequency_hz(15)
    if hasattr(tof, "set_resolution"):
        tof.set_resolution(64)

    tof.start_ranging()
    print("\n" + "=" * 65)
    print(" >>> VL53L7CX ACTIVE! Wave hand 5cm-4m from sensor <<<")
    print("=" * 65 + "\n")

    # Give the sensor time to collect first frame
    time.sleep(0.5)

    try:
        for i in range(50):
            # Wait for data — retry up to 20 times (~2 seconds)
            ready = False
            for _ in range(20):
                try:
                    if hasattr(tof, "check_data_ready"):
                        ready = tof.check_data_ready()
                    elif hasattr(tof, "data_ready"):
                        ready = tof.data_ready()
                except Exception:
                    pass
                if ready:
                    break
                time.sleep(0.1)

            if not ready:
                print(f"#{i+1:02d} | (waiting for sensor...)")
                continue

            data = None
            for attempt in range(5):
                try:
                    data = tof.get_ranging_data()
                    break
                except Exception:
                    time.sleep(0.05)

            if data is None:
                print(f"#{i+1:02d} | (reading retry...)")
                continue

            dist = getattr(data, "distance_mm", data)
            arr = np.array(dist, dtype=np.float64).flatten()

            if len(arr) == 256:
                t_mat = arr.reshape((64, 4))
                valid_per_zone = np.where(t_mat > MIN_RANGE_MM, t_mat, np.inf)
                arr = np.min(valid_per_zone, axis=1)
                arr[np.isinf(arr)] = 0.0

            valid = arr[(arr > MIN_RANGE_MM) & (arr < MAX_RANGE_MM)]

            if len(valid) >= 3:
                median_cm = np.median(valid) / 10.0
                near_cm = np.percentile(valid, 10) / 10.0
                zones = len(valid)
                bar = "#" * int(max(1, min(20, median_cm / 20)))
                print(f"#{i+1:02d} | Median: {median_cm:.1f}cm | Near: {near_cm:.1f}cm | Zones: {zones:2d}/64 | [{bar:<20}]")
            else:
                print(f"#{i+1:02d} | Path Clear (no obstacle detected)")
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        try:
            tof.stop_ranging()
        except Exception:
            pass
        bus.close()
        print("\n>>> VL53L7CX Test Complete! <<<")


if __name__ == "__main__":
    main()

