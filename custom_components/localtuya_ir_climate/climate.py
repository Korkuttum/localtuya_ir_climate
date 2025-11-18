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
    """Set up platform from config entry."""
    _LOGGER.debug("Setting up entry: %s", entry.data)
    await async_setup_platform(hass, entry.data, async_add_entities)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the climate platform."""
    name = config.get("name", DEFAULT_FRIENDLY_NAME)
    dev_id = config.get("device_id")
    host = config.get("host")
    local_key = config.get("local_key")
    protocol_version = config.get("protocol_version")
    climate_brand = config.get(CONF_CLIMATE_BRAND, "lg")

    _LOGGER.debug("Setting up Tuya Climate: %s, brand: %s, dev_id: %s", name, climate_brand, dev_id)

    climate = TuyaIRClimate(
        name=name, 
        dev_id=dev_id, 
        address=host, 
        local_key=local_key,
        protocol_version=protocol_version, 
        climate_brand=climate_brand
    )
    
    await hass.async_add_executor_job(climate._update_availability)
    async_add_entities([climate])


class TuyaIRClimate(ClimateEntity):
    def __init__(self, name, dev_id, address, local_key, protocol_version, climate_brand):
        """Initialize the climate device."""
        self._attr_name = name  # Entity ismi için doğrudan attribute
        self._attr_has_entity_name = True  # Modern entity naming
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
        
        # Swing durumunu takip et
        self._swing_state = False

        _LOGGER.debug("Climate entity initialized: %s (ID: %s)", name, dev_id)

    def _init_device(self):
        if self._device: 
            return
            
        _LOGGER.debug("Initializing device %s with version %s", self._dev_id, self._protocol_version)
        try:
            # Önce IRRemoteControlDevice ile dene
            self._device = Contrib.IRRemoteControlDevice(
                dev_id=self._dev_id, 
                address=self._address, 
                local_key=self._local_key,
                version=self._protocol_version, 
                persist=True,
                connection_timeout=10,  # Zaman aşımını artır
                connection_retry_limit=3
            )
            _LOGGER.debug("IRRemoteControlDevice initialized successfully")
            
        except Exception as e:
            _LOGGER.warning("IRRemoteControlDevice failed, trying fallback: %s", e)
            try:
                # Fallback: normal Device kullan
                from tinytuya import Device
                self._device = Device(
                    self._dev_id, 
                    self._address, 
                    self._local_key,
                    version=self._protocol_version,
                    connection_timeout=10,
                    connection_retry_limit=3
                )
                _LOGGER.debug("Fallback Device initialized successfully")
            except Exception as fallback_error:
                _LOGGER.error("All initialization methods failed: %s", fallback_error)
                raise

    def _deinit_device(self):
        if self._device:
            try:
                self._device.close()
            except:
                pass
            finally:
                self._device = None

    def _ensure_connection(self):
        """Ensure device connection is active"""
        if not self._device:
            self._init_device()
            return self._device is not None
            
        try:
            # Basit bir bağlantı testi
            status = self._device.status()
            return True
        except Exception as e:
            _LOGGER.debug("Connection lost, reinitializing: %s", e)
            self._deinit_device()
            self._init_device()
            return self._device is not None

    def _update_availability(self):
        with self._lock:
            try:
                if not self._ensure_connection():
                    self._available = False
                    return
                    
                status = self._device.status()
                # Status kontrolünü esnet
                if status is not None:
                    self._available = True
                    _LOGGER.debug("Device %s is available", self._dev_id)
                else:
                    self._available = False
                    _LOGGER.debug("Device %s status is None", self._dev_id)
                    
            except Exception as e:
                self._available = False
                _LOGGER.debug("Availability check failed for %s: %s", self._dev_id, e)
                self._deinit_device()

    def _send_ir_command_sync(self, pulses):
        """Sync version of IR command sending"""
        with self._lock:
            try:
                if not self._ensure_connection():
                    raise HomeAssistantError("Cannot establish connection to device")
                    
                _LOGGER.debug("Sending IR command with %d pulses", len(pulses))
                
                # IRRemoteControlDevice kullanıyorsak
                if hasattr(self._device, 'send_button'):
                    b64 = Contrib.IRRemoteControlDevice.pulses_to_base64(pulses)
                    result = self._device.send_button(b64)
                else:
                    # Fallback için base64 encode et
                    import base64
                    pulse_str = ','.join(map(str, pulses))
                    b64 = base64.b64encode(pulse_str.encode()).decode()
                    result = self._device.set_value('201', b64)  # IR komutu için DPS
                
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
            self._available = False
            raise HomeAssistantError(f"Failed to send IR command: {e}")

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._attr_name

    @property
    def available(self): 
        return self._available
        
    @property
    def unique_id(self): 
        return f"{DOMAIN}_{self._dev_id}"
        
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
        """Return current swing mode - protokolün swing durumuna göre"""
        # Protokolün swing durumunu kullan
        if hasattr(self._protocol, 'swing_active'):
            return SwingMode.VERTICAL if self._protocol.swing_active else SwingMode.OFF
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
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._dev_id)},
            name=self._attr_name,  # Config'den gelen ismi kullan
            manufacturer="Tuya",
            model=f"IR Climate Controller ({self._climate_brand.upper()})",
            sw_version=f"Protocol {self._protocol_version}",
        )

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
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
            # Klima kapanınca swing durumunu sıfırla
            if hasattr(self._protocol, 'swing_active'):
                self._protocol.swing_active = False
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
            swing_mode_str = swing_mode.value
        else:
            swing_mode_str = str(swing_mode)
            
        _LOGGER.debug("Setting swing mode to %s", swing_mode_str)
        self._swing_mode = swing_mode_str
        await self._send_climate_command()
        self.async_write_ha_state()

    async def _send_climate_command(self):
        """Send climate command to device."""
        try:
            # Protocol'a string değerleri gönder
            pulses = self._protocol.generate_ir_code(
                hvac_mode=self._hvac_mode, 
                target_temp=self._target_temperature,
                fan_mode=self._fan_mode, 
                swing_mode=self._swing_mode
            )
            await self._send_ir_command(pulses)
            # Komut başarılıysa available yap
            self._available = True
        except Exception as e:
            _LOGGER.error("Climate command failed: %s", e)
            self._available = False
            raise HomeAssistantError(f"Climate command failed: {e}")

    async def async_update(self):
        """Update device state."""
        await self.hass.async_add_executor_job(self._update_availability)

    async def async_will_remove_from_hass(self):
        """Close connection when entity is removed."""
        self._deinit_device()
