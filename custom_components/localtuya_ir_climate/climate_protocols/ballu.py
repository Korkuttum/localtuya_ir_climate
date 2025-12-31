# ballu.py
"""Ballu Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class BalluProtocol(ClimateIRProtocol):
    """
    Ballu Klima IR Protokolü (YKR-K/002E remote)
    ESPHome climate_ir_ballu.h/cpp referans alınarak yazılmıştır
    """
    
    # Temperature range
    TEMP_MIN = 16.0
    TEMP_MAX = 32.0
    
    # State length
    STATE_LENGTH = 13
    
    # Modes (byte 6, bits 5-7)
    MODE_AUTO = 0x00
    MODE_COOL = 0x20
    MODE_DRY = 0x40
    MODE_HEAT = 0x80
    MODE_FAN = 0xC0
    
    # Fan speeds (byte 4, bits 5-7)
    FAN_AUTO = 0xA0
    FAN_HIGH = 0x20
    FAN_MED = 0x40
    FAN_LOW = 0x60
    
    # Swing masks
    SWING_VER = 0x07  # Vertical swing mask (byte 1, bits 0-2)
    SWING_HOR = 0xE0  # Horizontal swing mask (byte 2, bits 5-7)
    
    # Power mask
    POWER_MASK = 0x20  # Power mask (byte 9, bit 5)
    
    # Fixed bytes
    FIXED_BYTE0 = 0xC3
    FIXED_BYTE11 = 0x1E
    
    # IR timing parameters (microseconds)
    HEADER_MARK = 9000
    HEADER_SPACE = 4500
    BIT_MARK = 575
    ONE_SPACE = 1675
    ZERO_SPACE = 550
    CARRIER_FREQUENCY = 38000
    
    def __init__(self):
        super().__init__()
        
        # Ballu supports both vertical and horizontal swing
        self.supported_swing_modes = ["off", "vertical", "horizontal", "both"]
        self.supported_fan_modes = ["auto", "low", "medium", "high"]
        
        _LOGGER.debug("Ballu Protocol initialized")
    
    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Ballu IR code for climate command."""
        _LOGGER.debug(f"Generating Ballu IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        remote_state = [0] * self.STATE_LENGTH
        
        # Clamp temperature
        temp_val = max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp))
        temp_int = int(round(temp_val))
        
        # Determine swing states
        swing_ver = swing_mode in ["vertical", "both"]
        swing_hor = swing_mode in ["horizontal", "both"]
        
        # Byte 0: Fixed header
        remote_state[0] = self.FIXED_BYTE0
        
        # Byte 1: Temperature and vertical swing
        # Temperature: (temp - 8) << 3
        temp_bits = ((temp_int - 8) << 3) & 0xF8
        # Vertical swing: 0x07 when swing is OFF, 0x00 when swing is ON
        ver_swing_bits = 0x00 if swing_ver else self.SWING_VER
        remote_state[1] = temp_bits | ver_swing_bits
        
        # Byte 2: Horizontal swing
        # Horizontal swing: 0xE0 when swing is OFF, 0x00 when swing is ON
        hor_swing_bits = 0x00 if swing_hor else self.SWING_HOR
        remote_state[2] = hor_swing_bits
        
        # Byte 4: Fan speed
        fan_value = self._fan_mode_to_ballu(fan_mode)
        remote_state[4] = fan_value
        
        # Byte 6: Mode
        mode_value = self._hvac_mode_to_ballu(hvac_mode)
        remote_state[6] = mode_value
        
        # Byte 9: Power
        if hvac_mode != "off":
            remote_state[9] = self.POWER_MASK
        
        # Byte 11: Fixed value
        remote_state[11] = self.FIXED_BYTE11
        
        # Calculate checksum (sum of first 12 bytes)
        checksum = 0
        for i in range(self.STATE_LENGTH - 1):
            checksum += remote_state[i]
        remote_state[12] = checksum & 0xFF
        
        _LOGGER.debug(f"Ballu remote state: {[f'0x{x:02X}' for x in remote_state]}")
        
        # Convert to pulse sequence (LSB first)
        pulses = self._encode_to_pulses(remote_state)
        
        return pulses
    
    def _hvac_mode_to_ballu(self, hvac_mode):
        """Convert HVAC mode to Ballu mode value."""
        if hvac_mode == "heat":
            return self.MODE_HEAT
        elif hvac_mode == "cool":
            return self.MODE_COOL
        elif hvac_mode == "dry":
            return self.MODE_DRY
        elif hvac_mode == "fan_only":
            return self.MODE_FAN
        elif hvac_mode in ["auto", "heat_cool"]:
            return self.MODE_AUTO
        else:  # off or unknown
            return self.MODE_AUTO
    
    def _fan_mode_to_ballu(self, fan_mode):
        """Convert fan mode to Ballu fan value."""
        if fan_mode == "high":
            return self.FAN_HIGH
        elif fan_mode == "medium":
            return self.FAN_MED
        elif fan_mode == "low":
            return self.FAN_LOW
        else:  # auto
            return self.FAN_AUTO
    
    def _encode_to_pulses(self, remote_state):
        """Convert 13-byte array to IR pulse sequence (LSB first)."""
        pulses = []
        
        # Header
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        
        # Data bytes (LSB FIRST)
        for byte in remote_state:
            for bit in range(8):  # 0 to 7, LSB first
                pulses.append(self.BIT_MARK)
                if byte & (1 << bit):  # Check bit from LSB to MSB
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Footer
        pulses.append(self.BIT_MARK)
        
        return pulses