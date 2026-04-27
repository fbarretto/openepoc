from importlib.metadata import PackageNotFoundError, version

from .reader import (
    CHANNELS,
    KNOWN_DONGLES,
    QUALITY_BITS,
    SAMPLE_RATE,
    SENSOR_BITS,
    Decoder,
    Sample,
    find_dongle,
    read,
    read_from_hid,
)

try:
    __version__ = version("openepoc")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

__all__ = [
    "CHANNELS",
    "KNOWN_DONGLES",
    "QUALITY_BITS",
    "SAMPLE_RATE",
    "SENSOR_BITS",
    "Decoder",
    "Sample",
    "find_dongle",
    "read",
    "read_from_hid",
    "__version__",
]
