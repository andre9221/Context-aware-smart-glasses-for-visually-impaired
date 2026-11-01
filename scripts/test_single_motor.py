#!/usr/bin/env python3
"""
SmartElex DRV2605L Interactive Vibration Test
Tests ERM (coin disc) and LRA modes on all connected channels.
"""

import smbus2
import time
import sys

MUX_ADDR = 0x70
DRV_ADDR = 0x5A

def select_channel(bus, ch):
    bus.write_byte(MUX_ADDR, 1 << ch)
    time.sleep(0.02)

def test_motor(ch, name):
    bus = smbus2.SMBus(1)
    select_channel(bus, ch)
    print(f"\n=======================================================")
    print(f" TESTING MOTOR: Channel {ch} ({name})")
    print(f"=======================================================")

    # Read initial status
    try:
        status = bus.read_byte_data(DRV_ADDR, 0x00)
    except Exception as e:
        print(f"❌ Cannot communicate with DRV2605L on Channel {ch}: {e}")
        bus.close()
        return

    print(f"Initial Status Register: 0x{status:02X}")
    over_curr = status & 0x01
    over_temp = (status >> 1) & 0x01
    if over_curr:
        print("  ⚠️ Over-current flag is SET. (Checking wiring: motor wires must be on + and - pads only)")
    if over_temp:
        print("  ⚠️ Over-temperature flag is SET.")

    # Step 1: Wake up from standby
    bus.write_byte_data(DRV_ADDR, 0x01, 0x00)  # Internal trigger
    time.sleep(0.02)

    # Step 2: Try ERM Mode (DC coin motor, 3V-5V)
    print("\n[TEST 1] ERM Mode (Standard DC Coin / Disc Vibration Motor)...")
    bus.write_byte_data(DRV_ADDR, 0x1A, 0x36)  # Bit 7 = 0: ERM mode
    bus.write_byte_data(DRV_ADDR, 0x03, 0x01)  # Library 1 (ERM)
    bus.write_byte_data(DRV_ADDR, 0x04, 1)     # Waveform 1: Strong Click 100%
    bus.write_byte_data(DRV_ADDR, 0x05, 0)     # End
    bus.write_byte_data(DRV_ADDR, 0x0C, 1)     # GO = 1
    print("  Fired ERM Strong Click. Did you feel a click?")
    time.sleep(1.0)

    # Step 3: Try ERM Real-Time Continuous Vibration (2 seconds)
    print("\n[TEST 2] ERM Continuous Buzz (Real-Time Playback 2.0 seconds)...")
    bus.write_byte_data(DRV_ADDR, 0x01, 0x05)  # RTP Mode
    bus.write_byte_data(DRV_ADDR, 0x02, 0x7F)  # Full 100% power
    time.sleep(2.0)
    bus.write_byte_data(DRV_ADDR, 0x02, 0x00)  # Stop
    bus.write_byte_data(DRV_ADDR, 0x01, 0x00)  # Return to internal trigger
    print("  Did you feel a 2-second continuous vibration?")
    time.sleep(1.0)

    # Step 4: Try LRA Mode (Linear Resonant Actuator)
    print("\n[TEST 3] LRA Mode (Linear Resonant Actuator, Library 6)...")
    bus.write_byte_data(DRV_ADDR, 0x1A, 0xB6)  # Bit 7 = 1: LRA mode
    bus.write_byte_data(DRV_ADDR, 0x03, 0x06)  # Library 6 (LRA)
    bus.write_byte_data(DRV_ADDR, 0x04, 1)     # Waveform 1
    bus.write_byte_data(DRV_ADDR, 0x05, 0)
    bus.write_byte_data(DRV_ADDR, 0x0C, 1)     # GO = 1
    print("  Fired LRA Strong Click. Did you feel it?")
    time.sleep(1.0)

    # Check status at the end
    end_status = bus.read_byte_data(DRV_ADDR, 0x00)
    print(f"\nFinal Status Register: 0x{end_status:02X}")
    bus.close()

if __name__ == "__main__":
    ch = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    names = {0: "LEFT", 1: "CENTER", 2: "RIGHT"}
    test_motor(ch, names.get(ch, f"CH{ch}"))

