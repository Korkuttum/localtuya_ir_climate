# const.py
"""Constants for the LocalTuya Climate integration."""

DOMAIN = "localtuya_ir_climate"
DEFAULT_FRIENDLY_NAME = "Tuya IR Climate"
NOTIFICATION_TITLE = "Tuya IR Climate Control"

CONF_LOCAL_KEY = "local_key"
CONF_PROTOCOL_VERSION = "protocol_version"
CONF_CLOUD_INFO = "cloud_info"
CONF_CLIMATE_BRAND = "climate_brand"
CONF_CLIMATE_MODEL = "climate_model"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"

TUYA_VERSIONS = [3.3, 3.4, 3.5, 3.2, 3.1]

# Tüm desteklenen markalar
SUPPORTED_BRANDS = [
    "lg", "mitsubishi", "daikin", "toshiba", 
    "midea", "gree", "fujitsu", "tcl", 
    "ballu", "coolix", "hitachi", "whirlpool", 
    "whynter", "yashima", "general"
]

# Marka açıklamaları
BRAND_DESCRIPTIONS = {
    "lg": "LG Klima",
    "mitsubishi": "Mitsubishi Klima",
    "daikin": "Daikin Klima",
    "toshiba": "Toshiba Klima",
    "midea": "Midea Klima (Coolix uyumlu)",
    "gree": "Gree Klima",
    "fujitsu": "Fujitsu Klima",
    "tcl": "TCL Klima",
    "ballu": "Ballu Klima (YKR-K/002E)",
    "coolix": "Coolix Klima",
    "hitachi": "Hitachi Klima",
    "whirlpool": "Whirlpool Klima",
    "general": "Genel NEC Protokolü",
    "yashima": "Yashima Klima",
    "whynter": "Whynter Klima"
}
