#!/usr/bin/env python3
"""
Direct diagnostic for DRV2605L Haptic Driver Modules.
Tests:
1. Status register & chip detection
2. ERM mode (DC eccentric coin motor)
3. LRA mode (linear resonant actuator)
4. Real-Time Playback (RTP) direct voltage drive
"""

import smbus2
import time

MUX_ADDR = 0x70
DRV_ADDR = 0x5A

def select_channel(bus, ch):
    bus.write_byte(MUX_ADDR, 1 << ch)
    time.sleep(0.02)

def run_diagnostic():
    bus = smbus2.SMBus(1)
    print("=" * 60)
    print(" DRV2605L HAPTIC DRIVER DIAGNOSTIC & MOTOR TEST")
    print("=" * 60)

    for ch, name in [(0, "LEFT"), (1, "CENTER"), (2, "RIGHT")]:
        print(f"\n==================== Channel {ch}: {name} ====================")
        try:
            select_channel(bus, ch)
            # Read status register
            status = bus.read_byte_data(DRV_ADDR, 0x00)
            dev_id = (status >> 5) & 0x07
            diag_result = (status >> 3) & 0x01
            over_temp = (status >> 1) & 0x01
            over_curr = status & 0x01
            print(f"Status Byte: 0x{status:02X} (Device ID: {dev_id})")
            print(f"  Diagnostics bit: {'FAIL/In-progress' if diag_result else 'PASS'}")
            print(f"  Over-temp flag : {'YES (Warning)' if over_temp else 'NO'}")
            print(f"  Over-current   : {'YES (Fault)' if over_curr else 'NO'}")

            # Wake up from standby: Mode = 0x00 (Internal trigger)
            bus.write_byte_data(DRV_ADDR, 0x01, 0x00)
            time.sleep(0.01)

            # Test A: Real-Time Playback (RTP) at 100% full power drive (1.5 seconds)
            # This directly drives the H-bridge output to vibrate ANY motor connected (ERM or LRA)
            print("  >>> Firing 100% Full Power Real-Time Buzz for 1.5s...")
            bus.write_byte_data(DRV_ADDR, 0x01, 0x05)  # Mode: RTP (0x05)
            bus.write_byte_data(DRV_ADDR, 0x02, 0x7F)  # RTP: +127 (max power)
            time.sleep(1.5)
            bus.write_byte_data(DRV_ADDR, 0x02, 0x00)  # RTP: 0 (stop)
            bus.write_byte_data(DRV_ADDR, 0x01, 0x00)  # Mode: Int trigger

            # Test B: ERM ROM Library 1 (Waveform 1 - Strong Click 100%)
            print("  >>> Firing ERM ROM Waveform 1 (Strong Click)...")
            bus.write_byte_data(DRV_ADDR, 0x1A, 0x36)  # Bit 7 = 0 (ERM mode)
            bus.write_byte_data(DRV_ADDR, 0x03, 0x01)  # Library 1 (ERM)
            bus.write_byte_data(DRV_ADDR, 0x04, 0x01)  # Slot 1: waveform 1
            bus.write_byte_data(DRV_ADDR, 0x05, 0x00)  # Slot 2: stop
            bus.write_byte_data(DRV_ADDR, 0x0C, 0x01)  # GO bit = 1
            time.sleep(0.5)

            # Test C: LRA ROM Library 6 (Waveform 1 - Strong Click)
            print("  >>> Firing LRA ROM Waveform 1 (LRA Mode)...")
            bus.write_byte_data(DRV_ADDR, 0x1A, 0xB6)  # Bit 7 = 1 (LRA mode)
            bus.write_byte_data(DRV_ADDR, 0x03, 0x06)  # Library 6 (LRA)
            bus.write_byte_data(DRV_ADDR, 0x04, 0x01)  # Slot 1: waveform 1
            bus.write_byte_data(DRV_ADDR, 0x05, 0x00)  # Slot 2: stop
            bus.write_byte_data(DRV_ADDR, 0x0C, 0x01)  # GO bit = 1
            time.sleep(0.5)

            # Standby mode
            bus.write_byte_data(DRV_ADDR, 0x01, 0x40)
            print(f"Channel {ch} ({name}) test cycle complete.")

        except Exception as e:
            print(f"  ❌ Error on channel {ch}: {e}")

    bus.close()
    print("\n" + "=" * 60)
    print(" Diagnostic finished.")
    print("=" * 60)

if __name__ == "__main__":
    run_diagnostic()

