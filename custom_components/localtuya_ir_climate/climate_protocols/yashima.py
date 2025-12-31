"""Yashima Climate IR Protocol."""
import logging

# Home Assistant versiyonuna göre import
try:
    from homeassistant.components.climate import HVACMode, FanMode, SwingMode
except ImportError:
    # Eski versiyonlar için enum benzeri class'lar
    class HVACMode:
        OFF = "off"
        HEAT = "heat"
        COOL = "cool"
        HEAT_COOL = "heat_cool"
        AUTO = "auto"
        DRY = "dry"
        FAN_ONLY = "fan_only"
    
    class FanMode:
        AUTO = "auto"
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
    
    class SwingMode:
        OFF = "off"
        VERTICAL = "vertical"

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class YashimaProtocol(ClimateIRProtocol):
    """
    Yashima Klima IR Protokolü
    ESPHome yashima.h/cpp referans alınarak yazılmıştır
    """
    
    TEMP_MIN = 16  # Celsius
    TEMP_MAX = 30  # Celsius
    TEMP_STEP = 1
    
    # State length
    STATE_LENGTH = 9
    BITS = STATE_LENGTH * 8
    
    # Byte 0: Mode settings
    BASE_BYTE0 = 0b1110  # 4 bits
    
    MODE_HEAT_BYTE0 = 0b00100000
    MODE_DRY_BYTE0 = 0b01100000
    MODE_COOL_BYTE0 = 0b11100000
    MODE_FAN_BYTE0 = 0b10100000
    MODE_AUTO_BYTE0 = 0b11100000
    MODE_OFF_BYTE0 = 0b11110000
    
    # Byte 1: Temperature mapping
    BASE_BYTE1 = 0b11  # 2 bits
    
    # Temperature mapping (16-30°C)
    TEMP_MAP_BYTE1 = [
        0b01100100,  # 16C
        0b10100100,  # 17C
        0b00100100,  # 18C
        0b11000100,  # 19C
        0b01000100,  # 20C
        0b10000100,  # 21C
        0b00000100,  # 22C
        0b11111000,  # 23C
        0b01111000,  # 24C
        0b10111000,  # 25C
        0b00111000,  # 26C
        0b11011000,  # 27C
        0b01011000,  # 28C
        0b10011000,  # 29C
        0b00011000,  # 30C
    ]
    
    # Byte 2: Fan speed
    BASE_BYTE2 = 0b111111  # 6 bits
    
    FAN_AUTO_BYTE2 = 0b11000000
    FAN_LOW_BYTE2 = 0b00000000
    FAN_MEDIUM_BYTE2 = 0b10000000
    FAN_HIGH_BYTE2 = 0b01000000
    
    # Byte 3-4: Base values
    BASE_BYTE3 = 0b11111111
    BASE_BYTE4 = 0b11
    
    # Byte 5: Mode (second part)
    BASE_BYTE5 = 0b11111  # 5 bits
    
    MODE_HEAT_BYTE5 = 0b00000000
    MODE_DRY_BYTE5 = 0b00000000
    MODE_FAN_BYTE5 = 0b00000000
    MODE_AUTO_BYTE5 = 0b00000000
    MODE_COOL_BYTE5 = 0b10000000
    MODE_OFF_BYTE5 = 0b10000000
    
    # Byte 6-8: Base values
    BASE_BYTE6 = 0b11111111
    BASE_BYTE7 = 0b11111111
    BASE_BYTE8 = 0b11001111
    
    # IR Timing parameters (microseconds)
    HEADER_MARK = 9035
    HEADER_SPACE = 4517
    BIT_MARK = 667
    ONE_SPACE = 517
    ZERO_SPACE = 1543
    GAP = 4517  # Same as HEADER_SPACE
    
    def __init__(self):
        super().__init__()
        
        # Yashima supports only specific modes
        self.supported_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.HEAT_COOL,  # Auto mode
        ]
        
        # Yashima supports AUTO fan only based on ESPHome code
        self.supported_fan_modes = [
            FanMode.AUTO,
        ]
        
        # No swing support
        self.supported_swing_modes = []
        
        # State tracking
        self.supports_cool = True
        self.supports_heat = True
        
        _LOGGER.debug("Yashima Protocol initialized")
        
    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Yashima IR code for climate command."""
        _LOGGER.debug(f"Generating Yashima IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}")
        
        # Initialize remote state with all zeros
        remote_state = bytearray(self.STATE_LENGTH)
        
        # Set base values
        remote_state[0] = self.BASE_BYTE0
        remote_state[1] = self.BASE_BYTE1
        remote_state[2] = self.BASE_BYTE2
        remote_state[3] = self.BASE_BYTE3
        remote_state[4] = self.BASE_BYTE4
        remote_state[5] = self.BASE_BYTE5
        remote_state[6] = self.BASE_BYTE6
        remote_state[7] = self.BASE_BYTE7
        remote_state[8] = self.BASE_BYTE8
        
        # Set mode (Byte 0 and Byte 5)
        if hvac_mode == HVACMode.OFF:
            remote_state[0] |= self.MODE_OFF_BYTE0
            remote_state[5] |= self.MODE_OFF_BYTE5
        elif hvac_mode == HVACMode.HEAT:
            remote_state[0] |= self.MODE_HEAT_BYTE0
            remote_state[5] |= self.MODE_HEAT_BYTE5
        elif hvac_mode == HVACMode.COOL:
            remote_state[0] |= self.MODE_COOL_BYTE0
            remote_state[5] |= self.MODE_COOL_BYTE5
        elif hvac_mode == HVACMode.HEAT_COOL:  # Auto mode
            remote_state[0] |= self.MODE_AUTO_BYTE0
            remote_state[5] |= self.MODE_AUTO_BYTE5
        elif hvac_mode == HVACMode.DRY:
            # Note: ESPHome doesn't support DRY mode for Yashima
            # but we'll map it if needed
            remote_state[0] |= self.MODE_DRY_BYTE0
            remote_state[5] |= self.MODE_DRY_BYTE5
        elif hvac_mode == HVACMode.FAN_ONLY:
            # Note: ESPHome doesn't support FAN_ONLY for Yashima
            remote_state[0] |= self.MODE_FAN_BYTE0
            remote_state[5] |= self.MODE_FAN_BYTE5
        else:
            # Default to OFF for unknown modes
            remote_state[0] |= self.MODE_OFF_BYTE0
            remote_state[5] |= self.MODE_OFF_BYTE5
        
        # Set fan speed (only AUTO supported in ESPHome)
        # But we can implement full support
        if hvac_mode != HVACMode.OFF:
            if fan_mode == FanMode.LOW:
                remote_state[2] |= self.FAN_LOW_BYTE2
            elif fan_mode == FanMode.MEDIUM:
                remote_state[2] |= self.FAN_MEDIUM_BYTE2
            elif fan_mode == FanMode.HIGH:
                remote_state[2] |= self.FAN_HIGH_BYTE2
            else:  # AUTO or unknown
                remote_state[2] |= self.FAN_AUTO_BYTE2
        else:
            # When OFF, use AUTO fan
            remote_state[2] |= self.FAN_AUTO_BYTE2
        
        # Set temperature (Byte 1)
        if hvac_mode != HVACMode.OFF:
            # Clamp temperature to valid range
            safe_temp = int(max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp)))
            temp_index = safe_temp - self.TEMP_MIN
            
            if 0 <= temp_index < len(self.TEMP_MAP_BYTE1):
                remote_state[1] |= self.TEMP_MAP_BYTE1[temp_index]
                _LOGGER.debug(f"Setting temperature: {safe_temp}°C, index: {temp_index}, byte: 0b{self.TEMP_MAP_BYTE1[temp_index]:08b}")
            else:
                # Default to 24°C (index 8)
                remote_state[1] |= self.TEMP_MAP_BYTE1[8]
                _LOGGER.warning(f"Temperature {target_temp} out of range, using 24°C")
        else:
            # When OFF, set to default 24°C
            remote_state[1] |= self.TEMP_MAP_BYTE1[8]  # 24°C
        
        # Log the complete state
        state_hex = ' '.join([f"{byte:02X}" for byte in remote_state])
        _LOGGER.debug(f"Yashima remote state bytes: {state_hex}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(remote_state)
        _LOGGER.debug(f"Generated {len(pulses)} pulses")
        
        return pulses
    
    def _encode_to_pulses(self, remote_state):
        """Convert byte array to IR pulse sequence."""
        pulses = []
        
        # Add header
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        
        # Encode each byte from MSB to LSB
        for byte in remote_state:
            for bit_position in range(7, -1, -1):
                bit = (byte >> bit_position) & 1
                
                # Add mark
                pulses.append(self.BIT_MARK)
                
                # Add space based on bit value
                if bit:
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Add footer
        pulses.append(self.BIT_MARK)
        pulses.append(self.GAP)
        
        return pulses
    
    @property
    def supported_hvac_modes(self):
        """Return supported HVAC modes for Yashima."""
        modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
        
        if self.supports_cool:
            modes.append(HVACMode.COOL)
        if self.supports_heat:
            modes.append(HVACMode.HEAT)
        
        return modes
    
    @property 
    def supported_fan_modes(self):
        """Return supported fan modes for Yashima."""
        # Based on ESPHome code, Yashima only supports AUTO
        # But we can enable all if needed
        return [
            FanMode.AUTO,
            FanMode.LOW,
            FanMode.MEDIUM,
            FanMode.HIGH
        ]
    
    @property
    def supported_swing_modes(self):
        """Yashima doesn't support swing."""
        return []  # No swing control
    
    def set_supports_cool(self, supports):
        """Enable/disable cool mode support."""
        self.supports_cool = supports
    
    def set_supports_heat(self, supports):
        """Enable/disable heat mode support."""
        self.supports_heat = supports