import smbus2, time
bus = smbus2.SMBus(1)

reg_names = {
    0x00: "STATUS",
    0x01: "MODE",
    0x02: "RTP_INPUT",
    0x03: "LIBRARY",
    0x04: "WAV_SEQ1",
    0x05: "WAV_SEQ2",
    0x0C: "GO",
    0x0D: "OD_OFFSET",
    0x0E: "SU_OFFSET",
    0x0F: "BT_OFFSET",
    0x10: "BRK_TIME",
    0x16: "RATED_VOLT",
    0x17: "OD_CLAMP",
    0x18: "AUTO_CAL_COMP",
    0x19: "AUTO_CAL_BEMF",
    0x1A: "FEEDBACK_CTRL",
    0x1B: "CONTROL1",
    0x1C: "CONTROL2",
    0x1D: "CONTROL3",
    0x1E: "CONTROL4",
    0x1F: "CONTROL5",
    0x20: "LRA_LOOP_PER",
    0x21: "VBAT_VOLT",
    0x22: "LRA_RESONANCE"
}

for ch, name in [(0, "LEFT (CH0)"), (1, "CENTER (CH1)"), (2, "RIGHT (CH2)")]:
    print("\n================== " + name + " ==================")
    bus.write_byte(0x70, 1 << ch)
    time.sleep(0.02)
    for reg, rname in sorted(reg_names.items()):
        try:
            val = bus.read_byte_data(0x5A, reg)
            print("  0x{:02X} ({:15s}): 0x{:02X} (bin: {:08b})".format(reg, rname, val, val))
        except Exception as e:
            print("  0x{:02X} ({:15s}): ERROR {}".format(reg, rname, e))

bus.write_byte(0x70, 0x00)

