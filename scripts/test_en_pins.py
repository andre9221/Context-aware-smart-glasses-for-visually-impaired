import smbus2
import time
import subprocess

# Drive GPIO 17, 27, 22 HIGH in case EN is wired to them
for pin in [17, 27, 22]:
    subprocess.run(["pinctrl", "set", str(pin), "op", "dh"], capture_output=True)
print("Drove GPIO 17, 27, 22 (EN pins) HIGH!")

bus = smbus2.SMBus(1)
MUX_ADDR = 0x70
DRV_ADDR = 0x5A

def select_ch(ch):
    bus.write_byte(MUX_ADDR, 1 << ch)
    time.sleep(0.02)

for ch in [0, 1, 2]:
    select_ch(ch)
    # Wake up
    bus.write_byte_data(DRV_ADDR, 0x01, 0x00)
    # Continuous RTP 100% drive for 1.5s
    print(f"Buzzing Channel {ch} at 100% power for 1.5s...")
    bus.write_byte_data(DRV_ADDR, 0x01, 0x05)
    bus.write_byte_data(DRV_ADDR, 0x02, 0x7F)
    time.sleep(1.5)
    bus.write_byte_data(DRV_ADDR, 0x02, 0x00)
    bus.write_byte_data(DRV_ADDR, 0x01, 0x40)

bus.close()
print("Done.")

