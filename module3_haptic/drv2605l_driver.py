"""drv2605l_driver.py

Hardware driver for Texas Instruments DRV2605L Haptic Motor Driver
operating 3 Linear Resonant Actuators (LRAs) on Raspberry Pi 4.

Target: IEEE Sensors Journal (Module 3 Spatio-Tactile Haptics).
All register writes and masks are tagged # VERIFY vs datasheet.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

# Ensure config imports resolve from project root
try:
    import config
except ImportError:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    import config


class HapticDriverError(Exception):
    """Custom exception raised when an I2C communication or driver failure occurs."""
    pass


# Global hardware bus instance (initialized lazily)
_i2c_bus: Optional[Any] = None
_bus_override: Optional[Any] = None


def set_bus_override(bus: Any) -> None:
    """Inject a mock/fake SMBus object for unit testing."""
    global _bus_override, _i2c_bus
    _bus_override = bus
    _i2c_bus = bus


def reset_driver() -> None:
    """Reset driver state and injected bus for testing."""
    global _i2c_bus, _bus_override
    _i2c_bus = None
    _bus_override = None


def _get_bus(i2c_bus_num: int = 1) -> Any:
    """Acquire the I2C bus instance (smbus2 imported lazily)."""
    global _i2c_bus
    if _bus_override is not None:
        return _bus_override

    if _i2c_bus is None:
        try:
            import smbus2  # Lazy import inside driver functions, not at module top
            _i2c_bus = smbus2.SMBus(i2c_bus_num)
        except ImportError as e:
            raise HapticDriverError(
                "smbus2 is required for physical DRV2605L operation: "
                f"{e}"
            ) from e
        except (OSError, IOError) as e:
            raise HapticDriverError(
                f"Failed opening I2C bus {i2c_bus_num}: {e}"
            ) from e

    return _i2c_bus


def _select(motor: int) -> None:
    """Select the target LRA transducer (0=Left, 1=Center, 2=Right).

    # TODO: separate I2C buses vs TCA9548A mux, decision pending.
    # VERIFY vs hardware wiring
    """
    pass


def init(i2c_bus_num: int = 1) -> None:
    """Initialize DRV2605L into ROM Library 6 (LRA mode).

    Register sequence:
    1. Feedback Control Reg 0x1A: Set bit 7 (N_ERM_LRA = 1) for LRA # VERIFY vs datasheet
    2. Library Selection Reg 0x03: Set value 6 (LRA ROM library) # VERIFY vs datasheet
    3. Mode Reg 0x01: Set 0x00 (Internal Trigger mode) # VERIFY vs datasheet
    """
    bus = _get_bus(i2c_bus_num)

    for motor_idx in (
        config.MOTOR_INDEX_LEFT,
        config.MOTOR_INDEX_CENTER,
        config.MOTOR_INDEX_RIGHT,
    ):
        _select(motor_idx)
        try:
            # Reg 0x1A (Feedback control): Bit 7 = 1 (LRA mode: 0x80) # VERIFY vs datasheet
            bus.write_byte_data(
                config.DRV2605L_I2C_ADDR,
                config.REG_FEEDBACK_CTRL,
                config.FEEDBACK_LRA_BIT,  # 0x80 # VERIFY vs datasheet
            )

            # Reg 0x03 (Library selection): 6 = LRA library # VERIFY vs datasheet
            bus.write_byte_data(
                config.DRV2605L_I2C_ADDR,
                config.REG_LIBRARY_SEL,
                config.DRV2605L_LIBRARY,  # 0x06 # VERIFY vs datasheet
            )

            # Reg 0x01 (Mode): 0x00 = Internal trigger # VERIFY vs datasheet
            bus.write_byte_data(
                config.DRV2605L_I2C_ADDR,
                config.REG_MODE,
                config.MODE_INTERNAL_TRIGGER,  # 0x00 # VERIFY vs datasheet
            )
        except (OSError, IOError) as e:
            raise HapticDriverError(
                f"I2C error during DRV2605L init on motor {motor_idx}: {e}"
            ) from e


def fire(motor: int, effect_id: int, repeat_ms: int = 0) -> None:
    """Trigger a haptic waveform on the specified motor.

    Parameters:
        motor: Transducer index (0=Left, 1=Center, 2=Right).
        effect_id: DRV2605L ROM effect index (1 to 123).
        repeat_ms: Suggested repeat interval in ms.

    Register sequence:
    1. Route to motor via _select(motor).
    2. Waveform Slot 1 Reg 0x04: Set effect_id # VERIFY vs datasheet
    3. Waveform Slot 2 Reg 0x05: Set 0x00 (End of sequence) # VERIFY vs datasheet
    4. GO Reg 0x0C: Set bit 0 = 1 to fire waveform # VERIFY vs datasheet
    """
    bus = _get_bus()
    _select(motor)

    try:
        # Load waveform effect ID into slot 1 # VERIFY vs datasheet
        bus.write_byte_data(
            config.DRV2605L_I2C_ADDR,
            config.REG_WAVEFORM_SEQ_1,  # 0x04 # VERIFY vs datasheet
            effect_id,                  # # VERIFY vs datasheet
        )

        # Terminate waveform sequence in slot 2 (0x00 = end) # VERIFY vs datasheet
        bus.write_byte_data(
            config.DRV2605L_I2C_ADDR,
            0x05,                       # Slot 2 # VERIFY vs datasheet
            0x00,                       # End marker # VERIFY vs datasheet
        )

        # Fire GO register (0x0C = 0x01) # VERIFY vs datasheet
        bus.write_byte_data(
            config.DRV2605L_I2C_ADDR,
            config.REG_GO,              # 0x0C # VERIFY vs datasheet
            config.GO_FIRE,             # 0x01 # VERIFY vs datasheet
        )
    except (OSError, IOError) as e:
        raise HapticDriverError(
            f"I2C error during DRV2605L fire on motor {motor}: {e}"
        ) from e


def auto_calibrate(motor: int, i2c_bus_num: int = 1) -> None:
    """Run DRV2605L auto-calibration routine (mode 0x07).

    Untested on hardware; marked # VERIFY vs datasheet.
    Register sequence:
    1. Mode Reg 0x01: Set 0x07 (Auto-calibration mode) # VERIFY vs datasheet
    2. GO Reg 0x0C: Set 0x01 to initiate calibration # VERIFY vs datasheet
    """
    bus = _get_bus(i2c_bus_num)
    _select(motor)

    try:
        # Set Mode Reg 0x01 to 0x07 (Auto-calibration) # VERIFY vs datasheet
        bus.write_byte_data(
            config.DRV2605L_I2C_ADDR,
            config.REG_MODE,            # 0x01 # VERIFY vs datasheet
            0x07,                       # Mode 0x07 = Auto-calibration # VERIFY vs datasheet
        )

        # Trigger GO register # VERIFY vs datasheet
        bus.write_byte_data(
            config.DRV2605L_I2C_ADDR,
            config.REG_GO,              # 0x0C # VERIFY vs datasheet
            config.GO_FIRE,             # 0x01 # VERIFY vs datasheet
        )
    except (OSError, IOError) as e:
        raise HapticDriverError(
            f"I2C error during DRV2605L auto-calibration on motor {motor}: {e}"
        ) from e
