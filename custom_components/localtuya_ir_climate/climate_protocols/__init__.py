"""Climate IR protocols."""
from .lg import LGProtocol

PROTOCOL_MAP = {'lg': LGProtocol}

def get_protocol(brand):
    if brand in PROTOCOL_MAP:
        return PROTOCOL_MAP[brand]()
    raise ValueError(f"Unsupported climate brand: {brand}")

def get_supported_brands():
    return list(PROTOCOL_MAP.keys())