# mitsubishi.py
"""Mitsubishi Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class MitsubishiProtocol(ClimateIRProtocol):
    """
    Mitsubishi Klima IR Protokolü
    ESPHome climate_ir_mitsubishi.h/cpp referans alınarak yazılmıştır
    """
    
    TEMP_MIN = 16
    TEMP_MAX = 31
    TEMP_STEP = 1
    
    # Byte 5: On/Off
    MITSUBISHI_OFF = 0x00
    POWER_ON = 0x20
    
    # Byte 6: Modes
    MITSUBISHI_MODE_AUTO = 0x20
    MITSUBISHI_MODE_COOL = 0x18
    MITSUBISHI_MODE_DRY = 0x10
    MITSUBISHI_MODE_FAN_ONLY = 0x38
    MITSUBISHI_MODE_HEAT = 0x08
    
    # Byte 8: Mode A (different from Byte 6)
    MITSUBISHI_MODE_A_HEAT = 0x00
    MITSUBISHI_MODE_A_DRY = 0x02
    MITSUBISHI_MODE_A_COOL = 0x06
    MITSUBISHI_MODE_A_AUTO = 0x06
    
    # Byte 8: Wide Vane (horizontal swing)
    MITSUBISHI_WIDE_VANE_SWING = 0xC0
    
    # Byte 9: Fan
    MITSUBISHI_FAN_AUTO = 0x00
    
    # Byte 9: Vertical Vane
    MITSUBISHI_VERTICAL_VANE_SWING = 0x38
    MITSUBISHI_OTHERWISE = 0x40
    
    # Byte 14: Presets
    MITSUBISHI_ECONOCOOL = 0x20
    MITSUBISHI_NIGHTMODE = 0xC1
    
    # Byte 15: Presets
    MITSUBISHI_POWERFUL = 0x08
    
    # Constant bytes
    MITSUBISHI_BYTE00 = 0x23
    MITSUBISHI_BYTE01 = 0xCB
    MITSUBISHI_BYTE02 = 0x26
    MITSUBISHI_BYTE03 = 0x01
    MITSUBISHI_BYTE04 = 0x00
    MITSUBISHI_BYTE13 = 0x00
    MITSUBISHI_BYTE16 = 0x00
    
    # IR timing parameters (microseconds)
    BIT_MARK = 430
    ONE_SPACE = 1250
    ZERO_SPACE = 390
    HEADER_MARK = 3500
    HEADER_SPACE = 1700
    MIN_GAP = 17500
    
    # Fan mode mappings
    FAN_MODE_3L = 0  # 3 levels + auto
    FAN_MODE_4L = 1  # 4 levels + auto  
    FAN_MODE_Q4L = 2 # Quiet + 4 levels + auto
    
    def __init__(self):
        super().__init__()
        
        # Mitsubishi supports both vertical and horizontal swing
        self.supported_swing_modes = [
            "off", "vertical", "horizontal", "both"
        ]
        
        # Additional presets
        self.supported_presets = ["none", "eco", "boost", "sleep"]
        
        # State tracking
        self.swing_active = False
        self.swing_horizontal = False
        self.swing_vertical = False
        
        # Fan mode setting (default to 3 levels)
        self.fan_mode_type = self.FAN_MODE_3L
        
        # Default directions when swing is off
        self.default_horizontal_direction = 0x30  # MIDDLE
        self.default_vertical_direction = 0x00    # AUTO
        
        _LOGGER.debug("Mitsubishi Protocol initialized (3-level fan mode)")

    def set_fan_mode_type(self, fan_mode_type):
        """Set fan mode type: 0=3L, 1=4L, 2=Q4L"""
        self.fan_mode_type = fan_mode_type
        _LOGGER.debug(f"Fan mode type set to: {fan_mode_type}")

    def set_horizontal_default(self, direction):
        """Set default horizontal direction when swing is off"""
        self.default_horizontal_direction = direction
        
    def set_vertical_default(self, direction):
        """Set default vertical direction when swing is off"""
        self.default_vertical_direction = direction

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Mitsubishi IR code for climate command."""
        _LOGGER.debug(f"Generating Mitsubishi IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        # Initialize remote state with constant bytes
        remote_state = [
            0x23, 0xCB, 0x26, 0x01, 0x00,  # Bytes 0-4: Constant
            0x20,  # Byte 5: Power (0x20=On, 0x00=Off)
            0x00,  # Byte 6: Mode
            0x00,  # Byte 7: Temperature
            0x00,  # Byte 8: Mode A & Wide Vane
            0x00,  # Byte 9: Fan & Vertical Vane
            0x00,  # Byte 10: Clock current time (not used)
            0x00,  # Byte 11: End clock (not used)
            0x00,  # Byte 12: Start clock (not used)
            0x00,  # Byte 13: Constant 0x00
            0x00,  # Byte 14: ECONO COOL, CLEAN MODE, etc.
            0x00,  # Byte 15: POWERFUL, SMART SET, PLASMA, etc.
            0x00,  # Byte 16: Constant 0x00
            0x00   # Byte 17: Checksum (will be calculated)
        ]
        
        # Determine swing states
        swing_horizontal = swing_mode in ["horizontal", "both"]
        swing_vertical = swing_mode in ["vertical", "both"]
        
        # Byte 5: On/Off
        if hvac_mode == "off":
            remote_state[5] = self.MITSUBISHI_OFF
        else:
            remote_state[5] = self.POWER_ON
        
        # Byte 6: Mode and Byte 8: Mode A
        if hvac_mode == "heat":
            remote_state[6] = self.MITSUBISHI_MODE_HEAT
            remote_state[8] = self.MITSUBISHI_MODE_A_HEAT
        elif hvac_mode == "dry":
            remote_state[6] = self.MITSUBISHI_MODE_DRY
            remote_state[8] = self.MITSUBISHI_MODE_A_DRY
        elif hvac_mode == "cool":
            remote_state[6] = self.MITSUBISHI_MODE_COOL
            remote_state[8] = self.MITSUBISHI_MODE_A_COOL
        elif hvac_mode == "fan_only":
            remote_state[6] = self.MITSUBISHI_MODE_FAN_ONLY
            remote_state[8] = self.MITSUBISHI_MODE_A_AUTO
        elif hvac_mode == "auto" or hvac_mode == "heat_cool":
            remote_state[6] = self.MITSUBISHI_MODE_AUTO
            remote_state[8] = self.MITSUBISHI_MODE_A_AUTO
        else:  # off or unknown
            # When off, still set a mode for when it turns on
            remote_state[6] = self.MITSUBISHI_MODE_COOL
            remote_state[8] = self.MITSUBISHI_MODE_A_COOL
        
        # Byte 7: Temperature (0-15, added to 16°C = 16-31°C)
        if hvac_mode == "dry":
            # Dry mode always sends 24°C
            remote_state[7] = 24 - self.TEMP_MIN
        else:
            temp_val = int(max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp)))
            remote_state[7] = temp_val - self.TEMP_MIN
        
        # Byte 8: Wide Vane (horizontal swing)
        if swing_horizontal:
            remote_state[8] = remote_state[8] | self.MITSUBISHI_WIDE_VANE_SWING
        else:
            remote_state[8] = remote_state[8] | self.default_horizontal_direction
        
        # Byte 9: Fan speed (bits 0-2)
        fan_speed = self._fan_mode_to_speed(fan_mode)
        remote_state[9] = fan_speed
        
        # Byte 9: Vertical Vane (bits 3-5) and Switch to Auto (bit 6)
        if swing_vertical:
            remote_state[9] = remote_state[9] | self.MITSUBISHI_VERTICAL_VANE_SWING | self.MITSUBISHI_OTHERWISE
        else:
            remote_state[9] = remote_state[9] | self.default_vertical_direction | self.MITSUBISHI_OTHERWISE
        
        # Byte 14-15: Presets (currently not implemented in our base)
        # Would need to add preset support to base class
        
        # Byte 17: Checksum (sum of bytes 0-16)
        for i in range(17):
            remote_state[17] = (remote_state[17] + remote_state[i]) & 0xFF
        
        _LOGGER.debug(f"Mitsubishi remote state: {[f'0x{x:02X}' for x in remote_state]}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(remote_state)
        _LOGGER.debug(f"Generated {len(pulses)} pulses")
        
        return pulses

    def _fan_mode_to_speed(self, fan_mode):
        """Convert fan mode to Mitsubishi speed value (0-5)."""
        # Map fan modes to speed values
        if fan_mode == "auto":
            return self.MITSUBISHI_FAN_AUTO
        elif fan_mode == "low":
            return 1
        elif fan_mode == "medium":
            if self.fan_mode_type == self.FAN_MODE_3L:
                return 2  # For 3-level, medium = level 2
            else:
                return 3  # For 4-level, medium = level 3
        elif fan_mode == "high":
            if self.fan_mode_type == self.FAN_MODE_3L:
                return 3  # For 3-level, high = level 3
            else:
                return 4  # For 4-level, high = level 4
        elif fan_mode == "middle":  # Only for 4+ level fans
            return 2
        elif fan_mode == "quiet":  # Only for Q4L
            return 5
        else:
            return self.MITSUBISHI_FAN_AUTO

    def _encode_to_pulses(self, remote_state):
        """Convert 18-byte array to IR pulse sequence."""
        pulses = []
        
        # Repeat twice (as per Mitsubishi protocol)
        for repeat in range(2):
            # Header
            pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
            
            # Data bytes (LSB first)
            for byte in remote_state:
                for bit in range(8):
                    pulses.append(self.BIT_MARK)
                    
                    # Check bit (LSB first)
                    if byte & (1 << bit):
                        pulses.append(self.ONE_SPACE)
                    else:
                        pulses.append(self.ZERO_SPACE)
            
            # Footer between repeats
            if repeat == 0:
                pulses.append(self.BIT_MARK)
                pulses.append(self.MIN_GAP)
        
        # Final mark
        pulses.append(self.BIT_MARK)
        
        return pulses