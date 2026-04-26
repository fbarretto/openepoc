# csv-capture

Standalone, single-file Emotiv EPOC 1.0 raw-EEG capture script. No `emokit`
dependency — talks to the dongle directly via `hidapi`, decrypts AES-128-ECB
packets, and writes a 14-channel CSV at 128 Hz.

Kept here as a hackable fallback alongside the main `eeg-exp` package
(which uses emokit + LSL/OSC outlets).

## Usage

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# enumerate HID devices
python read_raw_eeg.py --list-devices

# record 60s to file using your headset's 16-char serial
python read_raw_eeg.py --serial SN20120229000123 -o recording.csv -d 60
```

Flags: `--consumer` (consumer-edition key schema, default is research),
`--raw` (14-bit ints instead of microvolts), `-d N` (duration in seconds).
