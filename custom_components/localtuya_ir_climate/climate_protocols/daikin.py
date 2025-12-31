# daikin.py
"""Daikin Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class DaikinProtocol(ClimateIRProtocol):
    """
    Daikin Klima IR Protokolü
    ESPHome climate_ir_daikin.h/cpp referans alınarak yazılmıştır
    """
    
    TEMP_MIN = 10
    TEMP_MAX = 30
    TEMP_STEP = 0.5  # Daikin yarım derece hassasiyetle çalışır
    
    # Modes
    DAIKIN_MODE_AUTO = 0x00
    DAIKIN_MODE_COOL = 0x30
    DAIKIN_MODE_HEAT = 0x40
    DAIKIN_MODE_DRY = 0x20
    DAIKIN_MODE_FAN = 0x60
    DAIKIN_MODE_OFF = 0x00
    DAIKIN_MODE_ON = 0x01
    
    # Fan Speed (upper byte of fan_speed)
    DAIKIN_FAN_AUTO = 0xA0
    DAIKIN_FAN_SILENT = 0xB0
    DAIKIN_FAN_1 = 0x30
    DAIKIN_FAN_2 = 0x40
    DAIKIN_FAN_3 = 0x50
    DAIKIN_FAN_4 = 0x60
    DAIKIN_FAN_5 = 0x70
    
    # Swing bits (lower byte of fan_speed)
    SWING_VERTICAL_BITS = 0x0F00  # Bits 8-11
    SWING_HORIZONTAL_BITS = 0x000F  # Bits 0-3
    
    # IR timing parameters (microseconds)
    IR_FREQUENCY = 38000
    HEADER_MARK = 3360
    HEADER_SPACE = 1760
    BIT_MARK = 520
    ONE_SPACE = 1370
    ZERO_SPACE = 360
    MESSAGE_SPACE = 32300
    
    # Frame structure
    STATE_FRAME_SIZE = 19  # For receiving
    
    def __init__(self):
        super().__init__()
        
        # Daikin supports both vertical and horizontal swing
        self.supported_swing_modes = [
            "off", "vertical", "horizontal", "both"
        ]
        
        # Daikin supports quiet mode
        self.supported_fan_modes = [
            "auto", "low", "medium", "high", "quiet"
        ]
        
        # State tracking
        self.swing_vertical = False
        self.swing_horizontal = False
        
        _LOGGER.debug("Daikin Protocol initialized")

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Daikin IR code for climate command."""
        _LOGGER.debug(f"Generating Daikin IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        # Initialize 35-byte remote state with default values
        remote_state = [
            0x11, 0xDA, 0x27, 0x00, 0xC5, 0x00, 0x00, 0xD7,  # Header + checksum?
            0x11, 0xDA, 0x27, 0x00, 0x42, 0x49, 0x05, 0xA2,  # More header
            0x11, 0xDA, 0x27, 0x00,  # Command header
            0x00,  # Byte 20: Start of actual data? 
            0x00,  # Byte 21: Operation mode (will be set)
            0x00,  # Byte 22: Temperature (will be set)
            0x00,  # Byte 23: Unknown
            0x00,  # Byte 24: Fan speed high byte (will be set)
            0x00,  # Byte 25: Fan speed low byte (will be set)
            0x00,  # Byte 26: Unknown
            0x00,  # Byte 27: Unknown
            0x00,  # Byte 28: Unknown
            0x00,  # Byte 29: Unknown
            0x06,  # Byte 30: Constant?
            0x60,  # Byte 31: Constant?
            0x00,  # Byte 32: Constant?
            0x00,  # Byte 33: Constant?
            0xC0,  # Byte 34: Constant?
            0x00,  # Byte 35: Constant?
            0x00,  # Byte 36: Constant?
            0x00,  # Byte 37: Checksum (will be calculated)
        ]
        
        # Byte 21: Operation mode
        remote_state[21] = self._operation_mode(hvac_mode)
        
        # Byte 22: Temperature (special handling for some modes)
        remote_state[22] = self._temperature_value(hvac_mode, target_temp)
        
        # Bytes 24-25: Fan speed (16-bit value)
        fan_speed_value = self._fan_speed_value(fan_mode, swing_mode)
        remote_state[24] = (fan_speed_value >> 8) & 0xFF  # High byte
        remote_state[25] = fan_speed_value & 0xFF         # Low byte
        
        # Calculate checksum for bytes 16-34 (index 16 to 34 inclusive)
        checksum = 0
        for i in range(16, 35):  # 16 to 34 inclusive
            checksum = (checksum + remote_state[i]) & 0xFF
        remote_state[35] = checksum
        
        _LOGGER.debug(f"Daikin remote state (first 8): {[f'0x{x:02X}' for x in remote_state[:8]]}")
        _LOGGER.debug(f"Daikin remote state (bytes 16-36): {[f'0x{x:02X}' for x in remote_state[16:]]}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(remote_state)
        _LOGGER.debug(f"Generated {len(pulses)} pulses")
        
        return pulses

    def _operation_mode(self, hvac_mode):
        """Convert HVAC mode to Daikin operation mode byte."""
        operation_mode = self.DAIKIN_MODE_ON
        
        if hvac_mode == "off":
            return self.DAIKIN_MODE_OFF
        elif hvac_mode == "cool":
            operation_mode |= self.DAIKIN_MODE_COOL
        elif hvac_mode == "heat":
            operation_mode |= self.DAIKIN_MODE_HEAT
        elif hvac_mode == "dry":
            operation_mode |= self.DAIKIN_MODE_DRY
        elif hvac_mode in ["auto", "heat_cool"]:
            operation_mode |= self.DAIKIN_MODE_AUTO
        elif hvac_mode == "fan_only":
            operation_mode |= self.DAIKIN_MODE_FAN
        else:
            operation_mode |= self.DAIKIN_MODE_AUTO
        
        return operation_mode

    def _temperature_value(self, hvac_mode, target_temp):
        """Convert temperature to Daikin temperature byte."""
        # Special temperatures for certain modes
        if hvac_mode == "fan_only":
            return 0x32  # Fixed value for fan mode
        elif hvac_mode == "dry":
            return 0xC0  # Fixed value for dry mode
        else:
            # Normal temperature: (temp * 2) as byte
            temp_val = max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp))
            return int(temp_val * 2)

    def _fan_speed_value(self, fan_mode, swing_mode):
        """Create 16-bit fan speed value with swing bits."""
        # Upper byte: Fan speed
        fan_speed = 0
        if fan_mode == "quiet":
            fan_speed = self.DAIKIN_FAN_SILENT << 8
        elif fan_mode == "low":
            fan_speed = self.DAIKIN_FAN_1 << 8
        elif fan_mode == "medium":
            fan_speed = self.DAIKIN_FAN_3 << 8
        elif fan_mode == "high":
            fan_speed = self.DAIKIN_FAN_5 << 8
        else:  # auto or unknown
            fan_speed = self.DAIKIN_FAN_AUTO << 8
        
        # Lower byte: Swing bits
        swing_bits = 0
        if swing_mode == "vertical":
            swing_bits = 0x0F  # Vertical swing enabled
        elif swing_mode == "horizontal":
            swing_bits = 0xF0  # Actually horizontal is in low byte bits 0-3
            swing_bits = 0x0F  # Correcting - horizontal is in low byte
        elif swing_mode == "both":
            swing_bits = 0xFF  # Both swings enabled
        
        # Combine: fan speed in high byte, swing in low byte
        # Actually from the C++ code: fan_speed is 16-bit with swing in both bytes
        # Let me re-examine the C++ code...
        
        # Looking at the C++ code:
        # fan_speed = DAIKIN_FAN_X << 8  (fan in high byte)
        # Then OR with swing bits:
        # vertical: 0x0F00 (bits 8-11)
        # horizontal: 0x000F (bits 0-3)
        # both: 0x0F0F
        
        fan_byte = 0
        if fan_mode == "quiet":
            fan_byte = self.DAIKIN_FAN_SILENT
        elif fan_mode == "low":
            fan_byte = self.DAIKIN_FAN_1
        elif fan_mode == "medium":
            fan_byte = self.DAIKIN_FAN_3
        elif fan_mode == "high":
            fan_byte = self.DAIKIN_FAN_5
        else:  # auto
            fan_byte = self.DAIKIN_FAN_AUTO
        
        result = fan_byte << 8  # Fan in high byte
        
        # Add swing bits
        if swing_mode == "vertical":
            result |= 0x0F00  # Set bits 8-11
        elif swing_mode == "horizontal":
            result |= 0x000F  # Set bits 0-3
        elif swing_mode == "both":
            result |= 0x0F0F  # Set bits 0-3 and 8-11
        
        return result

    def _encode_to_pulses(self, remote_state):
        """Convert 35-byte array to IR pulse sequence."""
        pulses = []
        
        # Daikin sends data in 3 blocks with headers
        
        # Block 1: Bytes 0-7
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        for byte in remote_state[0:8]:
            for mask in [1, 2, 4, 8, 16, 32, 64, 128]:  # MSB first
                pulses.append(self.BIT_MARK)
                if byte & mask:
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        pulses.append(self.BIT_MARK)
        pulses.append(self.MESSAGE_SPACE)
        
        # Block 2: Bytes 8-15
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        for byte in remote_state[8:16]:
            for mask in [1, 2, 4, 8, 16, 32, 64, 128]:  # MSB first
                pulses.append(self.BIT_MARK)
                if byte & mask:
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        pulses.append(self.BIT_MARK)
        pulses.append(self.MESSAGE_SPACE)
        
        # Block 3: Bytes 16-35
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        for byte in remote_state[16:35]:
            for mask in [1, 2, 4, 8, 16, 32, 64, 128]:  # MSB first
                pulses.append(self.BIT_MARK)
                if byte & mask:
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        pulses.append(self.BIT_MARK)
        
        return pulses