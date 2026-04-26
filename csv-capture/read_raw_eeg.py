#!/usr/bin/env python3
"""
Raw EEG data capture from Emotiv EPOC 1.0 (Research Edition) via USB dongle.

Reads 14-channel EEG at 128 Hz, decrypts AES-128-ECB packets, and outputs
to CSV. Uses hidapi to talk directly to the USB HID dongle.

Channels: AF3, F7, F3, FC5, T7, P7, O1, O2, P8, T8, FC6, F4, F8, AF4
"""

import csv
import sys
import time
import signal
import argparse
from datetime import datetime

import hid
from Crypto.Cipher import AES

EMOTIV_VENDOR_IDS = [0x1234, 0x21A1]
EMOTIV_PRODUCT_IDS = [0xED02, 0xED01]

CHANNELS = [
    "AF3", "F7", "F3", "FC5", "T7", "P7", "O1",
    "O2", "P8", "T8", "FC6", "F4", "F8", "AF4",
]

QUALITY_CHANNELS = [
    "F3", "FC5", "AF3", "F7", "T7", "P7", "O1",
    "O2", "P8", "T8", "FC6", "F4", "AF4", "F8",
]

SAMPLE_RATE = 128  # Hz


def find_emotiv_dongle():
    """Find the Emotiv USB dongle among connected HID devices."""
    all_devices = hid.enumerate()
    matches = [
        dev for dev in all_devices
        if dev["vendor_id"] in EMOTIV_VENDOR_IDS
        and dev["product_id"] in EMOTIV_PRODUCT_IDS
    ]
    if matches:
        # EPOC dongle exposes two HID interfaces; the second one streams EEG data
        return matches[-1]

    print("Emotiv dongle not found. Connected HID devices:")
    for dev in all_devices:
        name = dev.get("product_string", "Unknown")
        mfr = dev.get("manufacturer_string", "Unknown")
        print(f"  VID=0x{dev['vendor_id']:04X} PID=0x{dev['product_id']:04X} "
              f"- {mfr} / {name}")
    return None


def derive_key(serial: str, research: bool = True) -> bytes:
    """
    Derive AES-128 key from the headset serial number.

    Research edition and consumer edition use different key schedules.
    The serial is 16 characters printed on the headset (e.g., SN20120229000123).
    """
    s = serial.encode("ascii")

    if research:
        key = bytes([
            s[15], 0x00, s[14], 0x48,
            s[13], 0x00, s[12], 0x54,
            s[15], 0x10, s[14], 0x42,
            s[13], 0x00, s[12], 0x50,
        ])
    else:
        key = bytes([
            s[15], 0x00, s[14], 0x54,
            s[13], 0x10, s[12], 0x42,
            s[15], 0x00, s[14], 0x48,
            s[13], 0x12, s[12], 0x42,
        ])

    return key


def decrypt_packet(cipher: AES, raw: bytes) -> bytes:
    """Decrypt a 32-byte raw HID packet."""
    data = bytes(raw)
    if len(data) == 33:
        data = data[1:]  # strip HID report ID
    if len(data) != 32:
        return None
    return cipher.decrypt(data)


def parse_eeg_packet(decrypted: bytes) -> dict:
    """
    Parse a decrypted 32-byte EPOC packet into 14 EEG channel values.

    Each channel is 14 bits. The bit layout is documented in the emokit project.
    Returns a dict mapping channel name -> raw 14-bit integer value.
    """

    def get_level(data: bytes, bits: list) -> int:
        level = 0
        for i, bit_idx in enumerate(bits):
            byte_idx = bit_idx // 8
            bit_offset = bit_idx % 8
            if byte_idx < len(data):
                level |= ((data[byte_idx] >> bit_offset) & 1) << (13 - i)
        return level

    # Bit positions for each channel (14 bits each), from emokit source
    channel_bits = {
        "AF3": [10, 11, 12, 13, 14, 15, 0, 1, 2, 3, 4, 5, 6, 7],
        "F7":  [28, 29, 30, 31, 16, 17, 18, 19, 20, 21, 22, 23, 8, 9],
        "F3":  [46, 47, 32, 33, 34, 35, 36, 37, 38, 39, 24, 25, 26, 27],
        "FC5": [48, 49, 50, 51, 52, 53, 54, 55, 40, 41, 42, 43, 44, 45],
        "T7":  [66, 67, 68, 69, 70, 71, 56, 57, 58, 59, 60, 61, 62, 63],
        "P7":  [84, 85, 86, 87, 72, 73, 74, 75, 76, 77, 78, 79, 64, 65],
        "O1":  [102, 103, 88, 89, 90, 91, 92, 93, 94, 95, 80, 81, 82, 83],
        "O2":  [140, 141, 142, 143, 128, 129, 130, 131, 132, 133, 134, 135, 120, 121],
        "P8":  [158, 159, 144, 145, 146, 147, 148, 149, 150, 151, 136, 137, 138, 139],
        "T8":  [160, 161, 162, 163, 164, 165, 166, 167, 152, 153, 154, 155, 156, 157],
        "FC6": [178, 179, 180, 181, 182, 183, 168, 169, 170, 171, 172, 173, 174, 175],
        "F4":  [196, 197, 198, 199, 184, 185, 186, 187, 188, 189, 190, 191, 176, 177],
        "F8":  [214, 215, 200, 201, 202, 203, 204, 205, 206, 207, 192, 193, 194, 195],
        "AF4": [216, 217, 218, 219, 220, 221, 222, 223, 208, 209, 210, 211, 212, 213],
    }

    values = {}
    for ch_name in CHANNELS:
        values[ch_name] = get_level(decrypted, channel_bits[ch_name])

    # Counter / battery from first byte
    counter = decrypted[0]
    values["_counter"] = counter
    values["_battery"] = decrypted[0] if counter >= 128 else None

    # Gyro
    values["_gyro_x"] = decrypted[29]
    values["_gyro_y"] = decrypted[30]

    return values


def raw_to_microvolts(raw_value: int) -> float:
    """Convert raw 14-bit value to microvolts (approximate)."""
    # 14-bit range: 0-16383, centered at 8192
    # Resolution: ~0.51 uV/LSB for research edition
    return (raw_value - 8192) * 0.51


def main():
    parser = argparse.ArgumentParser(description="Read raw EEG from Emotiv EPOC 1.0")
    parser.add_argument("--serial", type=str, help="Headset serial number (16 chars, printed on device)")
    parser.add_argument("--consumer", action="store_true", help="Use consumer edition key (default: research)")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file (default: stdout)")
    parser.add_argument("--duration", "-d", type=int, default=0, help="Recording duration in seconds (0 = unlimited)")
    parser.add_argument("--raw", action="store_true", help="Output raw 14-bit values instead of microvolts")
    parser.add_argument("--list-devices", action="store_true", help="List all HID devices and exit")
    args = parser.parse_args()

    if args.list_devices:
        print("Connected HID devices:")
        for dev in hid.enumerate():
            name = dev.get("product_string", "Unknown")
            mfr = dev.get("manufacturer_string", "Unknown")
            print(f"  VID=0x{dev['vendor_id']:04X} PID=0x{dev['product_id']:04X} "
                  f"path={dev['path'].decode()} - {mfr} / {name}")
        return

    # Find dongle
    dongle_info = find_emotiv_dongle()
    if dongle_info is None:
        print("\nERROR: Cannot find Emotiv dongle. Make sure it's plugged in.", file=sys.stderr)
        print("Run with --list-devices to see all connected HID devices.", file=sys.stderr)
        sys.exit(1)

    vid = dongle_info["vendor_id"]
    pid = dongle_info["product_id"]
    print(f"Found dongle: VID=0x{vid:04X} PID=0x{pid:04X} "
          f"- {dongle_info.get('manufacturer_string', '?')} / {dongle_info.get('product_string', '?')}",
          file=sys.stderr)

    if not args.serial:
        print("\nERROR: --serial is required. This is the 16-character serial number", file=sys.stderr)
        print("printed on your headset (e.g., SN20120229000123).", file=sys.stderr)
        print("\nIf you don't know it, check the sticker on the headset arm.", file=sys.stderr)
        sys.exit(1)

    # Derive encryption key
    research = not args.consumer
    key = derive_key(args.serial, research=research)
    cipher = AES.new(key, AES.MODE_ECB)
    edition = "research" if research else "consumer"
    print(f"Using {edition} edition key for serial: {args.serial}", file=sys.stderr)

    # Open HID device
    device = hid.device()
    try:
        device.open_path(dongle_info["path"])
    except OSError as e:
        print(f"\nERROR: Cannot open dongle: {e}", file=sys.stderr)
        print("On macOS, you may need to grant Input Monitoring permission to Terminal/iTerm.", file=sys.stderr)
        print("Go to: System Settings > Privacy & Security > Input Monitoring", file=sys.stderr)
        sys.exit(1)

    device.set_nonblocking(0)  # blocking reads

    # Setup output
    if args.output:
        outfile = open(args.output, "w", newline="")
        print(f"Writing to: {args.output}", file=sys.stderr)
    else:
        outfile = sys.stdout

    writer = csv.writer(outfile)
    header = ["timestamp", "counter", "gyro_x", "gyro_y"] + CHANNELS
    writer.writerow(header)

    # Graceful shutdown
    running = True
    def signal_handler(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"Recording at {SAMPLE_RATE} Hz... (Ctrl+C to stop)", file=sys.stderr)
    start_time = time.time()
    packet_count = 0
    error_count = 0

    try:
        while running:
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                break

            raw = device.read(34, timeout_ms=1000)
            if not raw:
                continue

            decrypted = decrypt_packet(cipher, bytes(raw))
            if decrypted is None:
                error_count += 1
                continue

            parsed = parse_eeg_packet(decrypted)
            packet_count += 1

            timestamp = time.time()
            row = [
                f"{timestamp:.6f}",
                parsed["_counter"],
                parsed["_gyro_x"],
                parsed["_gyro_y"],
            ]

            for ch in CHANNELS:
                val = parsed[ch]
                if not args.raw:
                    val = raw_to_microvolts(val)
                    row.append(f"{val:.2f}")
                else:
                    row.append(val)

            writer.writerow(row)

            if outfile == sys.stdout:
                outfile.flush()

            if packet_count % (SAMPLE_RATE * 5) == 0:
                elapsed = time.time() - start_time
                rate = packet_count / elapsed if elapsed > 0 else 0
                print(f"  [{elapsed:.1f}s] {packet_count} packets, "
                      f"{rate:.1f} pkt/s, {error_count} errors", file=sys.stderr)

    finally:
        elapsed = time.time() - start_time
        print(f"\nDone. {packet_count} packets in {elapsed:.1f}s "
              f"({packet_count/elapsed:.1f} pkt/s), {error_count} errors",
              file=sys.stderr)
        device.close()
        if args.output:
            outfile.close()


if __name__ == "__main__":
    main()
