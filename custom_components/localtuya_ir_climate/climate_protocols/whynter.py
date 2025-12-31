"""Whynter Climate IR Protocol."""
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

class WhynterProtocol(ClimateIRProtocol):
    """
    Whynter Klima IR Protokolü
    ESPHome climate_ir_whynter.h/cpp referans alınarak yazılmıştır
    """
    
    TEMP_MIN = 16  # Celsius
    TEMP_MAX = 32  # Celsius
    TEMP_STEP = 1
    
    # Command constants
    COMMAND_CODE = 0x12 << 24
    
    # Power
    POWER_SHIFT = 8
    POWER_MASK = 1 << POWER_SHIFT
    POWER_OFF = 0 << POWER_SHIFT
    POWER_ON = 1 << POWER_SHIFT
    
    # Mode
    MODE_SHIFT = 16
    MODE_FAN = 0b0001 << MODE_SHIFT
    MODE_DRY = 0b0010 << MODE_SHIFT
    MODE_HEAT = 0b0100 << MODE_SHIFT
    MODE_COOL = 0b1000 << MODE_SHIFT
    
    # Fan Speed
    FAN_SHIFT = 20
    FAN_HIGH = 0b001 << FAN_SHIFT
    FAN_MED = 0b010 << FAN_SHIFT
    FAN_LOW = 0b100 << FAN_SHIFT
    
    # Temperature Unit (Celsius by default)
    UNIT_SHIFT = 10
    UNIT_CELSIUS = 0 << UNIT_SHIFT
    UNIT_FAHRENHEIT = 1 << UNIT_SHIFT
    
    # Temperature Value
    TEMP_OFFSET_C = 16
    
    def __init__(self):
        super().__init__()
        
        # Whynter IR timing parameters (microseconds)
        self.header_high = 8000
        self.header_low = 4000
        self.bit_high = 600
        self.bit_one_low = 1600
        self.bit_zero_low = 550
        
        # State tracking
        self.mode_before = HVACMode.OFF
        self.last_hvac_mode = HVACMode.OFF
        
        # Use Celsius by default
        self.fahrenheit = False
        
        _LOGGER.debug("Whynter Protocol initialized")

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate Whynter IR code for climate command."""
        _LOGGER.debug(f"Generating Whynter IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}")
        
        # Start with command code
        remote_state = self.COMMAND_CODE
        
        # Convert HVAC mode to Whynter format
        if hvac_mode == HVACMode.OFF:
            remote_state |= self.POWER_OFF
            self.mode_before = hvac_mode
        else:
            remote_state |= self.POWER_ON
            
            # Set mode based on HVAC mode
            if hvac_mode == HVACMode.FAN_ONLY:
                remote_state |= self.MODE_FAN
            elif hvac_mode == HVACMode.DRY:
                remote_state |= self.MODE_DRY
            elif hvac_mode == HVACMode.HEAT:
                remote_state |= self.MODE_HEAT
            elif hvac_mode in [HVACMode.COOL, HVACMode.HEAT_COOL, HVACMode.AUTO]:
                # Whynter doesn't have AUTO mode, default to COOL
                remote_state |= self.MODE_COOL
            else:
                # Default to COOL if unknown
                remote_state |= self.MODE_COOL
            
            self.mode_before = hvac_mode
        
        # Set fan speed
        if hvac_mode != HVACMode.OFF:
            if fan_mode == FanMode.HIGH:
                remote_state |= self.FAN_HIGH
            elif fan_mode == FanMode.MEDIUM:
                remote_state |= self.FAN_MED
            elif fan_mode == FanMode.LOW:
                remote_state |= self.FAN_LOW
            else:  # AUTO or unknown - default to HIGH
                remote_state |= self.FAN_HIGH
        else:
            # When off, use HIGH fan as default
            remote_state |= self.FAN_HIGH
        
        # Set temperature for appropriate modes
        if hvac_mode not in [HVACMode.OFF, HVACMode.FAN_ONLY]:
            # Clamp temperature to valid range
            temp_val = int(max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp)))
            
            if self.fahrenheit:
                # Convert to Fahrenheit and reverse bits
                import math
                temp_f = int(math.floor((temp_val * 9/5) + 32))
                temp_f = max(61, min(89, temp_f))  # Whynter Fahrenheit range
                temp_byte = self._reverse_bits(temp_f)
                remote_state |= self.UNIT_FAHRENHEIT
            else:
                # Celsius - subtract offset and reverse bits
                temp_c = temp_val - self.TEMP_OFFSET_C
                temp_byte = self._reverse_bits(temp_c)
                remote_state |= self.UNIT_CELSIUS
            
            # Add temperature byte to remote state
            remote_state |= temp_byte
            
            _LOGGER.debug(f"Setting temperature: {temp_val}°C, byte: 0x{temp_byte:02X}")
        else:
            # For FAN_ONLY or OFF mode, set default temperature (24°C)
            default_temp = 24 - self.TEMP_OFFSET_C
            temp_byte = self._reverse_bits(default_temp)
            remote_state |= self.UNIT_CELSIUS
            remote_state |= temp_byte
        
        _LOGGER.debug(f"Final remote state: 0x{remote_state:08X}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(remote_state)
        _LOGGER.debug(f"Generated {len(pulses)} pulses")
        
        return pulses
    
    def _reverse_bits(self, value):
        """Reverse bits in a byte (LSB to MSB)."""
        # Convert to 8-bit
        value = value & 0xFF
        
        # Reverse bits: 0bABCDEFGH -> 0bHGFEDCBA
        result = 0
        for i in range(8):
            result <<= 1
            result |= (value & 1)
            value >>= 1
        return result
    
    def _encode_to_pulses(self, value):
        """Convert 32-bit value to IR pulse sequence."""
        pulses = []
        BITS = 32
        
        # Add header
        pulses.extend([self.header_high, self.header_low])
        
        # Encode data bits (MSB first)
        for bit_position in range(BITS - 1, -1, -1):
            bit = (value >> bit_position) & 1
            
            # Add bit pulse
            pulses.append(self.bit_high)
            
            # Add gap based on bit value
            if bit:
                pulses.append(self.bit_one_low)
            else:
                pulses.append(self.bit_zero_low)
        
        # Add final mark
        pulses.append(self.bit_high)
        
        return pulses
    
    @property
    def supported_hvac_modes(self):
        """Return supported HVAC modes for Whynter."""
        return [
            HVACMode.OFF, 
            HVACMode.COOL, 
            HVACMode.HEAT, 
            HVACMode.DRY, 
            HVACMode.FAN_ONLY
        ]
    
    @property 
    def supported_fan_modes(self):
        """Return supported fan modes for Whynter."""
        return [
            FanMode.LOW,
            FanMode.MEDIUM,
            FanMode.HIGH
        ]
    
    @property
    def supported_swing_modes(self):
        """Whynter doesn't support swing."""
        return []  # Whynter doesn't have swing control