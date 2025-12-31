# gree.py
"""Gree Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class GreeProtocol(ClimateIRProtocol):
    """
    Gree Klima IR Protokolü
    ESPHome climate_ir_gree.h/cpp referans alınarak yazılmıştır
    """
    
    # Temperature range
    TEMP_MIN = 16
    TEMP_MAX = 30
    
    # Modes
    MODE_AUTO = 0x00
    MODE_COOL = 0x01
    MODE_HEAT = 0x04
    MODE_DRY = 0x02
    MODE_FAN = 0x03
    MODE_OFF = 0x00
    MODE_ON = 0x08
    
    # Fan speeds
    FAN_AUTO = 0x00
    FAN_1 = 0x10    # Low
    FAN_2 = 0x20    # Medium
    FAN_3 = 0x30    # High
    FAN_TURBO = 0x80  # Turbo (YX1FF only)
    
    # Special flags
    FAN_TURBO_BIT = 0x10      # Turbo bit in remote_state[2]
    PRESET_SLEEP_BIT = 0x80   # Sleep preset bit in remote_state[0]
    
    # Presets
    PRESET_NONE = 0x00
    PRESET_SLEEP = 0x01
    
    # Vertical directions
    VDIR_AUTO = 0x00
    VDIR_MANUAL = 0x00
    VDIR_SWING = 0x01
    VDIR_UP = 0x02
    VDIR_MUP = 0x03
    VDIR_MIDDLE = 0x04
    VDIR_MDOWN = 0x05
    VDIR_DOWN = 0x06
    
    # Horizontal directions
    HDIR_AUTO = 0x00
    HDIR_MANUAL = 0x00
    HDIR_SWING = 0x01
    HDIR_LEFT = 0x02
    HDIR_MLEFT = 0x03
    HDIR_MIDDLE = 0x04
    HDIR_MRIGHT = 0x05
    HDIR_RIGHT = 0x06
    
    # Model types
    MODEL_GENERIC = 0
    MODEL_YAN = 1
    MODEL_YAA = 2
    MODEL_YAC = 3
    MODEL_YAC1FB9 = 4
    MODEL_YX1FF = 5
    MODEL_YAG = 6
    
    # IR timing parameters (microseconds)
    IR_FREQUENCY = 38000
    HEADER_MARK = 9000
    HEADER_SPACE = 4000
    YAC1FB9_HEADER_SPACE = 4500
    BIT_MARK = 620
    ONE_SPACE = 1600
    ZERO_SPACE = 540
    MESSAGE_SPACE = 19000
    YAC1FB9_MESSAGE_SPACE = 19980
    
    def __init__(self, model="generic"):
        super().__init__()
        
        # Set model type
        self.model = self._parse_model(model)
        
        # Configure supported features based on model
        self._configure_model_features()
        
        # Mode bits for YAN, YAA, YAC, YAC1FB9 models
        self.mode_bits = 0
        
        # Special mode switches (Turbo, Light, Health, X-Fan)
        self.turbo_mode = False
        self.light_mode = False
        self.health_mode = False
        self.xfan_mode = False
        
        _LOGGER.debug(f"Gree Protocol initialized for model: {self.model}")
    
    def _parse_model(self, model_str):
        """Parse model string to enum value."""
        model_map = {
            "generic": self.MODEL_GENERIC,
            "yan": self.MODEL_YAN,
            "yaa": self.MODEL_YAA,
            "yac": self.MODEL_YAC,
            "yac1fb9": self.MODEL_YAC1FB9,
            "yx1ff": self.MODEL_YX1FF,
            "yag": self.MODEL_YAG
        }
        return model_map.get(model_str.lower(), self.MODEL_GENERIC)
    
    def _configure_model_features(self):
        """Configure supported features based on model."""
        # All models support basic fan modes
        self.supported_fan_modes = ["auto", "low", "medium", "high"]
        
        # All models support basic swing modes
        self.supported_swing_modes = ["off", "vertical", "horizontal", "both"]
        
        # YX1FF has quiet fan and sleep preset
        if self.model == self.MODEL_YX1FF:
            self.supported_fan_modes.append("quiet")
            self.supported_presets = ["none", "sleep"]
        else:
            self.supported_presets = ["none"]
        
        # Set temperature range based on model
        self._temperature_min = self.TEMP_MIN
        self._temperature_max = self.TEMP_MAX
    
    @property
    def temperature_min(self):
        return self._temperature_min
        
    @property 
    def temperature_max(self):
        return self._temperature_max
    
    def set_mode_bit(self, bit_mask, enabled):
        """Set mode bit for YAN, YAA, YAC, YAC1FB9 models."""
        if enabled:
            self.mode_bits |= bit_mask
        else:
            self.mode_bits &= ~bit_mask
        _LOGGER.debug(f"Mode bits updated: 0x{self.mode_bits:02X}")
    
    def set_turbo_mode(self, enabled):
        """Set turbo mode (YX1FF only)."""
        self.turbo_mode = enabled
    
    def set_light_mode(self, enabled):
        """Set light mode."""
        self.light_mode = enabled
    
    def set_health_mode(self, enabled):
        """Set health mode."""
        self.health_mode = enabled
    
    def set_xfan_mode(self, enabled):
        """Set X-Fan mode."""
        self.xfan_mode = enabled

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Gree IR code for climate command."""
        _LOGGER.debug(f"Generating Gree IR code: model={self.model}, mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        # Initialize 8-byte remote state
        remote_state = [0x00, 0x00, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00]
        
        # Byte 0: Fan speed and operation mode
        remote_state[0] = self._fan_speed_value(fan_mode) | self._operation_mode_value(hvac_mode)
        
        # Byte 1: Temperature
        remote_state[1] = self._temperature_value(target_temp)
        
        # Configure bytes 2-6 based on model
        self._configure_model_bytes(remote_state, swing_mode, fan_mode, hvac_mode)
        
        # Calculate checksum based on model
        self._calculate_checksum(remote_state)
        
        _LOGGER.debug(f"Gree remote state: {[f'0x{x:02X}' for x in remote_state]}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(remote_state)
        _LOGGER.debug(f"Generated {len(pulses)} pulses")
        
        return pulses
    
    def _operation_mode_value(self, hvac_mode):
        """Convert HVAC mode to Gree operation mode byte."""
        operating_mode = self.MODE_ON
        
        if hvac_mode == "off":
            return self.MODE_OFF
        elif hvac_mode == "cool":
            operating_mode |= self.MODE_COOL
        elif hvac_mode == "dry":
            operating_mode |= self.MODE_DRY
        elif hvac_mode == "heat":
            operating_mode |= self.MODE_HEAT
        elif hvac_mode == "fan_only":
            operating_mode |= self.MODE_FAN
        elif hvac_mode in ["auto", "heat_cool"]:
            operating_mode |= self.MODE_AUTO
        else:
            operating_mode |= self.MODE_AUTO
        
        # Add sleep preset bit for YX1FF
        if self.model == self.MODEL_YX1FF and hasattr(self, 'preset') and self.preset == "sleep":
            operating_mode |= self.PRESET_SLEEP_BIT
        
        return operating_mode
    
    def _fan_speed_value(self, fan_mode):
        """Convert fan mode to Gree fan speed value."""
        if self.model == self.MODEL_YX1FF:
            # YX1FF has 4 fan speeds + turbo
            if fan_mode == "quiet":
                return self.FAN_1
            elif fan_mode == "low":
                return self.FAN_2
            elif fan_mode == "medium":
                return self.FAN_3
            elif fan_mode == "high":
                return self.FAN_TURBO  # Turbo mode
            else:  # auto
                return self.FAN_AUTO
        else:
            # Standard models have 3 fan speeds
            if fan_mode == "low":
                return self.FAN_1
            elif fan_mode == "medium":
                return self.FAN_2
            elif fan_mode == "high":
                return self.FAN_3
            else:  # auto
                return self.FAN_AUTO
    
    def _temperature_value(self, target_temp):
        """Convert temperature to Gree temperature byte."""
        temp_val = max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp))
        return int(round(temp_val))
    
    def _vertical_swing_value(self, swing_mode):
        """Get vertical swing value."""
        if swing_mode in ["vertical", "both"]:
            return self.VDIR_SWING
        else:
            return self.VDIR_MANUAL
    
    def _horizontal_swing_value(self, swing_mode):
        """Get horizontal swing value."""
        if swing_mode in ["horizontal", "both"]:
            return self.HDIR_SWING
        else:
            return self.HDIR_MANUAL
    
    def _configure_model_bytes(self, remote_state, swing_mode, fan_mode, hvac_mode):
        """Configure bytes 2-6 based on model type."""
        vertical_swing = self._vertical_swing_value(swing_mode)
        horizontal_swing = self._horizontal_swing_value(swing_mode)
        
        if self.model == self.MODEL_YAN:
            remote_state[2] = 0x20  # Bits 0-3: 0000, Bits 4-7: TURBO, LIGHT, HEALTH, X-FAN
            remote_state[3] = 0x50  # Bits 4-7: 0101
            remote_state[4] = vertical_swing
            
            # Merge mode bits
            remote_state[2] = (remote_state[2] & 0x0F) | self.mode_bits
        
        elif self.model == self.MODEL_YX1FF or self.model == self.MODEL_YAG:
            remote_state[2] = 0x60
            remote_state[3] = 0x50
            remote_state[4] = vertical_swing
            
            # YX1FF turbo mode
            if self.model == self.MODEL_YX1FF and fan_mode == "high":  # turbo
                remote_state[2] |= self.FAN_TURBO_BIT
            
            # YAG swing bit
            if self.model == self.MODEL_YAG and (vertical_swing == self.VDIR_SWING or 
                                                 horizontal_swing == self.HDIR_SWING):
                remote_state[0] |= (1 << 6)  # Set bit 6 for swing
        
        elif self.model == self.MODEL_YAG:
            remote_state[5] = 0x40
            
            if vertical_swing == self.VDIR_SWING or horizontal_swing == self.HDIR_SWING:
                remote_state[0] |= (1 << 6)  # Set bit 6 for swing
        
        elif self.model == self.MODEL_YAC or self.model == self.MODEL_YAG:
            remote_state[4] |= (horizontal_swing << 4)
        
        elif self.model in [self.MODEL_YAA, self.MODEL_YAC, self.MODEL_YAC1FB9]:
            remote_state[2] = 0x20  # Bits 0-3: 0000, Bits 4-7: TURBO, LIGHT, HEALTH, X-FAN
            remote_state[3] = 0x50  # Bits 4-7: 0101
            remote_state[6] = 0x20  # YAA1FB, FAA1FB1, YB1F2 bits 4-7: 0010
            
            if vertical_swing == self.VDIR_SWING:
                remote_state[0] |= (1 << 6)  # Enable swing by setting bit 6
            elif vertical_swing != self.VDIR_AUTO:
                remote_state[5] = vertical_swing
            
            # Merge mode bits
            remote_state[2] = (remote_state[2] & 0x0F) | self.mode_bits
        
        # Generic/default configuration
        else:
            remote_state[2] = 0x20
            remote_state[3] = 0x50
            remote_state[4] = vertical_swing
    
    def _calculate_checksum(self, remote_state):
        """Calculate checksum based on model."""
        if self.model == self.MODEL_YAN or self.model == self.MODEL_YX1FF:
            # YAN and YX1FF checksum
            remote_state[7] = ((remote_state[0] << 4) + (remote_state[1] << 4) + 0xC0) & 0xFF
        
        elif self.model == self.MODEL_YAG:
            # YAG checksum
            checksum = (
                ((remote_state[0] & 0x0F) +
                 (remote_state[1] & 0x0F) +
                 (remote_state[2] & 0x0F) +
                 (remote_state[3] & 0x0F) +
                 ((remote_state[4] & 0xF0) >> 4) +
                 ((remote_state[5] & 0xF0) >> 4) +
                 ((remote_state[6] & 0xF0) >> 4) +
                 0x0A) & 0x0F
            ) << 4
            remote_state[7] = checksum
        
        else:
            # Other models checksum
            checksum = (
                (((remote_state[0] & 0x0F) +
                  (remote_state[1] & 0x0F) +
                  (remote_state[2] & 0x0F) +
                  (remote_state[3] & 0x0F) +
                  ((remote_state[5] & 0xF0) >> 4) +
                  ((remote_state[6] & 0xF0) >> 4) +
                  ((remote_state[7] & 0xF0) >> 4) +
                  0x0A) & 0x0F) << 4
            ) | (remote_state[7] & 0x0F)
            remote_state[7] = checksum
    
    def _encode_to_pulses(self, remote_state):
        """Convert 8-byte array to IR pulse sequence."""
        pulses = []
        
        # Set carrier frequency
        # Note: In actual implementation, this would be set on the transmitter
        
        # Header
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        
        # First 4 bytes
        for i in range(4):
            byte = remote_state[i]
            for mask in [1, 2, 4, 8, 16, 32, 64, 128]:  # MSB first
                pulses.append(self.BIT_MARK)
                if byte & mask:
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Fixed pattern
        pulses.extend([
            self.BIT_MARK, self.ZERO_SPACE,
            self.BIT_MARK, self.ONE_SPACE,
            self.BIT_MARK, self.ZERO_SPACE
        ])
        
        # Message space
        pulses.append(self.BIT_MARK)
        if self.model == self.MODEL_YAC1FB9:
            pulses.append(self.YAC1FB9_MESSAGE_SPACE)
        else:
            pulses.append(self.MESSAGE_SPACE)
        
        # Last 4 bytes
        for i in range(4, 8):
            byte = remote_state[i]
            for mask in [1, 2, 4, 8, 16, 32, 64, 128]:  # MSB first
                pulses.append(self.BIT_MARK)
                if byte & mask:
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Final mark
        pulses.append(self.BIT_MARK)
        
        return pulses