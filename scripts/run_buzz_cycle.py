import sys
sys.path.insert(0, '/home/pi/smart_glasses')
import time, smbus2, config

bus = smbus2.SMBus(1)

motors = [
    ("LEFT", config.PCA9548A_CHANNELS[config.MOTOR_LEFT]),
    ("CENTER", config.PCA9548A_CHANNELS[config.MOTOR_CENTER]),
    ("RIGHT", config.PCA9548A_CHANNELS[config.MOTOR_RIGHT])
]

print("=" * 60)
print(" 3-MOTOR CYCLE TEST (CH6 Left @ 0x5B, CH1 Center, CH2 Right)")
print("=" * 60)

for name, ch in motors:
    bus.write_byte(0x70, 1 << ch)
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
        print(f"\n❌ {name} (CH{ch}): No DRV chip detected at 0x5A or 0x5B!")
        continue

    print(f"\n--- Actuating {name} (CH{ch} @ 0x{addr:02X}) ---")

    # 1. Wake up from standby and configure LRA mode
    bus.write_byte_data(addr, 0x01, 0x00) # Internal trigger
    bus.write_byte_data(addr, 0x1A, 0xB6) # LRA mode
    bus.write_byte_data(addr, 0x03, 0x06) # Library 6 (LRA)

    # 2. Strong buzz via RTP (1.2 seconds)
    print(f"  >>> [1] Buzzing {name} for 1.2s (Continuous RTP)...", end="", flush=True)
    bus.write_byte_data(addr, 0x01, 0x05) # RTP mode
    bus.write_byte_data(addr, 0x02, 0x7F) # 100% full power
    time.sleep(1.2)
    bus.write_byte_data(addr, 0x02, 0x00) # Stop
    bus.write_byte_data(addr, 0x01, 0x00) # Internal trigger
    print(" [DONE]")
    time.sleep(0.4)

    # 3. Waveform click (Waveform 1 Strong Click)
    print(f"  >>> [2] Playing Waveform 1 on {name}...", end="", flush=True)
    bus.write_byte_data(addr, 0x04, 1)
    bus.write_byte_data(addr, 0x05, 0)
    bus.write_byte_data(addr, 0x0C, 0x01) # GO
    time.sleep(0.6)
    print(" [DONE]")

bus.write_byte(0x70, 0x00)
print("\n" + "=" * 60)
print(" ALL 3 MOTORS COMPLETED")
print("=" * 60)
