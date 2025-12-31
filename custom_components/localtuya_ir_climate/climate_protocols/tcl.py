# tcl.py
"""TCL112 Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class TCLProtocol(ClimateIRProtocol):
    """
    TCL112 Klima IR Protokolü
    ESPHome climate_ir_tcl112.h/cpp referans alınarak yazılmıştır
    """
    
    # Temperature range
    TEMP_MIN = 16.0
    TEMP_MAX = 31.0
    TEMP_STEP = 0.5  # Yarım derece hassasiyet
    
    # State length
    STATE_LENGTH = 14
    BITS = STATE_LENGTH * 8
    
    # Modes
    TCL_HEAT = 1
    TCL_DRY = 2
    TCL_COOL = 3
    TCL_FAN = 7
    TCL_AUTO = 8
    
    # Fan speeds
    FAN_AUTO = 0
    FAN_LOW = 2
    FAN_MED = 3
    FAN_HIGH = 5
    
    # Masks
    VSWING_MASK = 0x38  # Vertical swing mask (bits 3-5)
    POWER_MASK = 0x04   # Power mask
    
    # Half degree flag
    HALF_DEGREE = 0b00100000
    
    # IR timing parameters (microseconds)
    HEADER_MARK = 3100
    HEADER_SPACE = 1650
    BIT_MARK = 500
    ONE_SPACE = 1100
    ZERO_SPACE = 350
    GAP = 1650  # Same as HEADER_SPACE
    
    # Fixed bytes
    FIXED_BYTE0 = 0x23
    FIXED_BYTE1 = 0xCB
    FIXED_BYTE2 = 0x26
    FIXED_BYTE3 = 0x01
    
    def __init__(self):
        super().__init__()
        
        # TCL112 supports vertical swing and half-degree temperature
        self.supported_swing_modes = ["off", "vertical"]
        self.supported_fan_modes = ["auto", "low", "medium", "high"]
        
        # TCL uses half-degree precision
        self._temperature_step = 0.5
        
        _LOGGER.debug("TCL112 Protocol initialized")
    
    @property
    def temperature_step(self):
        return self._temperature_step

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate TCL112 IR code for climate command."""
        _LOGGER.debug(f"Generating TCL112 IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        remote_state = [0] * self.STATE_LENGTH
        
        # Set known good state (On, Cool, 24C as base)
        remote_state[0] = self.FIXED_BYTE0
        remote_state[1] = self.FIXED_BYTE1
        remote_state[2] = self.FIXED_BYTE2
        remote_state[3] = self.FIXED_BYTE3
        remote_state[5] = 0x24  # Default power on state
        remote_state[6] = 0x03  # Default mode bits
        remote_state[7] = 0x07  # Default temperature
        remote_state[8] = 0x40  # Default fan/swing
        
        # Set mode
        if hvac_mode == "off":
            # Clear power bit
            remote_state[5] &= ~self.POWER_MASK
        else:
            # Ensure power bit is set
            remote_state[5] |= self.POWER_MASK
            
            # Clear mode bits (lower 4 bits of byte 6)
            remote_state[6] &= 0xF0
            
            # Set mode
            if hvac_mode == "heat":
                remote_state[6] |= self.TCL_HEAT
            elif hvac_mode == "cool":
                remote_state[6] |= self.TCL_COOL
            elif hvac_mode == "dry":
                remote_state[6] |= self.TCL_DRY
            elif hvac_mode == "fan_only":
                remote_state[6] |= self.TCL_FAN
            elif hvac_mode in ["auto", "heat_cool"]:
                remote_state[6] |= self.TCL_AUTO
            else:
                remote_state[6] |= self.TCL_AUTO  # Default to AUTO
        
        # Set temperature (with half-degree support)
        # Clamp temperature to valid range
        safe_temp = max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp))
        
        # Convert to half degrees
        half_degrees = int(safe_temp * 2)
        
        # Check for half degree
        if half_degrees & 1:  # Odd number = half degree
            remote_state[12] |= self.HALF_DEGREE
        else:
            remote_state[12] &= ~self.HALF_DEGREE
        
        # Calculate temperature value (inverted: TEMP_MAX - temp)
        temp_value = int(self.TEMP_MAX) - (half_degrees // 2)
        
        # Clear temperature bits in byte 7 (lower 4 bits)
        remote_state[7] &= 0xF0
        # Set temperature
        remote_state[7] |= temp_value
        
        # Set fan speed
        fan_value = self.FAN_AUTO  # Default
        if fan_mode == "high":
            fan_value = self.FAN_HIGH
        elif fan_mode == "medium":
            fan_value = self.FAN_MED
        elif fan_mode == "low":
            fan_value = self.FAN_LOW
        
        # Clear fan bits (lower 3 bits of byte 8)
        remote_state[8] &= 0xF8
        # Set fan
        remote_state[8] |= fan_value
        
        # Set vertical swing
        if swing_mode == "vertical":
            remote_state[8] |= self.VSWING_MASK
        else:
            remote_state[8] &= ~self.VSWING_MASK
        
        # Calculate checksum (sum of first 13 bytes)
        checksum = 0
        for i in range(self.STATE_LENGTH - 1):
            checksum += remote_state[i]
        remote_state[self.STATE_LENGTH - 1] = checksum & 0xFF
        
        _LOGGER.debug(f"TCL112 remote state: {[f'0x{x:02X}' for x in remote_state]}")
        
        # Convert to pulse sequence (LSB first)
        pulses = self._encode_to_pulses(remote_state)
        
        return pulses
    
    def _encode_to_pulses(self, remote_state):
        """Convert 14-byte array to IR pulse sequence (LSB first)."""
        pulses = []
        
        # Header
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        
        # Data bytes (LSB FIRST - TCL specific)
        for byte in remote_state:
            for bit in range(8):  # 0 to 7, LSB first
                pulses.append(self.BIT_MARK)
                if byte & (1 << bit):  # Check bit from LSB to MSB
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Footer
        pulses.extend([self.BIT_MARK, self.GAP])
        
        return pulses