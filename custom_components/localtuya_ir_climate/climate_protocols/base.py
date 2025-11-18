"""Base climate protocol."""
from abc import ABC, abstractmethod

# Home Assistant versiyonuna göre import
try:
    from homeassistant.components.climate import HVACMode, HVACAction, FanMode, SwingMode
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
    
    class HVACAction:
        OFF = "off"
        HEATING = "heating"
        COOLING = "cooling"
        DRYING = "drying"
        IDLE = "idle"
        FAN = "fan"
    
    class FanMode:
        AUTO = "auto"
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
    
    class SwingMode:
        OFF = "off"
        VERTICAL = "vertical"

class ClimateIRProtocol(ABC):
    """Base class for all climate IR protocols."""
    
    def __init__(self):
        self.supported_hvac_modes = [
            HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, 
            HVACMode.DRY, HVACMode.FAN_ONLY
        ]
        self.supported_fan_modes = [
            FanMode.AUTO, FanMode.LOW, FanMode.MEDIUM, FanMode.HIGH
        ]
        self.supported_swing_modes = [
            SwingMode.OFF, SwingMode.VERTICAL
        ]
        
    @abstractmethod
    def generate_ir_code(self, hvac_mode, target_temp, fan_mode, swing_mode):
        """Generate IR pulse sequence for climate command."""
        pass
        
    @property
    def temperature_min(self):
        return getattr(self, 'TEMP_MIN', 16)
        
    @property 
    def temperature_max(self):
        return getattr(self, 'TEMP_MAX', 30)
        
    @property
    def temperature_step(self):
        return getattr(self, 'TEMP_STEP', 1)