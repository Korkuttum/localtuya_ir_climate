# midea.py
"""Midea Climate IR Protocol."""
import logging
import math

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class MideaProtocol(ClimateIRProtocol):
    """
    Midea Klima IR Protokolü
    ESPHome climate_ir_midea.h/cpp referans alınarak yazılmıştır
    Coolix protokolü ile uyumludur
    """
    
    # Temperature ranges
    TEMPC_MIN = 17  # Celsius minimum
    TEMPC_MAX = 30  # Celsius maximum
    TEMPF_MIN = 62  # Fahrenheit minimum
    TEMPF_MAX = 86  # Fahrenheit maximum
    
    # Midea data types
    MIDEA_TYPE_CONTROL = 0x82
    MIDEA_TYPE_FOLLOW_ME = 0x83
    MIDEA_TYPE_SPECIAL = 0x84
    
    # Special command codes
    VSWING_STEP = 1     # Vertical swing step
    VSWING_TOGGLE = 2   # Vertical swing toggle
    TURBO_TOGGLE = 9    # Turbo mode toggle
    
    # Modes (byte 1, bits 0-2)
    MODE_COOL = 0
    MODE_DRY = 1
    MODE_AUTO = 2
    MODE_HEAT = 3
    MODE_FAN_ONLY = 4
    
    # Fan modes (byte 1, bits 3-4)
    FAN_AUTO = 0
    FAN_LOW = 1
    FAN_MEDIUM = 2
    FAN_HIGH = 3
    
    # IR timing (using Midea/Coolix protocol)
    # Midea uses standard 38kHz carrier with specific timing
    # These are typical values, actual encoding is done by MideaProtocol class
    BIT_MARK = 560
    ZERO_SPACE = 560
    ONE_SPACE = 1680
    HEADER_MARK = 4500
    HEADER_SPACE = 4500
    GAP_SPACE = 10000
    
    def __init__(self):
        super().__init__()
        
        # Midea supports swing and presets
        self.supported_swing_modes = ["off", "vertical"]
        self.supported_presets = ["none", "sleep", "boost"]
        
        # State tracking for swing and boost
        self.swing_pending = False
        self.boost_pending = False
        
        # Fahrenheit mode (default Celsius)
        self.fahrenheit_mode = False
        
        # Temperature step depends on unit
        self._temperature_step = 1.0  # Default Celsius
        
        _LOGGER.debug("Midea Protocol initialized")
    
    def set_fahrenheit(self, value):
        """Set Fahrenheit mode."""
        self.fahrenheit_mode = value
        self._temperature_step = 0.5 if value else 1.0
        _LOGGER.debug(f"Fahrenheit mode set to: {value}, temperature step: {self._temperature_step}")
    
    @property
    def temperature_step(self):
        """Return temperature step based on unit."""
        return self._temperature_step
    
    @property
    def temperature_min(self):
        return self.TEMPF_MIN if self.fahrenheit_mode else self.TEMPC_MIN
        
    @property 
    def temperature_max(self):
        return self.TEMPF_MAX if self.fahrenheit_mode else self.TEMPC_MAX

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Midea IR code for climate command."""
        _LOGGER.debug(f"Generating Midea IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}, fahrenheit={self.fahrenheit_mode}")
        
        # Check for swing toggle
        if swing_mode == "vertical" and not self.swing_pending:
            self.swing_pending = True
            _LOGGER.debug("Swing toggle requested")
            return self._generate_swing_toggle()
        
        # Check for boost preset toggle
        # Note: Boost is a preset in Midea, not handled in this method directly
        
        # Generate control command
        control_data = self._generate_control_data(hvac_mode, target_temp, fan_mode)
        
        # Convert to pulses using Midea encoding
        pulses = self._encode_midea_data(control_data)
        
        # Reset swing pending flag
        self.swing_pending = False
        
        return pulses
    
    def _generate_control_data(self, hvac_mode, target_temp, fan_mode):
        """Generate Midea control data (5 bytes)."""
        # Start with base control data
        data = [self.MIDEA_TYPE_CONTROL, 0x00, 0x00, 0xFF, 0xFF]
        
        # Byte 1: Power, Mode, Fan, and flags
        byte1 = 0
        
        # Power bit (bit 7)
        if hvac_mode != "off":
            byte1 |= 0x80  # Power ON
        
        # Mode bits (bits 0-2)
        mode_value = self._hvac_mode_to_midea(hvac_mode)
        byte1 |= mode_value
        
        # Fan mode bits (bits 3-4)
        fan_value = self._fan_mode_to_midea(fan_mode)
        byte1 |= (fan_value << 3)
        
        # Special flag bit 5 (needed for certain modes with AUTO fan)
        if fan_mode == "auto" and mode_value in [self.MODE_COOL, self.MODE_HEAT, self.MODE_FAN_ONLY]:
            byte1 |= 0x20  # Set bit 5
        
        data[1] = byte1
        
        # Byte 2: Temperature and Fahrenheit flag
        byte2 = 0
        
        # Temperature bits (bits 0-4)
        if self.fahrenheit_mode:
            # Convert to Fahrenheit and clamp
            temp_f = self._celsius_to_fahrenheit(target_temp)
            temp_f = max(self.TEMPF_MIN, min(self.TEMPF_MAX, temp_f))
            temp_val = int(round(temp_f)) - self.TEMPF_MIN
            # Set Fahrenheit flag (bit 5)
            byte2 |= 0x20
        else:
            # Celsius
            temp_c = max(self.TEMPC_MIN, min(self.TEMPC_MAX, target_temp))
            temp_val = int(round(temp_c)) - self.TEMPC_MIN
        
        byte2 |= temp_val
        
        # For FAN_ONLY mode, set all temperature bits
        if hvac_mode == "fan_only":
            byte2 |= 0x1F  # Set all 5 temperature bits
        
        data[2] = byte2
        
        # Bytes 3-4: Fixed values (0xFF)
        data[3] = 0xFF
        data[4] = 0xFF
        
        # Calculate checksum (XOR of all bytes)
        checksum = 0
        for byte in data:
            checksum ^= byte
        
        # Replace last byte with checksum
        data[4] = checksum
        
        _LOGGER.debug(f"Midea control data: {[f'0x{x:02X}' for x in data]}")
        return data
    
    def _generate_swing_toggle(self):
        """Generate swing toggle special command."""
        special_data = [self.MIDEA_TYPE_SPECIAL, self.VSWING_TOGGLE, 0xFF, 0xFF, 0xFF]
        
        # Calculate checksum
        checksum = 0
        for byte in special_data:
            checksum ^= byte
        special_data[4] = checksum
        
        _LOGGER.debug(f"Midea swing toggle: {[f'0x{x:02X}' for x in special_data]}")
        return self._encode_midea_data(special_data)
    
    def _generate_turbo_toggle(self):
        """Generate turbo toggle special command."""
        special_data = [self.MIDEA_TYPE_SPECIAL, self.TURBO_TOGGLE, 0xFF, 0xFF, 0xFF]
        
        # Calculate checksum
        checksum = 0
        for byte in special_data:
            checksum ^= byte
        special_data[4] = checksum
        
        _LOGGER.debug(f"Midea turbo toggle: {[f'0x{x:02X}' for x in special_data]}")
        return self._encode_midea_data(special_data)
    
    def _hvac_mode_to_midea(self, hvac_mode):
        """Convert HVAC mode to Midea mode value."""
        if hvac_mode == "cool":
            return self.MODE_COOL
        elif hvac_mode == "dry":
            return self.MODE_DRY
        elif hvac_mode == "heat":
            return self.MODE_HEAT
        elif hvac_mode == "fan_only":
            return self.MODE_FAN_ONLY
        else:  # auto or heat_cool
            return self.MODE_AUTO
    
    def _fan_mode_to_midea(self, fan_mode):
        """Convert fan mode to Midea fan value."""
        if fan_mode == "low":
            return self.FAN_LOW
        elif fan_mode == "medium":
            return self.FAN_MEDIUM
        elif fan_mode == "high":
            return self.FAN_HIGH
        else:  # auto
            return self.FAN_AUTO
    
    def _celsius_to_fahrenheit(self, celsius):
        """Convert Celsius to Fahrenheit."""
        return (celsius * 9/5) + 32
    
    def _fahrenheit_to_celsius(self, fahrenheit):
        """Convert Fahrenheit to Celsius."""
        return (fahrenheit - 32) * 5/9
    
    def _encode_midea_data(self, data):
        """
        Encode Midea data to pulse sequence.
        Midea uses a specific encoding similar to NEC but with 5 bytes.
        """
        pulses = []
        
        # Header
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        
        # Data bytes (LSB first for each byte)
        for byte in data:
            for bit in range(8):
                pulses.append(self.BIT_MARK)
                if byte & (1 << bit):  # LSB first
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Trailer
        pulses.append(self.BIT_MARK)
        
        return pulses
    
    def _encode_coolix_compatible(self, data):
        """
        Alternative encoding for Coolix compatibility.
        Midea devices can also understand Coolix protocol.
        """
        # This is a simplified version - actual Coolix encoding is more complex
        pulses = []
        
        # Coolix header
        pulses.extend([4500, 4500])  # Header mark/space
        
        # Data (34 bits total for Coolix)
        # Simplified implementation
        for byte in data:
            for i in range(8):
                pulses.append(560)  # Bit mark
                if byte & (1 << i):
                    pulses.append(1690)  # 1 space
                else:
                    pulses.append(560)   # 0 space
        
        pulses.append(560)  # Final mark
        
        return pulses