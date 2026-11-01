import smbus2
import time

bus = smbus2.SMBus(1)
MUX_ADDR = 0x70
DRV_ADDR = 0x5A

def select_ch(ch):
    bus.write_byte(MUX_ADDR, 1 << ch)
    time.sleep(0.02)

print("Clearing faults and running auto-calibration...")

for ch in [0, 1, 2]:
    select_ch(ch)
    # Read status to clear sticky flags
    s = bus.read_byte_data(DRV_ADDR, 0x00)
    # Soft reset
    bus.write_byte_data(DRV_ADDR, 0x01, 0x80)
    time.sleep(0.05)
    # Read status after reset
    s_after = bus.read_byte_data(DRV_ADDR, 0x00)
    print(f"Channel {ch}: before=0x{s:02X}, after_reset=0x{s_after:02X}")

bus.close()

