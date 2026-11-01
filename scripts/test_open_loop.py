import smbus2, time

bus = smbus2.SMBus(1)

print("=== TESTING OPEN-LOOP LRA DRIVE ON CH0 ===")
bus.write_byte(0x70, 1 << 0)
time.sleep(0.02)

# 1. Wake up
bus.write_byte_data(0x5A, 0x01, 0x00) # Internal trigger
time.sleep(0.01)

# 2. Select LRA mode
bus.write_byte_data(0x5A, 0x1A, 0xB6) # LRA mode

# 3. SET LRA_OPEN_LOOP = 1 (Bit 0 of Reg 0x1D)
# Reg 0x1D: 0xA1 (PWM_NG=2%, ERM_OPEN_LOOP=1, LRA_OPEN_LOOP=1)
bus.write_byte_data(0x5A, 0x1D, 0xA1)
print("Reg 0x1D set to 0xA1 (LRA Open-Loop ENABLED)")

# 4. Set LRA drive period in Reg 0x20
# Typical LRA is 205 Hz -> period = 1 / (205 * 98.46e-6) = 49.5 -> 0x32
# If 175 Hz -> 0x3A
# If 267 Hz -> 0x26
for freq_name, period_val in [("205 Hz", 0x32), ("267 Hz", 0x26), ("175 Hz", 0x3A)]:
    print(f"\nDriving Open-Loop at {freq_name} (period=0x{period_val:02X}) for 2.0s...")
    bus.write_byte_data(0x5A, 0x20, period_val) # Drive period
    bus.write_byte_data(0x5A, 0x01, 0x05)       # RTP mode
    bus.write_byte_data(0x5A, 0x02, 0x7F)       # 100% full magnitude
    time.sleep(2.0)
    bus.write_byte_data(0x5A, 0x02, 0x00)       # Stop
    bus.write_byte_data(0x5A, 0x01, 0x00)       # Internal trigger
    time.sleep(0.5)

bus.write_byte(0x70, 0x00)
print("\n=== OPEN-LOOP TEST COMPLETE ===")

