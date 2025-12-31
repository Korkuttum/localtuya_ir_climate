# coolix.py
"""Coolix Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class CoolixProtocol(ClimateIRProtocol):
    """
    Coolix Klima IR Protokolü
    ESPHome climate_ir_coolix.h/cpp referans alınarak yazılmıştır
    Midea ile uyumludur
    """
    
    # Temperature range
    TEMP_MIN = 17
    TEMP_MAX = 30
    
    # Special commands
    COOLIX_OFF = 0xB27BE0
    COOLIX_SWING = 0xB26BE0
    COOLIX_LED = 0xB5F5A5
    COOLIX_SILENCE_FP = 0xB5F5B6
    
    # Modes (bits 2-3)
    COOLIX_COOL = 0b0000
    COOLIX_DRY_FAN = 0b0100
    COOLIX_AUTO = 0b1000
    COOLIX_HEAT = 0b1100
    MODE_MASK = 0b1100
    
    # Fan masks
    FAN_MASK = 0xF000
    FAN_MODE_AUTO_DRY = 0x1000
    FAN_AUTO = 0xB000
    FAN_MIN = 0x9000  # Low
    FAN_MED = 0x5000  # Medium
    FAN_MAX = 0x3000  # High
    
    # Temperature
    TEMP_RANGE = TEMP_MAX - TEMP_MIN + 1
    FAN_TEMP_CODE = 0b11100000  # For FAN_ONLY mode
    TEMP_MASK = 0b11110000
    
    # Temperature mapping (Gray code)
    TEMP_MAP = [
        0b00000000,  # 17C
        0b00010000,  # 18C
        0b00110000,  # 19C
        0b00100000,  # 20C
        0b01100000,  # 21C
        0b01110000,  # 22C
        0b01010000,  # 23C
        0b01000000,  # 24C
        0b11000000,  # 25C
        0b11010000,  # 26C
        0b10010000,  # 27C
        0b10000000,  # 28C
        0b10100000,  # 29C
        0b10110000   # 30C
    ]
    
    # Base state
    BASE_STATE = 0xB20F00
    
    def __init__(self):
        super().__init__()
        
        # Coolix supports vertical swing
        self.supported_swing_modes = ["off", "vertical"]
        self.supported_fan_modes = ["auto", "low", "medium", "high"]
        
        # Swing command tracking
        self.swing_pending = False
        
        _LOGGER.debug("Coolix Protocol initialized")
    
    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Coolix IR code for climate command."""
        _LOGGER.debug(f"Generating Coolix IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        # Check for swing command
        if swing_mode == "vertical" and not self.swing_pending:
            self.swing_pending = True
            _LOGGER.debug("Sending Coolix swing command")
            return self._encode_coolix_command(self.COOLIX_SWING)
        
        # Reset swing pending
        self.swing_pending = False
        
        # Handle OFF mode
        if hvac_mode == "off":
            return self._encode_coolix_command(self.COOLIX_OFF)
        
        # Start with base state
        remote_state = self.BASE_STATE
        
        # Set mode
        if hvac_mode == "cool":
            remote_state |= self.COOLIX_COOL
        elif hvac_mode == "heat":
            remote_state |= self.COOLIX_HEAT
        elif hvac_mode in ["auto", "heat_cool"]:
            remote_state |= self.COOLIX_AUTO
        elif hvac_mode in ["dry", "fan_only"]:
            remote_state |= self.COOLIX_DRY_FAN
        else:
            remote_state |= self.COOLIX_AUTO  # Default
        
        # Set temperature or fan-only code
        if hvac_mode == "fan_only":
            remote_state |= self.FAN_TEMP_CODE
        else:
            # Normal temperature
            temp_val = max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp))
            temp_index = int(temp_val) - self.TEMP_MIN
            if temp_index < len(self.TEMP_MAP):
                remote_state |= self.TEMP_MAP[temp_index]
        
        # Set fan speed
        if hvac_mode in ["auto", "heat_cool", "dry"]:
            # AUTO/HEAT_COOL/DRY modes force AUTO fan
            remote_state |= self.FAN_MODE_AUTO_DRY
        else:
            # Normal fan control
            if fan_mode == "high":
                remote_state |= self.FAN_MAX
            elif fan_mode == "medium":
                remote_state |= self.FAN_MED
            elif fan_mode == "low":
                remote_state |= self.FAN_MIN
            else:  # auto
                remote_state |= self.FAN_AUTO
        
        _LOGGER.debug(f"Coolix remote state: 0x{remote_state:06X}")
        
        # Convert to pulse sequence
        return self._encode_coolix_command(remote_state)
    
    def _encode_coolix_command(self, command):
        """Encode Coolix 24-bit command to pulse sequence."""
        # Coolix uses its own protocol encoding
        # For simplicity, we'll use a generic approach
        # Actual implementation would use CoolixProtocol class
        
        pulses = []
        
        # Coolix timing parameters (typical values)
        HEADER_MARK = 4500
        HEADER_SPACE = 4500
        BIT_MARK = 560
        ONE_SPACE = 1690
        ZERO_SPACE = 560
        GAP = 2250
        
        # Header
        pulses.extend([HEADER_MARK, HEADER_SPACE])
        
        # Convert 24-bit command to bytes
        bytes_data = [
            (command >> 16) & 0xFF,
            (command >> 8) & 0xFF,
            command & 0xFF
        ]
        
        # Data bytes (LSB first for Coolix)
        for byte in bytes_data:
            for bit in range(8):  # 0 to 7, LSB first
                pulses.append(BIT_MARK)
                if byte & (1 << bit):  # Check bit from LSB to MSB
                    pulses.append(ONE_SPACE)
                else:
                    pulses.append(ZERO_SPACE)
        
        # Footer
        pulses.append(BIT_MARK)
        
        return pulses