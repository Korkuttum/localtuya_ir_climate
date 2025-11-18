"""LG Climate IR Protocol."""
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

class LGProtocol(ClimateIRProtocol):
    """
    LG Klima IR Protokolü
    ESPHome climate_ir_lg.h/cpp referans alınarak yazılmıştır
    """
    
    TEMP_MIN = 18
    TEMP_MAX = 30
    TEMP_STEP = 1
    
    # Command constants
    COMMAND_OFF = 0xC0000
    COMMAND_SWING = 0x10000
    COMMAND_ON_COOL = 0x00000
    COMMAND_ON_DRY = 0x01000
    COMMAND_ON_FAN_ONLY = 0x02000
    COMMAND_ON_AI = 0x03000
    COMMAND_ON_HEAT = 0x04000
    
    # Fan speed constants
    FAN_AUTO = 0x50
    FAN_MIN = 0x00
    FAN_MED = 0x20
    FAN_MAX = 0x40
    
    def __init__(self):
        super().__init__()
        
        # LG IR timing parameters (microseconds)
        self.header_high = 8000
        self.header_low = 4000
        self.bit_high = 500
        self.bit_one_low = 1600
        self.bit_zero_low = 500
        
        # State tracking
        self.mode_before = HVACMode.OFF
        self.swing_active = False  # Swing durumunu takip et
        
        _LOGGER.debug("LG Protocol initialized")

    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate LG IR code for climate command."""
        _LOGGER.debug(f"Generating LG IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}, swing={swing_mode}")
        
        remote_state = 0x8800000  # Base LG code
        
        # Swing modu değişti mi kontrol et
        swing_changed = False
        if swing_mode == SwingMode.VERTICAL and not self.swing_active:
            # Swing açılıyor
            swing_changed = True
            self.swing_active = True
            _LOGGER.debug("Turning swing ON")
        elif swing_mode == SwingMode.OFF and self.swing_active:
            # Swing kapanıyor
            swing_changed = True
            self.swing_active = False
            _LOGGER.debug("Turning swing OFF")
        
        # Swing komutu gönder (açık veya kapalı farketmez, toggle olarak çalışır)
        if swing_changed and hvac_mode != HVACMode.OFF:
            remote_state |= self.COMMAND_SWING
            _LOGGER.debug("Sending swing toggle command")
            
            # Calculate checksum
            remote_state = self._calculate_checksum(remote_state)
            _LOGGER.debug(f"Swing remote state: 0x{remote_state:08X}")
            
            # Convert to pulse sequence
            pulses = self._encode_to_pulses(remote_state)
            _LOGGER.debug(f"Generated {len(pulses)} pulses for swing")
            
            return pulses
        
        # Normal mod komutları (swing değişmediyse veya klima kapalıysa)
        climate_is_off = (self.mode_before == HVACMode.OFF)
        
        if hvac_mode == HVACMode.OFF:
            remote_state |= self.COMMAND_OFF
            # Klima kapanınca swing'i de sıfırla
            self.swing_active = False
        elif hvac_mode == HVACMode.COOL:
            remote_state |= self.COMMAND_ON_COOL if climate_is_off else 0x08000
        elif hvac_mode == HVACMode.DRY:
            remote_state |= self.COMMAND_ON_DRY if climate_is_off else 0x09000
        elif hvac_mode == HVACMode.FAN_ONLY:
            remote_state |= self.COMMAND_ON_FAN_ONLY if climate_is_off else 0x0A000
        elif hvac_mode == HVACMode.HEAT_COOL:
            remote_state |= self.COMMAND_ON_AI if climate_is_off else 0x0B000
        elif hvac_mode == HVACMode.HEAT:
            remote_state |= self.COMMAND_ON_HEAT if climate_is_off else 0x0C000
    
        self.mode_before = hvac_mode
        
        # Set fan speed
        if hvac_mode == HVACMode.OFF:
            remote_state |= self.FAN_AUTO
        else:
            if fan_mode == FanMode.HIGH:
                remote_state |= self.FAN_MAX
            elif fan_mode == FanMode.MEDIUM:
                remote_state |= self.FAN_MED
            elif fan_mode == FanMode.LOW:
                remote_state |= self.FAN_MIN
            else:  # AUTO or unknown
                remote_state |= self.FAN_AUTO
        
        # Set temperature for appropriate modes - SWING AÇIKKEN DE AYARLANABİLSİN
        if hvac_mode in [HVACMode.COOL, HVACMode.HEAT, HVACMode.HEAT_COOL, HVACMode.AUTO, HVACMode.DRY]:
            temp_val = int(max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp)))
            remote_state |= ((temp_val - 15) << 8)
            _LOGGER.debug(f"Setting temperature: {temp_val}°C, code: {((temp_val - 15) << 8):04X}")
        
        # Calculate checksum
        remote_state = self._calculate_checksum(remote_state)
        
        _LOGGER.debug(f"Final remote state: 0x{remote_state:08X}")
        
        # Convert to pulse sequence
        pulses = self._encode_to_pulses(remote_state)
        _LOGGER.debug(f"Generated {len(pulses)} pulses")
        
        return pulses

    def _calculate_checksum(self, value):
        """Calculate LG checksum - sum of nibbles."""
        mask = 0xF
        sum_val = 0
        
        # Sum nibbles 1-7 (skip nibble 0)
        for i in range(1, 8):
            nibble = (value >> (i * 4)) & mask
            sum_val += nibble
        
        # Add checksum to nibble 0
        value = (value & 0xFFFFFFF0) | (sum_val & mask)
        
        return value

    def _encode_to_pulses(self, value):
        """Convert 28-bit value to IR pulse sequence."""
        pulses = []
        BITS = 28
        
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
