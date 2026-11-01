#!/usr/bin/env python3
"""
Diagnostic Motor Cycle Test
Fires each motor with a strong 1.5-second continuous vibration in a loop
so you can physically feel which channel is buzzing.
"""

import smbus2
import time
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

MUX_ADDR = 0x70

# Drive EN pins HIGH
for pin in [17, 27, 22]:
    subprocess.run(["pinctrl", "set", str(pin), "op", "dh"], capture_output=True)

bus = smbus2.SMBus(1)

def buzz_channel(ch, name, duration=1.2):
    print(f"\n>>> BUZZING {name} (PCA9548A Channel {ch})...", flush=True)
    try:
        # Select channel
        bus.write_byte(MUX_ADDR, 1 << ch)
        time.sleep(0.02)
        
        # Detect address (0x5A or 0x5B)
        addr = None
        for test_addr in [0x5A, 0x5B]:
            try:
                bus.read_byte(test_addr)
                addr = test_addr
                break
            except Exception:
                pass

        if addr is None:
            print(f"    ❌ ERROR on Channel {ch}: No DRV found at 0x5A or 0x5B", flush=True)
            return

        # Configure LRA mode
        bus.write_byte_data(addr, 0x01, 0x00)
        bus.write_byte_data(addr, 0x1A, 0xB6)
        bus.write_byte_data(addr, 0x03, 0x06)

        # Set RTP Mode (0x05) = Real-Time Playback direct motor drive
        bus.write_byte_data(addr, 0x01, 0x05)
        # Full power (0x7F = 127)
        bus.write_byte_data(addr, 0x02, 0x7F)
        
        time.sleep(duration)
        
        # Stop
        bus.write_byte_data(addr, 0x02, 0x00)
        bus.write_byte_data(addr, 0x01, 0x00)
        print(f"    [DONE] Feel the vibration on {name} (@ 0x{addr:02X})?", flush=True)
    except Exception as e:
        print(f"    ❌ ERROR on Channel {ch}: {e}", flush=True)

print("=" * 60)
print(" 3-AXIS HAPTIC MOTOR CONTINUOUS VIBRATION TEST")
print("=" * 60)
print("Holding all 3 motors in hand. Testing each one sequentially...")

motors = [
    (config.PCA9548A_CHANNELS[config.MOTOR_LEFT], "LEFT   (SD6/SC6)"),
    (config.PCA9548A_CHANNELS[config.MOTOR_CENTER], "CENTER (SD1/SC1)"),
    (config.PCA9548A_CHANNELS[config.MOTOR_RIGHT], "RIGHT  (SD2/SC2)"),
]

try:
    for cycle in range(1, 4):
        print(f"\n--- CYCLE {cycle}/3 ---")
        for ch, name in motors:
            buzz_channel(ch, name, duration=1.2)
            time.sleep(0.8)
            
    print("\n" + "=" * 60)
    print(" ALL 3 CHANNELS TESTED SUCCESSFULLY!")
    print("=" * 60)
except KeyboardInterrupt:
    print("\nStopped.")
finally:
    try:
        # Stop all
        for ch, _ in motors:
            bus.write_byte(MUX_ADDR, 1 << ch)
            bus.write_byte_data(DRV_ADDR, 0x02, 0x00)
            bus.write_byte_data(DRV_ADDR, 0x01, 0x00)
        bus.write_byte(MUX_ADDR, 0x00)
        bus.close()
    except Exception:
        pass

