# toshiba.py
"""Toshiba Climate IR Protocol."""
import logging
from enum import Enum

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class ToshibaModel(Enum):
    """Toshiba model types."""
    GENERIC = 0           # Temperature range 17 to 30
    RAC_PT1411HWRU_C = 1  # Temperature range 16 to 30 (Celsius)
    RAC_PT1411HWRU_F = 2  # Temperature range 16 to 30 (Fahrenheit conversion)
    RAS_2819T = 3         # RAS-2819T protocol, temperature range 18 to 30


class ToshibaProtocol(ClimateIRProtocol):
    """
    Toshiba Klima IR Protokolü
    ESPHome climate_ir_toshiba.h/cpp referans alınarak yazılmıştır
    """
    
    # Temperature ranges by model
    TEMP_MIN_GENERIC = 17
    TEMP_MAX_GENERIC = 30
    TEMP_MIN_RAC_PT1411HWRU = 16
    TEMP_MAX_RAC_PT1411HWRU = 30
    TEMP_MIN_RAS_2819T = 18
    TEMP_MAX_RAS_2819T = 30
    
    # IR timing parameters (microseconds)
    HEADER_MARK = 4380
    HEADER_SPACE = 4370
    GAP_SPACE = 5480
    PACKET_SPACE = 10500
    BIT_MARK = 540
    ZERO_SPACE = 540
    ONE_SPACE = 1620
    CARRIER_FREQUENCY = 38000
    HEADER_LENGTH = 4
    
    # Generic Toshiba commands
    COMMAND_DEFAULT = 0x01
    COMMAND_POWER = 0x08
    COMMAND_MOTION = 0x02
    
    # Modes
    MODE_AUTO = 0x00
    MODE_COOL = 0x01
    MODE_DRY = 0x02
    MODE_HEAT = 0x03
    MODE_FAN_ONLY = 0x04
    MODE_OFF = 0x07
    
    # Fan speeds
    FAN_SPEED_AUTO = 0x00
    FAN_SPEED_QUIET = 0x20
    FAN_SPEED_1 = 0x40
    FAN_SPEED_2 = 0x60
    FAN_SPEED_3 = 0x80
    FAN_SPEED_4 = 0xa0
    FAN_SPEED_5 = 0xc0
    
    # Power settings
    POWER_HIGH = 0x01
    POWER_ECO = 0x03
    
    # Motion/Swing
    MOTION_SWING = 0x04
    MOTION_FIX = 0x00
    
    # RAC-PT1411HWRU specific constants
    RAC_PT1411HWRU_MESSAGE_HEADER0 = 0xB2
    RAC_PT1411HWRU_MESSAGE_HEADER1 = 0xD5
    RAC_PT1411HWRU_MESSAGE_LENGTH = 6
    
    # RAC-PT1411HWRU flags
    RAC_PT1411HWRU_FLAG_FAH = 0x01    # Fahrenheit flag
    RAC_PT1411HWRU_FLAG_FRAC = 0x20   # Fractional flag
    RAC_PT1411HWRU_FLAG_NEG = 0x10    # Negative flag
    RAC_PT1411HWRU_FLAG_MASK = 0x0F   # Temperature code mask
    
    # RAC-PT1411HWRU swing commands
    RAC_PT1411HWRU_SWING_VERTICAL = [0xB9, 0x46, 0xF5, 0x0A, 0x04, 0xFB]
    RAC_PT1411HWRU_SWING_OFF = [0xB9, 0x46, 0xF5, 0x0A, 0x05, 0xFA]
    
    # RAC-PT1411HWRU fan speed structures
    RAC_PT1411HWRU_FAN_OFF = 0x7B
    RAC_PT1411HWRU_FAN_AUTO = (0xBF, 0x66)
    RAC_PT1411HWRU_FAN_LOW = (0x9F, 0x28)
    RAC_PT1411HWRU_FAN_MED = (0x5F, 0x3C)
    RAC_PT1411HWRU_FAN_HIGH = (0x3F, 0x64)
    RAC_PT1411HWRU_NO_FAN = (0x1F, 0x65)  # For AUTO/DRY modes
    
    # RAC-PT1411HWRU modes
    RAC_PT1411HWRU_MODE_AUTO = 0x08
    RAC_PT1411HWRU_MODE_COOL = 0x00
    RAC_PT1411HWRU_MODE_DRY = 0x04
    RAC_PT1411HWRU_MODE_FAN = 0x04
    RAC_PT1411HWRU_MODE_HEAT = 0x0C
    RAC_PT1411HWRU_MODE_OFF = 0x00
    
    # RAC-PT1411HWRU fan-only temperature
    RAC_PT1411HWRU_TEMPERATURE_FAN_ONLY = 0x0E
    
    # RAC-PT1411HWRU temperature codes (Celsius, Gray code)
    RAC_PT1411HWRU_TEMPERATURE_C = [
        0x10, 0x00, 0x01, 0x03, 0x02, 0x06, 0x07, 0x05,
        0x04, 0x0C, 0x0D, 0x09, 0x08, 0x0A, 0x0B
    ]  # 16-30°C
    
    # RAC-PT1411HWRU temperature codes (Fahrenheit)
    RAC_PT1411HWRU_TEMPERATURE_F = [
        0x10, 0x30, 0x00, 0x20, 0x01, 0x21, 0x03, 0x23, 0x02,
        0x22, 0x06, 0x26, 0x07, 0x05, 0x25, 0x04, 0x24, 0x0C,
        0x2C, 0x0D, 0x2D, 0x09, 0x08, 0x28, 0x0A, 0x2A, 0x0B
    ]  # 60-86°F
    
    # RAS-2819T constants
    RAS_2819T_HEADER1 = 0xC23D
    RAS_2819T_HEADER2 = 0xD5
    RAS_2819T_MESSAGE_LENGTH = 6
    
    # RAS-2819T fan speed codes (first packet bytes 2-3)
    RAS_2819T_FAN_AUTO = 0xBF40
    RAS_2819T_FAN_QUIET = 0xFF00
    RAS_2819T_FAN_LOW = 0x9F60
    RAS_2819T_FAN_MEDIUM = 0x5FA0
    RAS_2819T_FAN_HIGH = 0x3FC0
    
    # RAS-2819T fan speed codes (second packet byte 1)
    RAS_2819T_FAN2_AUTO = 0x66
    RAS_2819T_FAN2_QUIET = 0x01
    RAS_2819T_FAN2_LOW = 0x28
    RAS_2819T_FAN2_MEDIUM = 0x3C
    RAS_2819T_FAN2_HIGH = 0x50
    
    # RAS-2819T special commands
    RAS_2819T_SWING_TOGGLE = 0xC23D6B94E01F
    RAS_2819T_POWER_OFF_COMMAND = 0xC23D7B84E01F
    
    # RAS-2819T temperature codes (18-30°C)
    RAS_2819T_TEMP_CODES = [
        0x10,  # 18°C
        0x30,  # 19°C
        0x20,  # 20°C
        0x60,  # 21°C
        0x70,  # 22°C
        0x50,  # 23°C
        0x40,  # 24°C
        0xC0,  # 25°C
        0xD0,  # 26°C
        0x90,  # 27°C
        0x80,  # 28°C
        0xA0,  # 29°C
        0xB0   # 30°C
    ]
    
    def __init__(self, model="generic"):
        super().__init__()
        
        # Set model type
        if model == "rac_pt1411hwru_c":
            self.model = ToshibaModel.RAC_PT1411HWRU_C
            self.TEMP_MIN = self.TEMP_MIN_RAC_PT1411HWRU
            self.TEMP_MAX = self.TEMP_MAX_RAC_PT1411HWRU
        elif model == "rac_pt1411hwru_f":
            self.model = ToshibaModel.RAC_PT1411HWRU_F
            self.TEMP_MIN = self.TEMP_MIN_RAC_PT1411HWRU
            self.TEMP_MAX = self.TEMP_MAX_RAC_PT1411HWRU
        elif model == "ras_2819t":
            self.model = ToshibaModel.RAS_2819T
            self.TEMP_MIN = self.TEMP_MIN_RAS_2819T
            self.TEMP_MAX = self.TEMP_MAX_RAS_2819T
        else:
            self.model = ToshibaModel.GENERIC
            self.TEMP_MIN = self.TEMP_MIN_GENERIC
            self.TEMP_MAX = self.TEMP_MAX_GENERIC
        
        # Update temperature range properties
        self._temperature_min = self.TEMP_MIN
        self._temperature_max = self.TEMP_MAX
        
        # State tracking for RAS-2819T swing optimization
        self.last_swing_mode = "off"
        self.last_hvac_mode = "off"
        self.last_fan_mode = "auto"
        self.last_target_temperature = 24.0
        
        # Configure supported features based on model
        if self.model == ToshibaModel.RAS_2819T:
            self.supported_swing_modes = ["off", "vertical"]
            self.supported_fan_modes = ["auto", "low", "medium", "high", "quiet"]
        else:
            self.supported_swing_modes = ["off", "vertical"]
            self.supported_fan_modes = ["auto", "low", "medium", "high"]
        
        _LOGGER.debug(f"Toshiba Protocol initialized for model: {self.model}")

    @property
    def temperature_min(self):
        return self._temperature_min
        
    @property 
    def temperature_max(self):
        return self._temperature_max

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Toshiba IR code for climate command."""
        _LOGGER.debug(f"Generating Toshiba IR code: model={self.model}, mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        # Check if we should send just swing toggle for RAS-2819T
        swing_changed = (swing_mode != self.last_swing_mode)
        mode_changed = (hvac_mode != self.last_hvac_mode)
        fan_changed = (fan_mode != self.last_fan_mode)
        temp_changed = abs(target_temp - self.last_target_temperature) > 0.1
        
        # For RAS-2819T, if ONLY swing changed, send swing toggle command
        if (self.model == ToshibaModel.RAS_2819T and 
            swing_changed and not mode_changed and not fan_changed and not temp_changed):
            _LOGGER.debug("Sending RAS-2819T swing-only toggle command")
            return self._generate_ras_2819t_swing_toggle()
        
        # Update state tracking
        self.last_swing_mode = swing_mode
        self.last_hvac_mode = hvac_mode
        self.last_fan_mode = fan_mode
        self.last_target_temperature = target_temp
        
        # Generate based on model
        if self.model == ToshibaModel.GENERIC:
            return self._generate_generic_code(hvac_mode, target_temp, fan_mode, swing_mode)
        elif self.model in [ToshibaModel.RAC_PT1411HWRU_C, ToshibaModel.RAC_PT1411HWRU_F]:
            return self._generate_rac_pt1411hwru_code(hvac_mode, target_temp, fan_mode, swing_mode)
        elif self.model == ToshibaModel.RAS_2819T:
            return self._generate_ras_2819t_code(hvac_mode, target_temp, fan_mode, swing_mode)
        else:
            return self._generate_generic_code(hvac_mode, target_temp, fan_mode, swing_mode)

    def _generate_generic_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate generic Toshiba IR code."""
        message = [0] * 9
        
        # Header
        message[0] = 0xf2
        message[1] = 0x0d
        
        # Message length
        message[2] = 3  # message_length - 6
        
        # First checksum
        message[3] = message[0] ^ message[1] ^ message[2]
        
        # Command
        message[4] = self.COMMAND_DEFAULT
        
        # Temperature (17-30°C range)
        temp_val = int(max(self.TEMP_MIN_GENERIC, min(self.TEMP_MAX_GENERIC, target_temp)))
        message[5] = (temp_val - self.TEMP_MIN_GENERIC) << 4
        
        # Mode and fan
        mode_byte = 0
        if hvac_mode == "off":
            mode_byte = self.MODE_OFF
        elif hvac_mode == "heat":
            mode_byte = self.MODE_HEAT
        elif hvac_mode == "cool":
            mode_byte = self.MODE_COOL
        elif hvac_mode == "dry":
            mode_byte = self.MODE_DRY
        elif hvac_mode == "fan_only":
            mode_byte = self.MODE_FAN_ONLY
        else:  # auto or heat_cool
            mode_byte = self.MODE_AUTO
        
        fan_byte = 0
        if fan_mode == "quiet":
            fan_byte = self.FAN_SPEED_QUIET
        elif fan_mode == "low":
            fan_byte = self.FAN_SPEED_1
        elif fan_mode == "medium":
            fan_byte = self.FAN_SPEED_3
        elif fan_mode == "high":
            fan_byte = self.FAN_SPEED_5
        else:  # auto
            fan_byte = self.FAN_SPEED_AUTO
        
        message[6] = fan_byte | mode_byte
        
        # Zero byte
        message[7] = 0x00
        
        # Final checksum (XOR of bytes 4-7)
        for i in range(4, 8):
            message[8] ^= message[i]
        
        _LOGGER.debug(f"Generic Toshiba message: {[f'0x{x:02X}' for x in message]}")
        
        # Convert to pulses
        pulses = self._encode_to_pulses(message, 9, repeat=1)
        
        # Add swing packet if needed (for generic with swing)
        if swing_mode == "vertical":
            swing_pulses = self._generate_generic_swing()
            pulses.extend(swing_pulses)
        
        return pulses

    def _generate_generic_swing(self):
        """Generate generic swing command (not fully implemented in ESPHome)."""
        # Generic swing not fully documented, return empty for now
        return []

    def _generate_rac_pt1411hwru_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate RAC-PT1411HWRU IR code."""
        # This protocol has two parts: main command and swing command
        pulses = []
        
        # Part 1: Main climate command
        main_message = self._build_rac_pt1411hwru_main(hvac_mode, target_temp, fan_mode)
        if main_message:
            pulses.extend(self._encode_to_pulses(main_message[:6], 6, repeat=1))
        
        # Part 2: Second block (if not OFF mode)
        if hvac_mode != "off" and len(main_message) > 6:
            pulses.extend(self._encode_to_pulses(main_message[6:12], 6, repeat=0))
        
        # Part 3: Swing command
        swing_pulses = self._generate_rac_pt1411hwru_swing(swing_mode)
        if swing_pulses:
            # Add gap before swing command
            pulses.extend([self.BIT_MARK, self.PACKET_SPACE])
            pulses.extend(swing_pulses)
            pulses.extend([self.BIT_MARK, self.PACKET_SPACE])
        
        return pulses

    def _build_rac_pt1411hwru_main(self, hvac_mode, target_temp, fan_mode):
        """Build RAC-PT1411HWRU main message (12 bytes)."""
        message = [0] * 12
        temperature = max(self.TEMP_MIN_RAC_PT1411HWRU, min(self.TEMP_MAX_RAC_PT1411HWRU, target_temp))
        
        # Byte 0: Header upper (0xB2)
        message[0] = self.RAC_PT1411HWRU_MESSAGE_HEADER0
        # Byte 1: Header lower (0x4D) - complement of byte 0
        message[1] = ~message[0] & 0xFF
        
        # Byte 2: Fan speed upper / power state
        if hvac_mode == "off":
            message[2] = self.RAC_PT1411HWRU_FAN_OFF
        elif hvac_mode in ["auto", "heat_cool", "dry"]:
            message[2] = self.RAC_PT1411HWRU_NO_FAN[0]
            message[7] = self.RAC_PT1411HWRU_NO_FAN[1]
        else:
            if fan_mode == "low":
                message[2] = self.RAC_PT1411HWRU_FAN_LOW[0]
                message[7] = self.RAC_PT1411HWRU_FAN_LOW[1]
            elif fan_mode == "medium":
                message[2] = self.RAC_PT1411HWRU_FAN_MED[0]
                message[7] = self.RAC_PT1411HWRU_FAN_MED[1]
            elif fan_mode == "high":
                message[2] = self.RAC_PT1411HWRU_FAN_HIGH[0]
                message[7] = self.RAC_PT1411HWRU_FAN_HIGH[1]
            else:  # auto
                message[2] = self.RAC_PT1411HWRU_FAN_AUTO[0]
                message[7] = self.RAC_PT1411HWRU_FAN_AUTO[1]
        
        # Byte 3: Complement of byte 2
        message[3] = ~message[2] & 0xFF
        
        # Byte 4: Temperature (upper 4 bits) and Mode (lower 4 bits)
        temp_index = int(temperature - self.TEMP_MIN_RAC_PT1411HWRU)
        
        if self.model == ToshibaModel.RAC_PT1411HWRU_F:
            # Convert to Fahrenheit
            temperature_f = (temperature * 1.8) + 32
            temp_index = int(temperature_f - 60)  # 60°F is minimum
            
            if temp_index < len(self.RAC_PT1411HWRU_TEMPERATURE_F):
                temp_code = self.RAC_PT1411HWRU_TEMPERATURE_F[temp_index]
                message[9] |= self.RAC_PT1411HWRU_FLAG_FAH
            else:
                temp_code = 0x10  # Default
        else:
            if temp_index < len(self.RAC_PT1411HWRU_TEMPERATURE_C):
                temp_code = self.RAC_PT1411HWRU_TEMPERATURE_C[temp_index]
            else:
                temp_code = 0x10  # Default
        
        # Check for special flags
        if temp_code & self.RAC_PT1411HWRU_FLAG_FRAC:
            message[8] |= self.RAC_PT1411HWRU_FLAG_FRAC
        if temp_code & self.RAC_PT1411HWRU_FLAG_NEG:
            message[9] |= self.RAC_PT1411HWRU_FLAG_NEG
        
        # Set temperature bits (mask out flags)
        temp_bits = (temp_code & self.RAC_PT1411HWRU_FLAG_MASK) << 4
        
        # Set mode bits
        mode_bits = 0
        if hvac_mode == "heat":
            mode_bits = self.RAC_PT1411HWRU_MODE_HEAT
        elif hvac_mode == "cool":
            if hvac_mode == "off" or (temp_bits >> 4) == self.RAC_PT1411HWRU_TEMPERATURE_FAN_ONLY:
                mode_bits = self.RAC_PT1411HWRU_MODE_OFF
            else:
                mode_bits = self.RAC_PT1411HWRU_MODE_COOL
        elif hvac_mode == "dry":
            mode_bits = self.RAC_PT1411HWRU_MODE_DRY
        elif hvac_mode == "fan_only":
            mode_bits = self.RAC_PT1411HWRU_MODE_FAN
            temp_bits = self.RAC_PT1411HWRU_TEMPERATURE_FAN_ONLY << 4
        else:  # auto or heat_cool
            mode_bits = self.RAC_PT1411HWRU_MODE_AUTO
        
        message[4] = temp_bits | mode_bits
        
        # Byte 5: Complement of byte 4
        message[5] = ~message[4] & 0xFF
        
        # If not OFF mode, add second block
        if hvac_mode != "off":
            # Byte 6: Second header (0xD5)
            message[6] = self.RAC_PT1411HWRU_MESSAGE_HEADER1
            # Byte 7: Fan speed part 2 (already set)
            # Byte 8: Flags (already set)
            # Byte 9: More flags (already set)
            # Byte 10: 0x00
            message[10] = 0x00
            # Byte 11: Checksum (bytes 6-10)
            for i in range(6, 11):
                message[11] = (message[11] + message[i]) & 0xFF
        
        return message

    def _generate_rac_pt1411hwru_swing(self, swing_mode):
        """Generate RAC-PT1411HWRU swing command."""
        if swing_mode == "vertical":
            return self._encode_to_pulses(self.RAC_PT1411HWRU_SWING_VERTICAL, 6, repeat=1)
        else:
            return self._encode_to_pulses(self.RAC_PT1411HWRU_SWING_OFF, 6, repeat=1)

    def _generate_ras_2819t_swing_toggle(self):
        """Generate RAS-2819T swing toggle command."""
        # Convert 48-bit command to 6 bytes
        swing_command = self.RAS_2819T_SWING_TOGGLE
        message = []
        
        for i in range(5, -1, -1):
            message.append((swing_command >> (i * 8)) & 0xFF)
        
        _LOGGER.debug(f"RAS-2819T swing toggle: {[f'0x{x:02X}' for x in message]}")
        
        return self._encode_to_pulses(message, 6, repeat=1)

    def _generate_ras_2819t_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate RAS-2819T IR code (two packets)."""
        pulses = []
        
        # First packet
        message1 = self._build_ras_2819t_packet1(hvac_mode, target_temp, fan_mode)
        if message1:
            pulses.extend(self._encode_to_pulses(message1, 6, repeat=1))
        
        # Second packet (if not OFF mode)
        if hvac_mode != "off":
            message2 = self._build_ras_2819t_packet2(hvac_mode, fan_mode)
            if message2:
                pulses.extend(self._encode_to_pulses(message2, 6, repeat=0))
        
        return pulses

    def _build_ras_2819t_packet1(self, hvac_mode, target_temp, fan_mode):
        """Build RAS-2819T first packet."""
        message = [0] * 6
        
        # Handle OFF mode
        if hvac_mode == "off":
            # Use power off command
            power_off = self.RAS_2819T_POWER_OFF_COMMAND
            for i in range(6):
                message[i] = (power_off >> ((5 - i) * 8)) & 0xFF
            return message
        
        # Byte 0-1: Header (0xC23D)
        message[0] = (self.RAS_2819T_HEADER1 >> 8) & 0xFF
        message[1] = self.RAS_2819T_HEADER1 & 0xFF
        
        # Get temperature code
        temp_code = self._get_ras_2819t_temp_code(target_temp)
        
        # Get fan code
        fan_code = self._get_ras_2819t_fan_code(fan_mode)
        
        # Dry mode forces AUTO fan
        effective_fan_mode = fan_mode
        if hvac_mode == "dry":
            effective_fan_mode = "auto"
            fan_code = self.RAS_2819T_FAN_AUTO
        
        # Bytes 2-3: Fan speed
        message[2] = (fan_code >> 8) & 0xFF
        message[3] = fan_code & 0xFF
        
        # Bytes 4-5: Temperature with mode offset and complement
        if hvac_mode == "cool":
            message[4] = temp_code
        elif hvac_mode == "heat":
            message[4] = temp_code | 0x0C  # Heat offset
        elif hvac_mode in ["auto", "heat_cool"]:
            message[4] = temp_code | 0x08  # Auto offset
        elif hvac_mode == "dry":
            message[4] = temp_code | 0x24  # Dry offset
        elif hvac_mode == "fan_only":
            message[4] = 0xE4  # Fan-only temperature code
        else:
            message[4] = temp_code
        
        # Byte 5: Complement of byte 4
        message[5] = ~message[4] & 0xFF
        
        _LOGGER.debug(f"RAS-2819T packet1: {[f'0x{x:02X}' for x in message]}")
        return message

    def _build_ras_2819t_packet2(self, hvac_mode, fan_mode):
        """Build RAS-2819T second packet."""
        message = [0] * 6
        
        # Byte 0: Header (0xD5)
        message[0] = self.RAS_2819T_HEADER2
        
        # Get fan byte and suffix
        fan2_byte, suffix = self._get_ras_2819t_second_packet_codes(fan_mode, hvac_mode)
        
        # Dry/Auto modes use fixed values
        if hvac_mode in ["auto", "heat_cool", "dry"]:
            message[1] = 0x65  # AUTO_DRY_FAN_BYTE
            message[2] = 0x00
            message[3] = 0x00
            message[4] = 0x00
            message[5] = 0x3A if hvac_mode == "dry" else 0x3A  # AUTO_DRY_SUFFIX
        else:
            message[1] = fan2_byte
            message[2] = 0x00
            message[3] = suffix[0]
            message[4] = suffix[1]
            message[5] = suffix[2]
        
        _LOGGER.debug(f"RAS-2819T packet2: {[f'0x{x:02X}' for x in message]}")
        return message

    def _get_ras_2819t_temp_code(self, temperature):
        """Get RAS-2819T temperature code for given temperature."""
        temp_index = int(temperature) - self.TEMP_MIN_RAS_2819T
        if 0 <= temp_index < len(self.RAS_2819T_TEMP_CODES):
            return self.RAS_2819T_TEMP_CODES[temp_index]
        return 0x40  # Default to 24°C

    def _get_ras_2819t_fan_code(self, fan_mode):
        """Get RAS-2819T fan code for given fan mode."""
        if fan_mode == "quiet":
            return self.RAS_2819T_FAN_QUIET
        elif fan_mode == "low":
            return self.RAS_2819T_FAN_LOW
        elif fan_mode == "medium":
            return self.RAS_2819T_FAN_MEDIUM
        elif fan_mode == "high":
            return self.RAS_2819T_FAN_HIGH
        else:  # auto
            return self.RAS_2819T_FAN_AUTO

    def _get_ras_2819t_second_packet_codes(self, fan_mode, hvac_mode):
        """Get RAS-2819T second packet fan byte and suffix."""
        # Default suffix for non-heat modes
        suffix = (0x00, 0x02, 0x3D)  # AUTO suffix
        
        if fan_mode == "quiet":
            fan_byte = self.RAS_2819T_FAN2_QUIET
            suffix = (0x00, 0x02, 0xD8)
        elif fan_mode == "low":
            fan_byte = self.RAS_2819T_FAN2_LOW
            suffix = (0x00, 0x02, 0xFF)
        elif fan_mode == "medium":
            fan_byte = self.RAS_2819T_FAN2_MEDIUM
            suffix = (0x00, 0x02, 0x13)
        elif fan_mode == "high":
            fan_byte = self.RAS_2819T_FAN2_HIGH
            suffix = (0x00, 0x02, 0x27)
        else:  # auto
            fan_byte = self.RAS_2819T_FAN2_AUTO
        
        # Heat mode has different suffix
        if hvac_mode == "heat":
            suffix = (0x00, 0x00, 0x3B)
        
        return fan_byte, suffix

    def _encode_to_pulses(self, message, nbytes, repeat=1):
        """Convert message to IR pulse sequence."""
        pulses = []
        
        for copy in range(repeat + 1):
            # Header
            pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
            
            # Data bytes (MSB first)
            for byte in message[:nbytes]:
                for bit in range(7, -1, -1):  # 7 to 0 (MSB first)
                    pulses.append(self.BIT_MARK)
                    if byte & (1 << bit):
                        pulses.append(self.ONE_SPACE)
                    else:
                        pulses.append(self.ZERO_SPACE)
            
            # Gap between repeats
            pulses.extend([self.BIT_MARK, self.GAP_SPACE])
        
        return pulses