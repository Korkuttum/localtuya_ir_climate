"""Config flow for LocalTuya Climate."""
import logging
import voluptuous as vol
import tinytuya
from tinytuya import Contrib, Cloud

from .const import *

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_DEVICE_ID, CONF_REGION, CONF_CLIENT_ID, CONF_CLIENT_SECRET

_LOGGER = logging.getLogger(__name__)

class LocalTuyaClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self.config = {
            CONF_NAME: DEFAULT_FRIENDLY_NAME,
            CONF_DEVICE_ID: '', 
            CONF_LOCAL_KEY: '', 
            CONF_PROTOCOL_VERSION: 'Auto',
            CONF_PERSISTENT_CONNECTION: DEFAULT_PERSISTENT_CONNECTION,
            CONF_REGION: 'eu', 
            CONF_CLIENT_ID: '', 
            CONF_CLIENT_SECRET: '', 
            CONF_HOST: '',
            CONF_CLIMATE_BRAND: 'lg', 
        }
        self.cloud = False

    @staticmethod
    @callback
    def async_get_options_flow(entry):
        return LocalTuyaClimateOptionsFlow(entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_method()

    async def async_step_method(self, user_input=None):
        """Select connection method."""
        return self.async_show_menu(
            step_id="method",
            menu_options={
                "cloud": "Tuya Cloud (Recommended)",
                "manual": "Manual Configuration"
            }
        )

    def _get_cloud_devices(self, region, client_id, client_secret):
        """Blocking cloud operation"""
        try:
            cloud = Cloud(region, client_id, client_secret)
            status = cloud.getconnectstatus()
            return cloud, status
        except Exception as e:
            _LOGGER.error("Cloud connection failed: %s", e)
            return None, None

    async def async_step_cloud(self, user_input=None):
        """Handle cloud API step."""
        errors = {}
        if user_input is not None:
            try:
                self.config[CONF_REGION] = user_input[CONF_REGION]
                self.config[CONF_CLIENT_ID] = user_input[CONF_CLIENT_ID]
                self.config[CONF_CLIENT_SECRET] = user_input[CONF_CLIENT_SECRET]
                
                cloud, status = await self.hass.async_add_executor_job(
                    self._get_cloud_devices,
                    user_input[CONF_REGION],
                    user_input[CONF_CLIENT_ID], 
                    user_input[CONF_CLIENT_SECRET]
                )
                
                if not cloud or not status:
                    errors["base"] = "cloud_error"
                elif 'Err' in status and status['Err'] == '911':
                    errors["base"] = "cloud_unauthorized"
                else:
                    devices = await self.hass.async_add_executor_job(cloud.getdevices)
                    if not devices:
                        errors["base"] = "cloud_no_devices"
                    else:
                        self.cloud_devices = devices
                        self.cloud = True
                        return await self.async_step_device_select()
                        
            except Exception as e:
                _LOGGER.error("Cloud API error: %s", e, exc_info=True)
                errors["base"] = "unknown"
        
        schema = vol.Schema({
            vol.Required(CONF_REGION, default=self.config[CONF_REGION]): vol.In([
                "us", "us-e", "eu", "eu-w", "in", "cn", "sg"
            ]),
            vol.Required(CONF_CLIENT_ID, default=self.config[CONF_CLIENT_ID]): cv.string,
            vol.Required(CONF_CLIENT_SECRET, default=self.config[CONF_CLIENT_SECRET]): cv.string
        })
        
        return self.async_show_form(
            step_id="cloud", 
            errors=errors, 
            data_schema=schema
        )

    async def async_step_manual(self, user_input=None):
        """Handle manual configuration."""
        return await self.async_step_climate_config()

    async def async_step_device_select(self, user_input=None):
        """Select device from cloud."""
        if user_input is not None:
            device_str = user_input[CONF_DEVICE_ID]
            device_id = device_str.split('(')[-1].split(')')[0]
            
            self.config[CONF_DEVICE_ID] = device_id
            
            for device in self.cloud_devices:
                if device['id'] == device_id:
                    self.config[CONF_NAME] = device['name']
                    self.config[CONF_LOCAL_KEY] = device['key']
                    self.cloud_info = device
                    break
            
            return await self.async_step_climate_config()
        
        device_list = [f"{device['name']} ({device['id']})" for device in self.cloud_devices]
        
        schema = vol.Schema({
            vol.Required(CONF_DEVICE_ID): vol.In(device_list),
        })
        
        return self.async_show_form(
            step_id="device_select", 
            data_schema=schema
        )

    async def async_step_climate_config(self, user_input=None):
        """Climate brand selection."""
        if user_input is not None:
            self.config[CONF_CLIMATE_BRAND] = user_input[CONF_CLIMATE_BRAND]
            
            if self.cloud:
                return await self.async_step_cloud_final()
            else:
                return await self.async_step_manual_config()
        
        # Açılır pencere şeklinde marka listesi
        brand_list = {
            "lg": "LG",
            "mitsubishi": "Mitsubishi", 
            "samsung": "Samsung",
            "daikin": "Daikin",
            "general": "General (NEC Protocol)"
        }
        
        schema = vol.Schema({
            vol.Required(CONF_CLIMATE_BRAND, default=self.config[CONF_CLIMATE_BRAND]): vol.In(brand_list),
        })
        
        return self.async_show_form(
            step_id="climate_config", 
            data_schema=schema
        )

    async def async_step_cloud_final(self, user_input=None):
        """Final step for cloud configuration - direkt kaydet"""
        errors = {}
        
        try:
            # Local ağda cihazı tarayalım
            scan_results = await self.hass.async_add_executor_job(tinytuya.deviceScan)
            device_ip = None
            
            for ip, device_info in scan_results.items():
                if device_info.get('gwId') == self.config[CONF_DEVICE_ID]:
                    device_ip = ip
                    _LOGGER.debug("Found device %s at IP %s", self.config[CONF_DEVICE_ID], device_ip)
                    break
            
            if device_ip:
                self.config[CONF_HOST] = device_ip
                
                # Auto version ile connection test yap
                version_ok = None
                for version in TUYA_VERSIONS:
                    try:
                        _LOGGER.debug("Testing connection with version %s", version)
                        device, status = await self.hass.async_add_executor_job(
                            self._test_connection,
                            self.config[CONF_DEVICE_ID],
                            self.config[CONF_HOST],
                            self.config[CONF_LOCAL_KEY],
                            version
                        )
                        
                        if device and "Error" not in status:
                            version_ok = version
                            self.config[CONF_PROTOCOL_VERSION] = version
                            _LOGGER.debug("Connection successful with version %s", version)
                            break
                    except Exception as e:
                        _LOGGER.debug("Version %s failed: %s", version, e)
                        continue
                
                if version_ok:
                    # Security için key'i temizle
                    if hasattr(self, 'cloud_info') and 'key' in self.cloud_info:
                        del self.cloud_info['key']
                    self.config[CONF_CLOUD_INFO] = getattr(self, 'cloud_info', None)
                    
                    if self.config[CONF_DEVICE_ID] in self._async_current_ids():
                        return self.async_abort(reason="already_configured")
                    
                    await self.async_set_unique_id(self.config[CONF_DEVICE_ID])
                    return self.async_create_entry(title=self.config[CONF_NAME], data=self.config)
                else:
                    # IP bulundu ama bağlantı kurulamadı
                    return await self.async_step_cloud_ip()
            else:
                # IP bulunamadı
                return await self.async_step_cloud_ip()
                
        except Exception as e:
            _LOGGER.error("Final configuration failed: %s", e)
            return await self.async_step_cloud_ip()

    async def async_step_cloud_ip(self, user_input=None):
        """IP address input for cloud devices"""
        errors = {}
        
        if user_input is not None:
            self.config[CONF_HOST] = user_input[CONF_HOST]
            self.config[CONF_PERSISTENT_CONNECTION] = user_input[CONF_PERSISTENT_CONNECTION]
            
            # Auto version ile connection test
            version_ok = None
            for version in TUYA_VERSIONS:
                try:
                    device, status = await self.hass.async_add_executor_job(
                        self._test_connection,
                        self.config[CONF_DEVICE_ID],
                        user_input[CONF_HOST],
                        self.config[CONF_LOCAL_KEY],
                        version
                    )
                    
                    if device and "Error" not in status:
                        version_ok = version
                        self.config[CONF_PROTOCOL_VERSION] = version
                        break
                except Exception:
                    continue
            
            if version_ok:
                # Security için key'i temizle
                if hasattr(self, 'cloud_info') and 'key' in self.cloud_info:
                    del self.cloud_info['key']
                self.config[CONF_CLOUD_INFO] = getattr(self, 'cloud_info', None)
                
                if self.config[CONF_DEVICE_ID] in self._async_current_ids():
                    return self.async_abort(reason="already_configured")
                
                await self.async_set_unique_id(self.config[CONF_DEVICE_ID])
                return self.async_create_entry(title=self.config[CONF_NAME], data=self.config)
            else:
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_HOST, default=self.config.get(CONF_HOST, "")): cv.string,
            vol.Required(CONF_PERSISTENT_CONNECTION, default=self.config.get(CONF_PERSISTENT_CONNECTION, DEFAULT_PERSISTENT_CONNECTION)): cv.boolean,
        })
        
        return self.async_show_form(
            step_id="cloud_ip", 
            errors=errors, 
            data_schema=schema
        )

    async def async_step_manual_config(self, user_input=None):
        """Manual device configuration."""
        errors = {}
        if user_input is not None:
            self.config.update(user_input)
            
            # Auto version ile connection test
            version_ok = None
            for version in TUYA_VERSIONS:
                try:
                    device, status = await self.hass.async_add_executor_job(
                        self._test_connection,
                        user_input[CONF_DEVICE_ID],
                        user_input[CONF_HOST], 
                        user_input[CONF_LOCAL_KEY],
                        version
                    )
                    
                    if "Error" not in status:
                        version_ok = version
                        self.config[CONF_PROTOCOL_VERSION] = version
                        break
                except Exception:
                    continue
            
            if version_ok:
                if self.config[CONF_DEVICE_ID] in self._async_current_ids():
                    return self.async_abort(reason="already_configured")
                
                await self.async_set_unique_id(self.config[CONF_DEVICE_ID])
                return self.async_create_entry(title=self.config[CONF_NAME], data=self.config)
            else:
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required(CONF_NAME, default=self.config.get(CONF_NAME, DEFAULT_FRIENDLY_NAME)): cv.string,
            vol.Required(CONF_HOST, default=self.config.get(CONF_HOST, "")): cv.string,
            vol.Required(CONF_DEVICE_ID, default=self.config.get(CONF_DEVICE_ID, "")): cv.string,
            vol.Required(CONF_LOCAL_KEY, default=self.config.get(CONF_LOCAL_KEY, "")): cv.string,
            vol.Required(CONF_PERSISTENT_CONNECTION, default=self.config.get(CONF_PERSISTENT_CONNECTION, DEFAULT_PERSISTENT_CONNECTION)): cv.boolean,
        })
        
        return self.async_show_form(
            step_id="manual_config", 
            errors=errors, 
            data_schema=schema
        )

    def _test_connection(self, dev_id, address, local_key, version):
        """Blocking connection test"""
        _LOGGER.debug("Testing connection to %s at %s with version %s", dev_id, address, version)
        try:
            device = Contrib.IRRemoteControlDevice(
                dev_id=dev_id,
                address=address,
                local_key=local_key,
                version=version,
                connection_timeout=10,
                connection_retry_limit=3
            )
            status = device.status()
            _LOGGER.debug("Connection test status: %s", status)
            return device, status
        except Exception as e:
            _LOGGER.error("Connection test failed: %s", e)
            return None, {"Error": str(e)}


class LocalTuyaClimateOptionsFlow(config_entries.OptionsFlow):
    """Options flow for LocalTuya Climate."""
    
    def __init__(self, entry):
        self.entry = entry
        self.config = dict(entry.data.items())

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            self.config[CONF_PERSISTENT_CONNECTION] = user_input[CONF_PERSISTENT_CONNECTION]
            self.hass.config_entries.async_update_entry(self.entry, data=self.config)
            return self.async_create_entry(data=self.config)

        schema = vol.Schema({
            vol.Required(
                CONF_PERSISTENT_CONNECTION, 
                default=self.config.get(CONF_PERSISTENT_CONNECTION, DEFAULT_PERSISTENT_CONNECTION)
            ): cv.boolean
        })

        return self.async_show_form(
            step_id="init", 
            data_schema=schema
        )