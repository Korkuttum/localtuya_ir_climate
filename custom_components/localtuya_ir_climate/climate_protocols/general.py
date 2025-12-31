# general.py
"""General/NEC Climate IR Protocol."""
import logging

from .base import ClimateIRProtocol

_LOGGER = logging.getLogger(__name__)

class GeneralProtocol(ClimateIRProtocol):
    """
    General/NEC Klima IR Protokolü
    Birçok marka için temel NEC protokolü
    """
    
    # Default temperature range
    TEMP_MIN = 16
    TEMP_MAX = 30
    
    # NEC timing parameters (microseconds)
    HEADER_MARK = 9000
    HEADER_SPACE = 4500
    BIT_MARK = 560
    ONE_SPACE = 1690
    ZERO_SPACE = 560
    REPEAT_SPACE = 2250
    
    # NEC address and command
    NEC_ADDRESS = 0x00
    NEC_COMMAND = 0x00
    
    # Mode mappings (customize based on device)
    MODE_COOL = 0x01
    MODE_HEAT = 0x02
    MODE_DRY = 0x03
    MODE_FAN = 0x04
    MODE_AUTO = 0x05
    
    # Fan speed mappings
    FAN_AUTO = 0x00
    FAN_LOW = 0x01
    FAN_MEDIUM = 0x02
    FAN_HIGH = 0x03
    
    def __init__(self, custom_mappings=None):
        super().__init__()
        
        # Allow custom mode/fan mappings
        if custom_mappings:
            self.mode_mappings = custom_mappings.get('modes', {})
            self.fan_mappings = custom_mappings.get('fans', {})
        else:
            self.mode_mappings = {}
            self.fan_mappings = {}
        
        # General protocol supports basic features
        self.supported_swing_modes = ["off"]  # Basic NEC doesn't support swing
        self.supported_fan_modes = ["auto", "low", "medium", "high"]
        
        _LOGGER.debug("General/NEC Protocol initialized")
    
    def set_custom_mappings(self, mode_mappings=None, fan_mappings=None):
        """Set custom mode and fan mappings for specific device."""
        if mode_mappings:
            self.mode_mappings = mode_mappings
        if fan_mappings:
            self.fan_mappings = fan_mappings
        _LOGGER.debug(f"Custom mappings set: modes={self.mode_mappings}, fans={self.fan_mappings}")
    
    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate General/NEC IR code for climate command."""
        _LOGGER.debug(f"Generating General/NEC IR code: mode={hvac_mode}, temp={target_temp}, fan={fan_mode}")
        
        # Clamp temperature
        temp_val = max(self.TEMP_MIN, min(self.TEMP_MAX, target_temp))
        temp_code = int(temp_val) - self.TEMP_MIN
        
        # Get mode code
        mode_code = self._get_mode_code(hvac_mode)
        
        # Get fan code
        fan_code = self._get_fan_code(fan_mode)
        
        # Combine into NEC command
        # Format: [address, ~address, command, ~command]
        # We'll use temperature in command byte
        command_byte = (temp_code << 4) | (mode_code & 0x0F)
        
        # Create NEC frame (address and command with inverses)
        address = self.NEC_ADDRESS
        address_inv = (~address) & 0xFF
        command = command_byte
        command_inv = (~command) & 0xFF
        
        nec_frame = [address, address_inv, command, command_inv]
        
        _LOGGER.debug(f"NEC frame: address=0x{address:02X}, command=0x{command:02X}")
        _LOGGER.debug(f"Full frame: {[f'0x{x:02X}' for x in nec_frame]}")
        
        # Convert to NEC pulse sequence
        pulses = self._encode_nec_frame(nec_frame)
        
        return pulses
    
    def _get_mode_code(self, hvac_mode):
        """Get mode code from mappings or defaults."""
        # First check custom mappings
        if hvac_mode in self.mode_mappings:
            return self.mode_mappings[hvac_mode]
        
        # Default mappings
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
        else:  # off or unknown
            return 0x00
    
    def _get_fan_code(self, fan_mode):
        """Get fan code from mappings or defaults."""
        # First check custom mappings
        if fan_mode in self.fan_mappings:
            return self.fan_mappings[fan_mode]
        
        # Default mappings
        if fan_mode == "low":
            return self.FAN_LOW
        elif fan_mode == "medium":
            return self.FAN_MEDIUM
        elif fan_mode == "high":
            return self.FAN_HIGH
        else:  # auto
            return self.FAN_AUTO
    
    def _encode_nec_frame(self, frame):
        """Convert NEC frame to pulse sequence."""
        pulses = []
        
        # Header
        pulses.extend([self.HEADER_MARK, self.HEADER_SPACE])
        
        # Data (LSB first for NEC)
        for byte in frame:
            for bit in range(8):  # 0 to 7, LSB first
                pulses.append(self.BIT_MARK)
                if byte & (1 << bit):  # Check bit from LSB to MSB
                    pulses.append(self.ONE_SPACE)
                else:
                    pulses.append(self.ZERO_SPACE)
        
        # Footer
        pulses.append(self.BIT_MARK)
        
        return pulses