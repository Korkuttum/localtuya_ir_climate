"""Support for Tuya IR Climate Control."""
import logging
import asyncio
import threading
from tinytuya import Contrib

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)

# Home Assistant versiyonuna göre import
try:
    from homeassistant.components.climate import FanMode, SwingMode
except ImportError:
    # Eski versiyonlar için enum benzeri class'lar
    class FanMode:
        AUTO = "auto"
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"
    
    class SwingMode:
        OFF = "off"
        VERTICAL = "vertical"

from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, DEFAULT_FRIENDLY_NAME, CONF_CLIMATE_BRAND

_LOGGER = logging.getLogger(__name__)

# HVAC Mode mapping - string değerlerini enum'a çevir
HVAC_MODE_MAPPING = {
    "off": HVACMode.OFF,
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "heat_cool": HVACMode.HEAT_COOL,
    "auto": HVACMode.AUTO,
    "dry": HVACMode.DRY,
    "fan_only": HVACMode.FAN_ONLY,
}

async def async_setup_entry(hass, entry, async_add_entities):
    await async_setup_platform(hass, entry.data, async_add_entities)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    name = config.get("name", DEFAULT_FRIENDLY_NAME)
    dev_id = config.get("device_id")
    host = config.get("host")
    local_key = config.get("local_key")
    protocol_version = config.get("protocol_version")
    climate_brand = config.get(CONF_CLIMATE_BRAND, "lg")

    _LOGGER.debug("Setting up Tuya Climate: %s, brand: %s", name, climate_brand)

    climate = TuyaIRClimate(
        name=name, dev_id=dev_id, address=host, local_key=local_key,
        protocol_version=protocol_version, climate_brand=climate_brand
    )
    
    await hass.async_add_executor_job(climate._update_availability)
    async_add_entities([climate])


class TuyaIRClimate(ClimateEntity):
    def __init__(self, name, dev_id, address, local_key, protocol_version, climate_brand):
        self._name = name
        self._dev_id = dev_id
        self._address = address
        self._local_key = local_key
        # Protocol version'ı float'a çevir (Auto ise 3.3 kullan)
        self._protocol_version = float(protocol_version) if protocol_version != "Auto" else 3.3
        self._climate_brand = climate_brand
        
        from .climate_protocols import get_protocol
        self._protocol = get_protocol(climate_brand)
        
        self._device = None
        self._available = False
        self._lock = threading.Lock()
        
        # String değerlerle başlat, sonra enum'a çevir
        self._hvac_mode = "off"
        self._hvac_action = "off"
        self._target_temperature = 24
        self._current_temperature = None
        self._fan_mode = "auto"
        self._swing_mode = "off"

    def _init_device(self):
        if self._device: 
            return
            
        _LOGGER.debug("Initializing device %s with version %s", self._dev_id, self._protocol_version)
        try:
            self._device = Contrib.IRRemoteControlDevice(
                dev_id=self._dev_id, 
                address=self._address, 
                local_key=self._local_key,
                version=self._protocol_version, 
                persist=True,
                connection_timeout=5,
                connection_retry_limit=2
            )
        except Exception as e:
            _LOGGER.error("Failed to initialize device: %s", e)
            raise

    def _deinit_device(self):
        if self._device:
            self._device.close()
            self._device = None

    def _update_availability(self):
        with self._lock:
            try:
                self._init_device()
                status = self._device.status()
                self._available = status and "Error" not in status
                _LOGGER.debug("Device %s availability: %s", self._dev_id, self._available)
            except Exception as e:
                self._available = False
                _LOGGER.error("Availability check failed for %s: %s", self._dev_id, e)
            if not self._available:
                self._deinit_device()

    def _send_ir_command_sync(self, pulses):
        """Sync version of IR command sending"""
        with self._lock:
            try:
                self._init_device()
                _LOGGER.debug("Sending IR command with %d pulses", len(pulses))
                
                b64 = Contrib.IRRemoteControlDevice.pulses_to_base64(pulses)
                result = self._device.send_button(b64)
                
                if result and "Error" in result:
                    _LOGGER.error("Failed to send IR command: %s", result)
                    raise HomeAssistantError(f"Tuya device error: {result}")
                    
                _LOGGER.debug("IR command sent successfully")
                return True
                
            except Exception as e:
                self._deinit_device()
                _LOGGER.error("Failed to send IR command: %s", e)
                raise HomeAssistantError(f"Failed to send IR command: {e}")

    async def _send_ir_command(self, pulses):
        """Send IR command to device - async version"""
        try:
            await self.hass.async_add_executor_job(self._send_ir_command_sync, pulses)
            return True
        except Exception as e:
            _LOGGER.error("Failed to send IR command: %s", e)
            raise HomeAssistantError(f"Failed to send IR command: {e}")

    @property
    def available(self): 
        return self._available
        
    @property
    def name(self): 
        return self._name
        
    @property
    def unique_id(self): 
        return self._dev_id
        
    @property
    def temperature_unit(self): 
        return UnitOfTemperature.CELSIUS
        
    @property
    def current_temperature(self): 
        return self._current_temperature
        
    @property
    def target_temperature(self): 
        return self._target_temperature
        
    @property
    def target_temperature_step(self): 
        return self._protocol.temperature_step
        
    @property
    def min_temp(self): 
        return self._protocol.temperature_min
        
    @property
    def max_temp(self): 
        return self._protocol.temperature_max
        
    @property
    def hvac_mode(self): 
        """Return current operation mode - enum formatında"""
        return HVAC_MODE_MAPPING.get(self._hvac_mode, HVACMode.OFF)
        
    @property
    def hvac_action(self): 
        """Return current HVAC action - enum formatında"""
        action_mapping = {
            "off": HVACAction.OFF,
            "heating": HVACAction.HEATING,
            "cooling": HVACAction.COOLING,
            "drying": HVACAction.DRYING,
            "idle": HVACAction.IDLE,
            "fan": HVACAction.FAN,
        }
        return action_mapping.get(self._hvac_action, HVACAction.OFF)
        
    @property
    def hvac_modes(self): 
        """Return the list of available operation modes - enum formatında"""
        return [HVAC_MODE_MAPPING[mode] for mode in self._protocol.supported_hvac_modes]
        
    @property
    def fan_mode(self): 
        return self._fan_mode
        
    @property
    def fan_modes(self): 
        return self._protocol.supported_fan_modes
        
    @property
    def swing_mode(self): 
        return self._swing_mode
        
    @property
    def swing_modes(self): 
        return self._protocol.supported_swing_modes
        
    @property
    def supported_features(self):
        return (ClimateEntityFeature.TARGET_TEMPERATURE |
                ClimateEntityFeature.FAN_MODE |
                ClimateEntityFeature.SWING_MODE)

    @property
    def device_info(self):
        return DeviceInfo(
            name=self._name, 
            manufacturer="Tuya", 
            identifiers={(DOMAIN, self._dev_id)},
            model=f"IR Climate ({self._climate_brand})",
            sw_version=str(self._protocol_version)
        )

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            self._target_temperature = kwargs[ATTR_TEMPERATURE]
            _LOGGER.debug("Setting temperature to %s", self._target_temperature)
            await self._send_climate_command()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode - enum veya string kabul eder"""
        # Enum ise string'e çevir
        if hasattr(hvac_mode, 'value'):
            hvac_mode_str = hvac_mode.value
        else:
            hvac_mode_str = str(hvac_mode)
            
        self._hvac_mode = hvac_mode_str
        
        # HVAC action'ı ayarla
        if hvac_mode_str == "heat":
            self._hvac_action = "heating"
        elif hvac_mode_str == "cool":
            self._hvac_action = "cooling"
        elif hvac_mode_str == "off":
            self._hvac_action = "off"
        else:
            self._hvac_action = "idle"
            
        _LOGGER.debug("Setting HVAC mode to %s (string: %s)", hvac_mode, hvac_mode_str)
        await self._send_climate_command()
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode - enum veya string kabul eder"""
        if hasattr(fan_mode, 'value'):
            self._fan_mode = fan_mode.value
        else:
            self._fan_mode = str(fan_mode)
            
        _LOGGER.debug("Setting fan mode to %s", self._fan_mode)
        await self._send_climate_command()
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation - enum veya string kabul eder"""
        if hasattr(swing_mode, 'value'):
            self._swing_mode = swing_mode.value
        else:
            self._swing_mode = str(swing_mode)
            
        _LOGGER.debug("Setting swing mode to %s", self._swing_mode)
        await self._send_climate_command()
        self.async_write_ha_state()

    async def _send_climate_command(self):
        try:
            # Protocol'a string değerleri gönder
            pulses = self._protocol.generate_ir_code(
                hvac_mode=self._hvac_mode, 
                target_temp=self._target_temperature,
                fan_mode=self._fan_mode, 
                swing_mode=self._swing_mode
            )
            await self._send_ir_command(pulses)
        except Exception as e:
            _LOGGER.error("Climate command failed: %s", e)
            raise HomeAssistantError(f"Climate command failed: {e}")

    async def async_update(self):
        await self.hass.async_add_executor_job(self._update_availability)

    async def async_will_remove_from_hass(self):
        self._deinit_device()