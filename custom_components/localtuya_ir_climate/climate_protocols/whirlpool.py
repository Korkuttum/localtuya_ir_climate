# whirlpool.py
"""Whirlpool Climate IR Protocol."""
import logging
import time

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class WhirlpoolProtocol(ClimateIRProtocol):
    """
    Whirlpool Klima IR Protokolü
    ESPHome climate_ir_whirlpool.h/cpp referans alınarak yazılmıştır
    21-byte frame yapısı, iki model desteği
    """
    
    # Model types
    MODEL_DG11J1_3A = 0
    MODEL_DG11J1_91 = 1
    
    # Temperature ranges by model
    TEMP_MIN_DG11J1_3A = 18
    TEMP_MAX_DG11J1_3A = 32
    TEMP_MIN_DG11J1_91 = 16
    TEMP_MAX_DG11J1_91 = 30
    
    # State length
    STATE_LENGTH = 21
    
    # Modes (byte 3, bits 0-2)
    MODE_HEAT = 0
    MODE_AUTO = 1
    MODE_COOL = 2
    MODE_DRY = 3
    MODE_FAN = 4
    
    # Fan speeds (byte 2, bits 0-1)
    FAN_AUTO = 0
    FAN_HIGH = 1
    FAN_MED = 2
    FAN_LOW = 3
    
    # Masks
    SWING_MASK = 0x80  # Byte 2, bit 7
    POWER_MASK = 0x04  # Byte 2, bit 2
    
    # Fixed bytes
    FIXED_BYTE0 = 0x83
    FIXED_BYTE1 = 0x06
    FIXED_BYTE6 = 0x80
    FIXED_BYTE18_DG11J191 = 0x08
    
    # IR timing parameters (microseconds)
    HEADER_MARK = 9000
    HEADER_SPACE = 4494
    BIT_MARK = 572
    ONE_SPACE = 1659
    ZERO_SPACE = 553
    GAP = 7960
    CARRIER_FREQUENCY = 38000
    
    def __init__(self, model="dg11j1_91"):
        super().__init__()
        
        # Set model
        self.model = self._parse_model(model)
        
        # Set temperature range based on model
        if self.model == self.MODEL_DG11J1_3A:
            self._temperature_min = self.TEMP_MIN_DG11J1_3A
            self._temperature_max = self.TEMP_MAX_DG11J1_3A
        else:
            self._temperature_min = self.TEMP_MIN_DG11J1_91
            self._temperature_max = self.TEMP_MAX_DG11J1_91
        
        # Whirlpool supports vertical swing
        self.supported_swing_modes = ["off", "vertical"]
        self.supported_fan_modes = ["auto", "low", "medium", "high"]
        
        # State tracking
        self.powered_on_assumed = False
        self.last_transmit_time = 0
        self.swing_pending = False
        
        _LOGGER.debug(f"Whirlpool Protocol initialized for model: {self.model}")
    
    def _parse_model(self, model_str):
        """Parse model string to enum value."""
        if model_str.lower() == "dg11j1_3a":
            return self.MODEL_DG11J1_3A
        else:  # Default to DG11J1_91
            return self.MODEL_DG11J1_91
    
    @property
    def temperature_min(self):
        return self._temperature_min
        
    @property 
    def temperature_max(self):
        return self._temperature_max

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Whirlpool IR code for climate command."""
        _LOGGER.debug(f"Generating Whirlpool IR code: model={self.model}, mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        # Update last transmit time
        self.last_transmit_time = time.time() * 1000  # Convert to milliseconds
        
        remote_state = [0] * self.STATE_LENGTH
        
        # Set fixed bytes
        remote_state[0] = self.FIXED_BYTE0
        remote_state[1] = self.FIXED_BYTE1
        remote_state[6] = self.FIXED_BYTE6
        
        # Set model-specific byte
        if self.model == self.MODEL_DG11J1_91:
            remote_state[18] = self.FIXED_BYTE18_DG11J191
        
        # Handle power toggle if needed
        powered_on = hvac_mode != "off"
        if powered_on != self.powered_on_assumed:
            # Set power toggle command
            remote_state[2] = 4  # Power toggle
            remote_state[15] = 1
            self.powered_on_assumed = powered_on
        
        # Set mode if powered on
        if powered_on:
            if hvac_mode in ["auto", "heat_cool"]:
                remote_state[3] = self.MODE_AUTO
                remote_state[15] = 0x17
            elif hvac_mode == "heat":
                remote_state[3] = self.MODE_HEAT
                remote_state[15] = 6
            elif hvac_mode == "cool":
                remote_state[3] = self.MODE_COOL
                remote_state[15] = 6
            elif hvac_mode == "dry":
                remote_state[3] = self.MODE_DRY
                remote_state[15] = 6
            elif hvac_mode == "fan_only":
                remote_state[3] = self.MODE_FAN
                remote_state[15] = 6
        
        # Set temperature (if not OFF)
        if hvac_mode != "off":
            temp_val = max(self.temperature_min, min(self.temperature_max, target_temp))
            temp_offset = int(temp_val) - self.temperature_min
            remote_state[3] |= (temp_offset << 4)
        
        # Set fan speed (if not OFF)
        if hvac_mode != "off":
            fan_value = self.FAN_AUTO  # Default
            if fan_mode == "high":
                fan_value = self.FAN_HIGH
            elif fan_mode == "medium":
                fan_value = self.FAN_MED
            elif fan_mode == "low":
                fan_value = self.FAN_LOW
            
            remote_state[2] |= fan_value
        
        # Handle swing command
        if swing_mode == "vertical" and self.swing_pending:
            remote_state[2] |= self.SWING_MASK
            remote_state[8] |= 0x40  # 0x40 = 64
        
        # Reset swing pending flag
        self.swing_pending = False
        
        # Calculate checksums
        # First checksum: XOR of bytes 2-12 -> byte 13
        checksum13 = 0
        for i in range(2, 13):
            checksum13 ^= remote_state[i]
        remote_state[13] = checksum13
        
        # Second checksum: XOR of bytes 14-19 -> byte 20
        checksum20 = 0
        for i in range(14, 20):
            checksum20 ^= remote_state[i]
        remote_state[20] = checksum20
        
        _LOGGER.debug(f"Whirlpool remote state: {[f'0x{x:02X}' for x in remote_state]}")
        
        # Convert to pulse sequence with dividers
        pulses = self._encode_to_pulses(remote_state)
        
        return pulses
    
    def _encode_to_pulses(self, remote_state):
        """Convert 21-byte array to IR pulse sequence with dividers."""
        pulses = []
        
        # Header
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        
        # Data bytes (LSB FIRST)
        bytes_sent = 0
        for byte in remote_state:
            for bit in range(8):  # 0 to 7, LSB first
                pulses.append(self.BIT_MARK)
                if byte & (1 << bit):  # Check bit from LSB to MSB
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
            
            bytes_sent += 1
            
            # Add dividers after bytes 6 and 14
            if bytes_sent == 6 or bytes_sent == 14:
                pulses.extend([self.BIT_MARK, self.GAP])
        
        # Footer
        pulses.append(self.BIT_MARK)
        
        return pulses