import smbus2, time

bus = smbus2.SMBus(1)

# Select CH0 (LEFT)
bus.write_byte(0x70, 1 << 0)
time.sleep(0.02)

print("\n=== TEST 1: ERM MODE (Library 1, Feedback 0x36) ===")
# 1. Reset
bus.write_byte_data(0x5A, 0x01, 0x00) # Internal trigger
bus.write_byte_data(0x5A, 0x1A, 0x36) # ERM mode (bit 7 = 0)
bus.write_byte_data(0x5A, 0x03, 0x01) # Library 1 (ERM standard)
# Fire Waveform 47 (Buzz 1 - 100%)
bus.write_byte_data(0x5A, 0x04, 47)
bus.write_byte_data(0x5A, 0x05, 0)
bus.write_byte_data(0x5A, 0x0C, 0x01) # GO
print("Fired Waveform 47 in ERM mode. Waiting 1.5s...")
time.sleep(1.5)

print("\n=== TEST 2: ERM CONTINUOUS RTP ===")
bus.write_byte_data(0x5A, 0x01, 0x05) # RTP mode
bus.write_byte_data(0x5A, 0x02, 0x7F) # 100% full DC drive
print("DRIVING 100% RTP FOR 2 SECONDS...")
time.sleep(2.0)
bus.write_byte_data(0x5A, 0x02, 0x00)
bus.write_byte_data(0x5A, 0x01, 0x00)
time.sleep(0.5)

print("\n=== TEST 3: LRA MODE (Library 6, Feedback 0xB6) ===")
bus.write_byte_data(0x5A, 0x1A, 0xB6) # LRA mode (bit 7 = 1)
bus.write_byte_data(0x5A, 0x03, 0x06) # Library 6
bus.write_byte_data(0x5A, 0x04, 1)    # Waveform 1 (Strong Click)
bus.write_byte_data(0x5A, 0x05, 0)
bus.write_byte_data(0x5A, 0x0C, 0x01) # GO
print("Fired Waveform 1 in LRA mode. Waiting 1s...")
time.sleep(1.0)

print("\n=== TEST 4: LRA CONTINUOUS RTP ===")
bus.write_byte_data(0x5A, 0x01, 0x05) # RTP mode
bus.write_byte_data(0x5A, 0x02, 0x7F) # 100% full AC drive
print("DRIVING 100% LRA RTP FOR 2 SECONDS...")
time.sleep(2.0)
bus.write_byte_data(0x5A, 0x02, 0x00)
bus.write_byte_data(0x5A, 0x01, 0x00)

bus.write_byte(0x70, 0x00)
print("\n=== TEST COMPLETED ===")

