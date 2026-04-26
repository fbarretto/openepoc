from __future__ import annotations

import time
from typing import Iterator, TypedDict

CHANNELS = (
    "AF3", "F7", "F3", "FC5", "T7", "P7", "O1",
    "O2", "P8", "T8", "FC6", "F4", "F8", "AF4",
)
SAMPLE_RATE = 128

VENDOR_ID = 0x1234
PRODUCT_ID = 0xED02
DATA_INTERFACE = 1

# 14-bit positions per channel inside the 32-byte decrypted packet.
# Bit n maps to bit (n % 8) of byte (n // 8 + 1).
# Reverse-engineered by openyou/emokit (MIT). Vendored here to drop the dep.
SENSOR_BITS: dict[str, list[int]] = {
    "F3":  [10, 11, 12, 13, 14, 15,  0,  1,  2,  3,  4,  5,  6,  7],
    "FC5": [28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23,  8,  9],
    "AF3": [46, 47, 32, 33, 34, 35, 36, 37, 38, 39, 24, 25, 26, 27],
    "F7":  [48, 49, 50, 51, 52, 53, 54, 55, 40, 41, 42, 43, 44, 45],
    "T7":  [66, 67, 68, 69, 70, 71, 56, 57, 58, 59, 60, 61, 62, 63],
    "P7":  [84, 85, 86, 87, 72, 73, 74, 75, 76, 77, 78, 79, 64, 65],
    "O1":  [102, 103, 88, 89, 90, 91, 92, 93, 94, 95, 80, 81, 82, 83],
    "O2":  [140, 141, 142, 143, 128, 129, 130, 131, 132, 133, 134, 135, 120, 121],
    "P8":  [158, 159, 144, 145, 146, 147, 148, 149, 150, 151, 136, 137, 138, 139],
    "T8":  [160, 161, 162, 163, 164, 165, 166, 167, 152, 153, 154, 155, 156, 157],
    "F8":  [178, 179, 180, 181, 182, 183, 168, 169, 170, 171, 172, 173, 174, 175],
    "AF4": [196, 197, 198, 199, 184, 185, 186, 187, 188, 189, 190, 191, 176, 177],
    "FC6": [214, 215, 200, 201, 202, 203, 204, 205, 206, 207, 192, 193, 194, 195],
    "F4":  [216, 217, 218, 219, 220, 221, 222, 223, 208, 209, 210, 211, 212, 213],
}

QUALITY_BITS = [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112]

# Counter byte -> which channel's contact quality this packet carries.
QUALITY_BYTE_TO_CHANNEL: dict[int, str] = {
    0: "F3", 64: "F3",
    1: "FC5", 65: "FC5",
    2: "AF3", 66: "AF3",
    3: "F7", 67: "F7",
    4: "T7", 68: "T7",
    5: "P7", 69: "P7",
    6: "O1", 70: "O1",
    7: "O2", 71: "O2",
    8: "P8", 72: "P8",
    9: "T8", 73: "T8",
    10: "F8", 74: "F8",
    11: "AF4", 75: "AF4",
    12: "FC6", 76: "FC6", 80: "FC6",
    13: "F4", 77: "F4",
    14: "F8", 78: "F8",
    15: "AF4", 79: "AF4",
}

# Counter byte -> battery percent (when counter > 127, byte is the battery reading).
BATTERY_VALUES: dict[int, int] = {
    255: 100, 254: 100, 253: 100, 252: 100, 251: 100, 250: 100, 249: 100, 248: 100,
    247: 99, 246: 97, 245: 93, 244: 89, 243: 85, 242: 82, 241: 77, 240: 72,
    239: 66, 238: 62, 237: 55, 236: 46, 235: 32, 234: 20, 233: 12, 232: 6,
    231: 4, 230: 3, 229: 2, 228: 2, 227: 2, 226: 1, 225: 0, 224: 0,
}


class Sample(TypedDict):
    t: float
    counter: int
    values: list[float]
    quality: dict[str, int]
    gyro: tuple[int, int]
    battery: int | None


def _crypto_key(serial: str, is_research: bool = False) -> bytes:
    sn = serial
    k = bytearray(16)
    k[0] = ord(sn[-1])
    k[1] = 0
    k[2] = ord(sn[-2])
    if is_research:
        k[3] = ord("H")
        k[4] = ord(sn[-1])
        k[5] = 0
        k[6] = ord(sn[-2])
        k[7] = ord("T")
        k[8] = ord(sn[-3])
        k[9] = 0x10
        k[10] = ord(sn[-4])
        k[11] = ord("B")
    else:
        k[3] = ord("T")
        k[4] = ord(sn[-3])
        k[5] = 0x10
        k[6] = ord(sn[-4])
        k[7] = ord("B")
        k[8] = ord(sn[-1])
        k[9] = 0
        k[10] = ord(sn[-2])
        k[11] = ord("H")
    k[12] = ord(sn[-3])
    k[13] = 0
    k[14] = ord(sn[-4])
    k[15] = ord("P")
    return bytes(k)


def _get_level(data: bytes, bits: list[int]) -> int:
    level = 0
    for i in range(13, -1, -1):
        level <<= 1
        b = (bits[i] // 8) + 1
        o = bits[i] % 8
        level |= (data[b] >> o) & 1
    return level


def _find_data_device() -> dict:
    import hid

    devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
    if not devices:
        raise RuntimeError(
            f"Emotiv dongle not found "
            f"(VID={VENDOR_ID:#06x} PID={PRODUCT_ID:#06x})"
        )
    for d in devices:
        if d.get("interface_number") == DATA_INTERFACE:
            return d
    return devices[-1]


def read(
    serial: str | None = None,
    is_research: bool = False,
) -> Iterator[Sample]:
    import hid
    from Crypto.Cipher import AES

    target = _find_data_device()
    if serial is None:
        serial = (target.get("serial_number") or "").strip()
    if not serial or len(serial) < 4:
        raise RuntimeError(
            "could not determine headset serial; pass serial=... explicitly"
        )

    cipher = AES.new(_crypto_key(serial, is_research), AES.MODE_ECB)
    h = hid.device()
    h.open_path(target["path"])

    quality_state: dict[str, int] = {c: 0 for c in CHANNELS}
    try:
        while True:
            raw = h.read(32, timeout_ms=1000)
            if not raw:
                continue
            packet = bytes(raw)
            data = cipher.decrypt(packet[:16]) + cipher.decrypt(packet[16:])
            counter = data[0]

            battery: int | None = None
            if counter > 127:
                battery = BATTERY_VALUES.get(counter, 0)

            values = [
                float(_get_level(data, SENSOR_BITS[c]) - 8192) for c in CHANNELS
            ]

            q = _get_level(data, QUALITY_BITS)
            ch_for_q = QUALITY_BYTE_TO_CHANNEL.get(counter)
            if ch_for_q is not None:
                quality_state[ch_for_q] = q

            yield Sample(
                t=time.time(),
                counter=counter,
                values=values,
                quality=dict(quality_state),
                gyro=(data[29] - 106, data[30] - 105),
                battery=battery,
            )
    finally:
        h.close()
