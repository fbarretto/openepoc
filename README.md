# eeg-exp

Boilerplate Python project for capturing live raw EEG from an **Emotiv EPOC 1.0**
(original 14-channel headset, 128 Hz, USB dongle) and re-streaming it as **LSL**
and/or **OSC**. Intended as a starting point for downstream experiments: model
training, BCI control, generative interfaces, sonification, etc.

## How it works

The EPOC 1.0 dongle enumerates as a USB HID device delivering 32-byte
AES-128-ECB encrypted reports at 128 Hz. The official Cortex SDK no longer
supports this model. We talk to the dongle directly via `cython-hidapi`,
derive the AES key from the headset's USB serial, decrypt with `pycryptodome`,
and unpack the 14 channels (14 bits each, packed across the 32-byte frame)
in `src/eeg_exp/reader.py`. The bit-position table and key derivation are
vendored from the public [openyou/emokit](https://github.com/openyou/emokit)
project (MIT) — no runtime dependency on it.

From there, samples are pushed to:

- **LSL** (Lab Streaming Layer) via [`pylsl`](https://github.com/labstreaminglayer/pylsl) — the research-standard wire format. Consumed by LabRecorder, OpenViBE, MNE-LSL, BCILAB, NeuroPype, etc.
- **OSC** via [`python-osc`](https://github.com/attwad/python-osc) — for TouchDesigner, Max/MSP, SuperCollider, Unity, p5.js (via osc-bridge), and similar creative-coding clients.

```
[ EPOC headset ] --2.4GHz--> [ USB dongle (HID) ]
                                    |
                              hidapi + AES decrypt
                                    |
                              eeg_exp.reader
                                  /     \
                            pylsl       python-osc
                              |             |
                          LSL stream    OSC messages
```

## Requirements

- macOS (tested on Apple Silicon, Ventura+) or Linux. Windows untested.
- Python 3.10+
- Emotiv EPOC 1.0 with paired USB dongle (factory pairing — do not mix dongles).

System dependencies (macOS):

```bash
brew install hidapi libusb
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For offline analysis (MNE, numpy, scipy):

```bash
pip install -e ".[analysis]"
```

## macOS permissions

Two separate permission systems can block this on Apple Silicon Macs.

### 1. Allow accessories to connect (the big one)

System Settings > **Privacy & Security** > scroll to the **Security** section
> **"Allow accessories to connect"**. Set this to **"Ask for new accessories"**
or **"Always"**. If it's restrictive and you accidentally dismissed an earlier
prompt, the deny is cached and the dongle gets stuck mid-enumeration
(`UsbEnumerationState=2`, `!matched, !registered` in `ioreg`) — no driver
binds, no app can see it. Symptoms: `system_profiler SPUSBDataType` shows the
dongle but `ioreg` shows no child interfaces and `hid.enumerate()` returns
nothing.

If you suspect a stale deny, clear the cache and replug:

```bash
sudo defaults delete /Library/Preferences/com.apple.security.usbaccessories 2>&1
sudo killall -HUP cfprefsd
```

Then unplug, wait 30 seconds, replug. macOS should prompt; click Allow.

### 2. Input Monitoring (less critical)

System Settings > **Privacy & Security** > **Input Monitoring**. Add your
terminal app (Terminal.app / iTerm2) and toggle it on. Sequoia/Ventura don't
accept raw Python binaries here — the terminal grant is sufficient.

### 3. Avoid driver collisions

Quit any installed EmotivPRO / Xavier / Emotiv Control Panel / Emotiv Launcher
apps before running. Their background services can hold the HID interface
exclusively.

## Usage

### Connection wizard

The first thing to run. It prints a physical-setup checklist (charging,
saline, sensor placement, dongle, power) and then runs end-to-end
diagnostics: HID enumeration, dongle detection, AES key-schema selection,
sanity check on the decrypted values, battery, and per-channel contact
quality.

```bash
eeg-exp wizard
```

Skip the checklist preamble once you know the drill:

```bash
eeg-exp wizard --no-checklist
```

### Verify

Confirm the headset is decrypting correctly (prints 20 raw samples):

```bash
eeg-exp verify
```

If the values look like flat noise or zeros, your unit may use the
research-edition key schema — flip the flag:

```bash
eeg-exp --research verify
```

Stream to LSL:

```bash
eeg-exp stream --lsl
```

Stream to OSC (single bundled message at `/eeg` with 14 floats):

```bash
eeg-exp stream --osc --osc-host 127.0.0.1 --osc-port 9000
```

Stream to both, with one OSC message per channel under `/eeg/<label>`:

```bash
eeg-exp stream --lsl --osc --osc-per-channel
```

Sensor order (matches LSL channel labels and OSC per-channel addresses):

```
AF3, F7, F3, FC5, T7, P7, O1, O2, P8, T8, FC6, F4, F8, AF4
```

## Programmatic use

```python
from eeg_exp import read

for sample in read(is_research=False):
    sample["values"]   # list[float], 14 channels in CHANNELS order
    sample["quality"]  # list[int], contact quality (rotates per packet)
    sample["gyro"]     # (gx, gy)
    sample["battery"]  # 0..100
    sample["t"]        # wall-clock timestamp (float seconds)
```

## Recording for offline analysis

Run the LSL outlet, then capture with
[LabRecorder](https://github.com/labstreaminglayer/App-LabRecorder) into XDF.
Convert to MNE for analysis:

```python
import pyxdf, mne, numpy as np
streams, _ = pyxdf.load_xdf("recording.xdf")
eeg = next(s for s in streams if s["info"]["type"][0] == "EEG")
data = np.array(eeg["time_series"]).T
sfreq = float(eeg["info"]["nominal_srate"][0])
labels = [c["label"][0] for c in eeg["info"]["desc"][0]["channels"][0]["channel"]]
raw = mne.io.RawArray(data, mne.create_info(labels, sfreq, "eeg"))
```

## Project layout

```
src/eeg_exp/
    reader.py       hid + AES decode loop, yields Sample dicts
    lsl_outlet.py   pylsl StreamOutlet factory
    osc_outlet.py   python-osc client + send helpers
    wizard.py       eeg-exp wizard (connection + diagnostics)
    cli.py          eeg-exp wizard | verify | stream
examples/
    stream.py       minimal LSL + OSC fan-out
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Wizard step 2 fails: "no Emotiv-like HID device found" but `system_profiler` sees the dongle | "Allow accessories to connect" denied/dismissed. See macOS permissions above. |
| `ioreg` shows the dongle as `!matched, !registered, UsbEnumerationState=2` | Same as above — accessory access blocked at the kernel layer. |
| `verify` prints nothing | Terminal needs Input Monitoring, or another Emotiv app is holding the HID interface |
| All-zero or flat values | Wrong AES schema — try `eeg-exp --research verify` |
| `hid.HIDException: open failed` | Dongle vanished mid-session; replug |
| Samples arrive but contact quality stays at 0 for some channels | Felt pads not saline-soaked, or sensor not making firm scalp contact |
| Battery shows under 10% | Charge via mini-USB on the back of the headband (~6h for full charge) |

## License

MIT
