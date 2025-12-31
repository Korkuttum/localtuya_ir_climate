# fujitsu.py
"""Fujitsu General Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class FujitsuProtocol(ClimateIRProtocol):
    """
    Fujitsu General Klima IR Protokolü
    ESPHome climate_ir_fujitsu_general.h/cpp referans alınarak yazılmıştır
    Byte'ların bitleri ters (LSB first) ve nibble'lar özel düzendedir
    """
    
    # Temperature range
    TEMP_MIN = 16  # Celsius
    TEMP_MAX = 30  # Celsius
    
    # Message lengths
    COMMON_LENGTH = 6
    STATE_MESSAGE_LENGTH = 16
    UTIL_MESSAGE_LENGTH = 7
    
    # Common header bytes
    COMMON_BYTE0 = 0x14
    COMMON_BYTE1 = 0x63
    COMMON_BYTE2 = 0x00
    COMMON_BYTE3 = 0x10
    COMMON_BYTE4 = 0x10
    MESSAGE_TYPE_BYTE = 5
    
    # Message types
    MESSAGE_TYPE_STATE = 0xFE
    MESSAGE_TYPE_OFF = 0x02
    MESSAGE_TYPE_ECONOMY = 0x09
    MESSAGE_TYPE_NUDGE = 0x6C
    
    # State header
    STATE_HEADER_BYTE0 = 0x09
    STATE_HEADER_BYTE1 = 0x30
    
    # State footer
    STATE_FOOTER_BYTE0 = 0x20
    
    # Nibble positions
    TEMPERATURE_NIBBLE = 16
    POWER_ON_NIBBLE = 17
    MODE_NIBBLE = 19
    SWING_NIBBLE = 20
    FAN_NIBBLE = 21
    
    # Power values
    POWER_OFF = 0x00
    POWER_ON = 0x01
    
    # Mode values
    MODE_AUTO = 0x00
    MODE_COOL = 0x01
    MODE_DRY = 0x02
    MODE_FAN = 0x03
    MODE_HEAT = 0x04
    # MODE_10C = 0x0B  # Not supported in ESPHome
    
    # Swing values
    SWING_NONE = 0x00
    SWING_VERTICAL = 0x01
    SWING_HORIZONTAL = 0x02
    SWING_BOTH = 0x03
    
    # Fan values
    FAN_AUTO = 0x00
    FAN_HIGH = 0x01
    FAN_MEDIUM = 0x02
    FAN_LOW = 0x03
    FAN_SILENT = 0x04
    
    # IR timing parameters (microseconds)
    HEADER_MARK = 3300
    HEADER_SPACE = 1600
    BIT_MARK = 420
    ONE_SPACE = 1200
    ZERO_SPACE = 420
    TRL_MARK = 420
    TRL_SPACE = 8000
    CARRIER_FREQUENCY = 38000
    
    def __init__(self):
        super().__init__()
        
        # Fujitsu supports all swing modes and quiet fan
        self.supported_swing_modes = ["off", "vertical", "horizontal", "both"]
        self.supported_fan_modes = ["auto", "low", "medium", "high", "quiet"]
        
        # Track power state (Fujitsu has separate power on flag)
        self.power_on = False
        
        _LOGGER.debug("Fujitsu General Protocol initialized")
    
    def _set_nibble(self, message, nibble, value):
        """Set a nibble (4 bits) in the message array."""
        # Nibbles are stored in bytes: nibble 0-1 in byte 0, nibble 2-3 in byte 1, etc.
        byte_index = nibble // 2
        shift = 0 if (nibble % 2) else 4
        mask = 0x0F << shift
        
        # Clear the nibble first
        message[byte_index] &= ~mask
        # Set the new value
        message[byte_index] |= (value & 0x0F) << shift
    
    def _get_nibble(self, message, nibble):
        """Get a nibble (4 bits) from the message array."""
        byte_index = nibble // 2
        shift = 0 if (nibble % 2) else 4
        return (message[byte_index] >> shift) & 0x0F

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Fujitsu IR code for climate command."""
        _LOGGER.debug(f"Generating Fujitsu IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        # Handle OFF mode separately
        if hvac_mode == "off":
            return self._generate_off_message()
        
        # Generate state message
        return self._generate_state_message(hvac_mode, target_temp, fan_mode, swing_mode)
    
    def _generate_state_message(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate state message (16 bytes)."""
        remote_state = [0] * self.STATE_MESSAGE_LENGTH
        
        # Common message header
        remote_state[0] = self.COMMON_BYTE0
        remote_state[1] = self.COMMON_BYTE1
        remote_state[2] = self.COMMON_BYTE2
        remote_state[3] = self.COMMON_BYTE3
        remote_state[4] = self.COMMON_BYTE4
        remote_state[5] = self.MESSAGE_TYPE_STATE
        remote_state[6] = self.STATE_HEADER_BYTE0
        remote_state[7] = self.STATE_HEADER_BYTE1
        
        # Unknown fixed values
        remote_state[14] = self.STATE_FOOTER_BYTE0
        
        # Set temperature
        temp_val = max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp))
        temp_offset = int(temp_val) - self.TEMP_MIN
        self._set_nibble(remote_state, self.TEMPERATURE_NIBBLE, temp_offset)
        
        # Set power on if coming from OFF state
        if not self.power_on:
            self._set_nibble(remote_state, self.POWER_ON_NIBBLE, self.POWER_ON)
        
        # Set mode
        mode_value = self._hvac_mode_to_fujitsu(hvac_mode)
        self._set_nibble(remote_state, self.MODE_NIBBLE, mode_value)
        
        # Set fan
        fan_value = self._fan_mode_to_fujitsu(fan_mode)
        self._set_nibble(remote_state, self.FAN_NIBBLE, fan_value)
        
        # Set swing
        swing_value = self._swing_mode_to_fujitsu(swing_mode)
        self._set_nibble(remote_state, self.SWING_NIBBLE, swing_value)
        
        # Calculate checksum
        remote_state[self.STATE_MESSAGE_LENGTH - 1] = self._checksum_state(remote_state)
        
        # Update power state
        self.power_on = True
        
        _LOGGER.debug(f"Fujitsu state message: {[f'0x{x:02X}' for x in remote_state]}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(remote_state, self.STATE_MESSAGE_LENGTH)
        
        return pulses
    
    def _generate_off_message(self):
        """Generate OFF message (7 bytes)."""
        remote_state = [0] * self.UTIL_MESSAGE_LENGTH
        
        # Common header
        remote_state[0] = self.COMMON_BYTE0
        remote_state[1] = self.COMMON_BYTE1
        remote_state[2] = self.COMMON_BYTE2
        remote_state[3] = self.COMMON_BYTE3
        remote_state[4] = self.COMMON_BYTE4
        remote_state[5] = self.MESSAGE_TYPE_OFF
        
        # Calculate checksum
        remote_state[6] = self._checksum_util(remote_state)
        
        # Update power state
        self.power_on = False
        
        _LOGGER.debug(f"Fujitsu OFF message: {[f'0x{x:02X}' for x in remote_state]}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(remote_state, self.UTIL_MESSAGE_LENGTH)
        
        return pulses
    
    def _hvac_mode_to_fujitsu(self, hvac_mode):
        """Convert HVAC mode to Fujitsu mode value."""
        if hvac_mode == "cool":
            return self.MODE_COOL
        elif hvac_mode == "heat":
            return self.MODE_HEAT
        elif hvac_mode == "dry":
            return self.MODE_DRY
        elif hvac_mode == "fan_only":
            return self.MODE_FAN
        elif hvac_mode in ["auto", "heat_cool"]:
            return self.MODE_AUTO
        else:
            return self.MODE_AUTO
    
    def _fan_mode_to_fujitsu(self, fan_mode):
        """Convert fan mode to Fujitsu fan value."""
        if fan_mode == "high":
            return self.FAN_HIGH
        elif fan_mode == "medium":
            return self.FAN_MEDIUM
        elif fan_mode == "low":
            return self.FAN_LOW
        elif fan_mode == "quiet":
            return self.FAN_SILENT
        else:  # auto
            return self.FAN_AUTO
    
    def _swing_mode_to_fujitsu(self, swing_mode):
        """Convert swing mode to Fujitsu swing value."""
        if swing_mode == "vertical":
            return self.SWING_VERTICAL
        elif swing_mode == "horizontal":
            return self.SWING_HORIZONTAL
        elif swing_mode == "both":
            return self.SWING_BOTH
        else:  # off
            return self.SWING_NONE
    
    def _checksum_state(self, message):
        """Calculate checksum for state message."""
        checksum = 0
        # Sum bytes 7 to 14 (0-indexed, so 7 to STATE_MESSAGE_LENGTH-2)
        for i in range(7, self.STATE_MESSAGE_LENGTH - 1):
            checksum += message[i]
        return (256 - checksum) & 0xFF
    
    def _checksum_util(self, message):
        """Calculate checksum for utility message."""
        return (255 - message[5]) & 0xFF
    
    def _encode_to_pulses(self, message, length):
        """Convert message to IR pulse sequence (LSB first)."""
        pulses = []
        
        # Header
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        
        # Data bytes (LSB FIRST - Fujitsu specific)
        for i in range(length):
            byte = message[i]
            for mask in [1, 2, 4, 8, 16, 32, 64, 128]:  # Still MSB first for bit testing
                # But we need to send LSB first, so we test bits in LSB order
                # Actually, looking at the C++ code: it writes from right to left (LSB first)
                # So we need to iterate bit masks in LSB order: 1, 2, 4, 8, 16, 32, 64, 128
                # Wait, that's what we're already doing... Let me re-examine
                
                # The C++ code uses: for (mask = 0b00000001; mask > 0; mask <<= 1)
                # That's LSB to MSB. So we need: 1, 2, 4, 8, 16, 32, 64, 128
                # Yes, that's correct.
                pulses.append(self.BIT_MARK)
                if byte & mask:
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Footer
        pulses.extend([self.TRL_MARK, self.TRL_SPACE])
        
        return pulses