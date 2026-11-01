import smbus2, time

bus = smbus2.SMBus(1)

for ch, name in [(0, "LEFT (CH0)"), (1, "CENTER (CH1)")]:
    print(f"\n================ Testing {name} ================")
    bus.write_byte(0x70, 1 << ch)
    time.sleep(0.02)
    
    # Configure
    bus.write_byte_data(0x5A, 0x01, 0x00) # Internal trigger
    bus.write_byte_data(0x5A, 0x1A, 0xB6) # LRA mode
    bus.write_byte_data(0x5A, 0x03, 0x06) # Library 6
    bus.write_byte_data(0x5A, 0x04, 47)   # Waveform 47 (Buzz 1 - 100%)
    bus.write_byte_data(0x5A, 0x05, 0)
    
    # Start playback
    bus.write_byte_data(0x5A, 0x0C, 0x01) # GO
    
    # Monitor for 800ms
    t_start = time.time()
    readings = []
    while time.time() - t_start < 0.8:
        try:
            go = bus.read_byte_data(0x5A, 0x0C)
            status = bus.read_byte_data(0x5A, 0x00)
            vbat_raw = bus.read_byte_data(0x5A, 0x21)
            vbat_v = vbat_raw * 5.6 / 255.0
            readings.append((round((time.time() - t_start)*1000), go, hex(status), round(vbat_v, 2)))
        except Exception as e:
            readings.append((round((time.time() - t_start)*1000), "ERR", str(e), 0))
        time.sleep(0.04)
        
    print(f"Sample readings (ms, GO, STATUS, VBAT):")
    for r in readings[:10]:
        print(f"  {r[0]:4d}ms: GO={r[1]}, STATUS={r[2]}, VBAT={r[3]}V")

bus.write_byte(0x70, 0x00)

