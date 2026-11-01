"""
TI DRV2605L Haptic Motor Driver with PCA9548A Multiplexer Support
Lead Researcher: Tejaswi E. (24BCE5518)

Interfaces with 3× TI DRV2605L haptic drivers (Left, Center, Right LRAs)
via PCA9548A I2C Multiplexer (Address 0x70) on Raspberry Pi 5 / 4.
Loads waveform sequences from ROM library and fires directional pulses.
"""

import time
from typing import Optional, Dict
from config import (
    DRV2605L_I2C_ADDR,
    PCA9548A_I2C_ADDR,
    PCA9548A_CHANNELS,
    I2C_BUS_ID,
    MOTOR_LEFT,
    MOTOR_CENTER,
    MOTOR_RIGHT,
    GPIO_LRA_LEFT,
    GPIO_LRA_CENTER,
    GPIO_LRA_RIGHT,
)


class DRV2605LDriver:
    """I2C driver for TI DRV2605L haptic driver IC via PCA9548A multiplexer."""

    # Registers
    REG_STATUS = 0x00
    REG_MODE = 0x01
    REG_RTPIN = 0x02
    REG_LIBRARY = 0x03
    REG_WAVESEQ1 = 0x04
    REG_WAVESEQ2 = 0x05
    REG_GO = 0x0C
    REG_FEEDBACK = 0x1A
    REG_CONTROL3 = 0x1D

    # Mode values
    MODE_INTTRIG = 0x00
    MODE_STANDBY = 0x40

    def __init__(
        self,
        i2c_bus: int = I2C_BUS_ID,
        address: int = DRV2605L_I2C_ADDR,
        mux_address: int = PCA9548A_I2C_ADDR,
        channel_map: Optional[Dict[str, int]] = None,
        force_hardware: bool = False,
    ):
        self.bus_id = i2c_bus
        self.address = address
        self.mux_address = mux_address
        self.channel_map = channel_map or PCA9548A_CHANNELS
        self.channel_addresses = {}
        self.is_connected = False
        self.has_mux = False
        self.bus = None
        self.gpio = None
        self.trigger_pins = {
            MOTOR_LEFT: GPIO_LRA_LEFT,
            MOTOR_CENTER: GPIO_LRA_CENTER,
            MOTOR_RIGHT: GPIO_LRA_RIGHT,
        }

        self._init_hardware()

    def _select_mux_channel(self, channel: int):
        """Switch PCA9548A multiplexer to specified sub-bus channel (0 to 7)."""
        if self.bus is not None:
            try:
                # Bitmask: Channel 0 -> 0x01, Channel 1 -> 0x02, Channel 2 -> 0x04, etc.
                self.bus.write_byte(self.mux_address, 1 << channel)
            except Exception as e:
                pass

    def _init_hardware(self):
        """Configure PCA9548A and DRV2605L drivers for LRA operation and ROM library 6."""
        try:
            import smbus2
            self.bus = smbus2.SMBus(self.bus_id)

            # Drive EN (Enable) pins HIGH to wake DRV2605L boards from hardware shutdown
            import subprocess
            for pin in self.trigger_pins.values():
                subprocess.run(["pinctrl", "set", str(pin), "op", "dh"], capture_output=True)
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                for pin in self.trigger_pins.values():
                    GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
                    GPIO.output(pin, GPIO.HIGH)
                self.gpio = GPIO
            except Exception as gpio_error:
                pass

            # Probe PCA9548A multiplexer
            try:
                self.bus.read_byte(self.mux_address)
                self.has_mux = True
                print(f"[PCA9548A] Detected I2C multiplexer at address 0x{self.mux_address:02X}")
            except Exception:
                self.has_mux = False

            initialized_count = 0
            channels = self.channel_map.items() if self.has_mux else [(MOTOR_CENTER, None)]

            for motor_name, ch in channels:
                if ch is not None:
                    self._select_mux_channel(ch)
                # Auto-detect address: try 0x5A, then 0x5B
                dev_addr = None
                for test_addr in [0x5A, 0x5B]:
                    try:
                        self.bus.read_byte(test_addr)
                        dev_addr = test_addr
                        break
                    except Exception:
                        pass

                if dev_addr is not None:
                    self.channel_addresses[motor_name] = dev_addr
                    try:
                        # Set mode to internal trigger
                        self.bus.write_byte_data(dev_addr, self.REG_MODE, self.MODE_INTTRIG)
                        from config import HAPTIC_MOTOR_TYPE
                        if HAPTIC_MOTOR_TYPE == "LRA":
                            self.bus.write_byte_data(dev_addr, self.REG_LIBRARY, 0x06)  # Library 6 (LRA)
                            self.bus.write_byte_data(dev_addr, self.REG_FEEDBACK, 0xB6) # Bit 7=1 (LRA mode)
                        else:
                            self.bus.write_byte_data(dev_addr, self.REG_LIBRARY, 0x01)  # Library 1 (ERM standard)
                            self.bus.write_byte_data(dev_addr, self.REG_FEEDBACK, 0x36) # Bit 7=0 (ERM mode)
                        initialized_count += 1
                    except Exception:
                        pass

            if initialized_count > 0:
                self.is_connected = True
                print(f"[DRV2605L] Successfully initialized {initialized_count} haptic driver(s) (Left/Center/Right)!")
            else:
                self.is_connected = False
                print("[DRV2605L] No DRV2605L responded behind multiplexer.")
        except Exception as e:
            print(f"[DRV2605L] Hardware init warning ({e}).")
            self.is_connected = False

    def trigger_waveform(self, motor_channel: str, waveform_id: int):
        """
        Loads specified ROM waveform into slot 1 and sets GO bit.
        Routes actuation to specified channel (LEFT, CENTER, RIGHT) via PCA9548A.
        """
        if self.is_connected and self.bus is not None:
            try:
                if self.has_mux and motor_channel in self.channel_map:
                    self._select_mux_channel(self.channel_map[motor_channel])

                addr = self.channel_addresses.get(motor_channel, self.address)

                # Ensure chip is out of standby (internal trigger mode)
                self.bus.write_byte_data(addr, self.REG_MODE, self.MODE_INTTRIG)
                from config import HAPTIC_MOTOR_TYPE
                if HAPTIC_MOTOR_TYPE == "LRA":
                    self.bus.write_byte_data(addr, self.REG_LIBRARY, 0x06)
                    self.bus.write_byte_data(addr, self.REG_FEEDBACK, 0xB6)
                else:
                    self.bus.write_byte_data(addr, self.REG_LIBRARY, 0x01)
                    self.bus.write_byte_data(addr, self.REG_FEEDBACK, 0x36)
                # Slot 1: target waveform (fallback to 1 if None)
                wf = int(waveform_id) if waveform_id else 1
                self.bus.write_byte_data(addr, self.REG_WAVESEQ1, wf & 0x7F)
                # Slot 2: 0x00 to terminate sequence
                self.bus.write_byte_data(addr, self.REG_WAVESEQ2, 0x00)
                # Set GO bit (0x01)
                self.bus.write_byte_data(addr, self.REG_GO, 0x01)
                return True
            except Exception as e:
                print(f"[DRV2605L] I2C write error on channel {motor_channel}: {e}")
                return False

        # Hardware not connected — cannot actuate
        return False

    def stop(self):
        """Place all active drivers into standby."""
        if self.is_connected and self.bus is not None:
            try:
                if self.has_mux:
                    for motor_name, ch in self.channel_map.items():
                        self._select_mux_channel(ch)
                        addr = self.channel_addresses.get(motor_name, self.address)
                        self.bus.write_byte_data(addr, self.REG_MODE, self.MODE_STANDBY)
                else:
                    self.bus.write_byte_data(self.address, self.REG_MODE, self.MODE_STANDBY)
            except Exception:
                pass

    def close(self):
        self.stop()
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
            self.bus = None
        if self.gpio is not None:
            try:
                self.gpio.cleanup(list(self.trigger_pins.values()))
            except Exception:
                pass
            self.gpio = None

