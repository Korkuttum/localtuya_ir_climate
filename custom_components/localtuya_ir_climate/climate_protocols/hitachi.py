# hitachi.py
"""Hitachi AC344 Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class HitachiProtocol(ClimateIRProtocol):
    """
    Hitachi AC344 Klima IR Protokolü
    ESPHome climate_ir_hitachi_ac344.h/cpp referans alınarak yazılmıştır
    43-byte frame yapısı
    """
    
    # Temperature range
    TEMP_MIN = 16
    TEMP_MAX = 32
    TEMP_FAN = 27  # Fan mode temperature
    
    # Byte positions
    POWER_BYTE = 27
    MODE_BYTE = 25
    TEMP_BYTE = 13
    FAN_BYTE = 25  # Same as MODE_BYTE (different bits)
    SWINGH_BYTE = 35
    SWINGV_BYTE = 37
    BUTTON_BYTE = 11
    
    # Power values
    POWER_ON = 0xF1
    POWER_OFF = 0xE1
    
    # Modes (lower 4 bits of MODE_BYTE)
    MODE_FAN = 1
    MODE_COOL = 3
    MODE_DRY = 5
    MODE_HEAT = 6
    MODE_AUTO = 7
    
    # Fan speeds (upper 4 bits of FAN_BYTE)
    FAN_MIN = 1
    FAN_LOW = 2
    FAN_MEDIUM = 3
    FAN_HIGH = 4
    FAN_AUTO = 5
    FAN_MAX = 6
    FAN_MAX_DRY = 2  # Dry mode max fan
    
    # Temperature bits
    TEMP_OFFSET = 2
    TEMP_SIZE = 6
    
    # Swing horizontal
    SWINGH_OFFSET = 0
    SWINGH_SIZE = 3
    SWINGH_AUTO = 0
    SWINGH_RIGHT_MAX = 1
    SWINGH_RIGHT = 2
    SWINGH_MIDDLE = 3
    SWINGH_LEFT = 4
    SWINGH_LEFT_MAX = 5
    
    # Swing vertical
    SWINGV_OFFSET = 5
    
    # Button values
    BUTTON_POWER = 0x13
    BUTTON_SLEEP = 0x31
    BUTTON_MODE = 0x41
    BUTTON_FAN = 0x42
    BUTTON_TEMP_DOWN = 0x43
    BUTTON_TEMP_UP = 0x44
    BUTTON_SWINGV = 0x81
    BUTTON_SWINGH = 0x8C
    
    # State length
    STATE_LENGTH = 43
    
    # IR timing parameters (microseconds)
    HDR_MARK = 3300
    HDR_SPACE = 1700
    BIT_MARK = 400
    ONE_SPACE = 1250
    ZERO_SPACE = 500
    MIN_GAP = 100000
    FREQ = 38000
    
    def __init__(self):
        super().__init__()
        
        # Hitachi supports horizontal swing
        self.supported_swing_modes = ["off", "horizontal", "vertical", "both"]
        self.supported_fan_modes = ["auto", "low", "medium", "high"]
        
        # Initialize remote state with default values
        self.remote_state = [
            0x01, 0x10, 0x00, 0x40, 0x00, 0xFF, 0x00, 0xCC, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00,
            0x80, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ]
        
        # Previous temperature tracking
        self.previous_temp = 27
        
        _LOGGER.debug("Hitachi AC344 Protocol initialized")
    
    def _set_bits(self, dst, offset, nbits, data):
        """Set nbits of data at offset in dst byte."""
        if offset >= 8 or nbits == 0:
            return
        
        # Calculate mask
        mask = (1 << nbits) - 1
        if nbits == 8:
            mask = 0xFF
        
        # Clear the bits
        dst[0] &= ~(mask << offset)
        # Set the bits
        dst[0] |= ((data & mask) << offset)
    
    def _set_bit(self, data, position, on):
        """Set a single bit in data byte."""
        if on:
            data[0] |= (1 << position)
        else:
            data[0] &= ~(1 << position)
    
    def _get_bits(self, data, offset, size):
        """Get bits from data byte."""
        mask = (1 << size) - 1
        if size == 8:
            mask = 0xFF
        return (data >> offset) & mask
    
    def _get_bit(self, data, position):
        """Get a single bit from data byte."""
        return (data >> position) & 1
    
    def _invert_byte_pairs(self, data, start, length):
        """Invert byte pairs (every second byte is inverse of previous)."""
        for i in range(start + 1, start + length, 2):
            data[i] = ~data[i - 1] & 0xFF
    
    def _set_power(self, on):
        """Set power state."""
        self.remote_state[self.BUTTON_BYTE] = self.BUTTON_POWER
        self.remote_state[self.POWER_BYTE] = self.POWER_ON if on else self.POWER_OFF
    
    def _set_mode(self, mode):
        """Set mode."""
        new_mode = mode
        
        # Handle special cases
        if mode == self.MODE_FAN:
            # Fan mode sets special temperature
            self._set_temp(self.TEMP_FAN, False)
        elif mode not in [self.MODE_HEAT, self.MODE_COOL, self.MODE_DRY]:
            new_mode = self.MODE_COOL  # Default to COOL
        
        # Set mode bits
        self._set_bits([self.remote_state[self.MODE_BYTE]], 0, 4, new_mode)
        
        # If not fan mode, restore previous temperature
        if new_mode != self.MODE_FAN:
            self._set_temp(self.previous_temp)
        
        # Reset fan after mode change
        self._set_fan(self._get_fan())
        
        # Power on
        self._set_power(True)
    
    def _set_temp(self, celsius, set_previous=True):
        """Set temperature."""
        temp_val = max(self.TEMP_MIN, min(self.TEMP_MAX, celsius))
        
        # Set temperature bits
        self._set_bits([self.remote_state[self.TEMP_BYTE]], self.TEMP_OFFSET, self.TEMP_SIZE, temp_val)
        
        # Set button based on temperature change
        if self.previous_temp > temp_val:
            self.remote_state[self.BUTTON_BYTE] = self.BUTTON_TEMP_DOWN
        elif self.previous_temp < temp_val:
            self.remote_state[self.BUTTON_BYTE] = self.BUTTON_TEMP_UP
        
        # Update previous temperature
        if set_previous:
            self.previous_temp = temp_val
    
    def _get_fan(self):
        """Get current fan speed."""
        return self._get_bits(self.remote_state[self.FAN_BYTE], 4, 4)
    
    def _set_fan(self, speed):
        """Set fan speed."""
        new_speed = max(speed, self.FAN_MIN)
        fan_max = self.FAN_MAX
        
        # Get current mode
        current_mode = self._get_bits(self.remote_state[self.MODE_BYTE], 0, 4)
        
        # Adjust max fan based on mode
        if current_mode == self.MODE_DRY and speed == self.FAN_AUTO:
            fan_max = self.FAN_AUTO
        elif current_mode == self.MODE_DRY:
            fan_max = self.FAN_MAX_DRY
        elif current_mode == self.MODE_FAN and speed == self.FAN_AUTO:
            # Fan mode doesn't have auto, set to min
            new_speed = self.FAN_MIN
        
        new_speed = min(new_speed, fan_max)
        
        # Set button if fan changed
        if new_speed != self._get_fan():
            self.remote_state[self.BUTTON_BYTE] = self.BUTTON_FAN
        
        # Set fan bits
        self._set_bits([self.remote_state[self.FAN_BYTE]], 4, 4, new_speed)
        
        # Set additional bytes based on fan speed
        if new_speed == self.FAN_MIN:
            self.remote_state[9] = 0x98
        else:
            self.remote_state[9] = 0x92
        
        self.remote_state[29] = 0x01
    
    def _set_swing_v(self, on):
        """Set vertical swing."""
        # Set button
        if on:
            self.remote_state[self.BUTTON_BYTE] = self.BUTTON_SWINGV
        
        # Set swing bit
        self._set_bit([self.remote_state[self.SWINGV_BYTE]], self.SWINGV_OFFSET, on)
    
    def _set_swing_h(self, position):
        """Set horizontal swing position."""
        if position > self.SWINGH_LEFT_MAX:
            position = self.SWINGH_MIDDLE
        
        self._set_bits([self.remote_state[self.SWINGH_BYTE]], self.SWINGH_OFFSET, self.SWINGH_SIZE, position)
        self.remote_state[self.BUTTON_BYTE] = self.BUTTON_SWINGH
    
    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Hitachi IR code for climate command."""
        _LOGGER.debug(f"Generating Hitachi IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        # Set mode
        if hvac_mode == "cool":
            self._set_mode(self.MODE_COOL)
        elif hvac_mode == "heat":
            self._set_mode(self.MODE_HEAT)
        elif hvac_mode == "dry":
            self._set_mode(self.MODE_DRY)
        elif hvac_mode == "fan_only":
            self._set_mode(self.MODE_FAN)
        elif hvac_mode in ["auto", "heat_cool"]:
            self._set_mode(self.MODE_AUTO)
        elif hvac_mode == "off":
            self._set_power(False)
        else:
            self._set_mode(self.MODE_COOL)
        
        # Set temperature if not OFF
        if hvac_mode != "off":
            self._set_temp(int(target_temp))
        
        # Set fan speed if not OFF
        if hvac_mode != "off":
            if fan_mode == "low":
                self._set_fan(self.FAN_LOW)
            elif fan_mode == "medium":
                self._set_fan(self.FAN_MEDIUM)
            elif fan_mode == "high":
                self._set_fan(self.FAN_HIGH)
            else:  # auto
                self._set_fan(self.FAN_AUTO)
        
        # Set swing
        if swing_mode == "both":
            self._set_swing_v(True)
            self._set_swing_h(self.SWINGH_AUTO)
        elif swing_mode == "vertical":
            self._set_swing_v(True)
            self._set_swing_h(self.SWINGH_MIDDLE)
        elif swing_mode == "horizontal":
            self._set_swing_v(False)
            self._set_swing_h(self.SWINGH_AUTO)
        else:  # off
            self._set_swing_v(False)
            self._set_swing_h(self.SWINGH_MIDDLE)
        
        # Set button to power (default)
        self.remote_state[self.BUTTON_BYTE] = self.BUTTON_POWER
        
        # Invert byte pairs (bytes 3 to end)
        self._invert_byte_pairs(self.remote_state, 3, self.STATE_LENGTH - 3)
        
        _LOGGER.debug(f"Hitachi remote state (first 10): {[f'0x{x:02X}' for x in self.remote_state[:10]]}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(self.remote_state)
        
        return pulses
    
    def _encode_to_pulses(self, remote_state):
        """Convert 43-byte array to IR pulse sequence (LSB first)."""
        pulses = []
        
        # Header
        pulses.extend([self.HDR_MARK, self.HDR_SPACE])
        
        # Data bytes (LSB FIRST)
        for byte in remote_state:
            for bit in range(8):  # 0 to 7, LSB first
                pulses.append(self.BIT_MARK)
                if byte & (1 << bit):  # Check bit from LSB to MSB
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Footer
        pulses.extend([self.BIT_MARK, self.MIN_GAP])
        
        return pulses