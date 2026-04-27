# openepoc

Open-source raw EEG capture from the **Emotiv EPOC 1.0** (the original 14-channel
headset, 128 Hz, USB dongle). A small Python library that opens the dongle via
`hidapi`, decrypts the AES-encrypted reports, and yields decoded samples — plus
optional outlets for LSL and OSC, and a CLI with a connection wizard.

Designed to be **importable as a library** so downstream projects (model
training, BCI control, generative interfaces, sonification) can build on top of
it. The decoder is a pure function on bytes — works on live HID, replayed
recordings, or fake data.

## How it works

The EPOC 1.0 dongle enumerates as a USB HID device delivering 32-byte
AES-128-ECB encrypted reports at 128 Hz. The official Cortex SDK no longer
supports this model. We:

1. Open the dongle via `cython-hidapi` and read 32-byte reports
2. Derive the AES key from the headset's USB serial
3. Decrypt with `pycryptodome`
4. Unpack the 14 channels (14 bits each, packed across the frame)
5. Yield typed `Sample` dicts

The bit-position table and key derivation are vendored from the public
[openyou/emokit](https://github.com/openyou/emokit) project (MIT). No runtime
dependency on it — `hidapi` and `pycryptodome` are the only core deps.

```
[ EPOC headset ] --2.4GHz--> [ USB dongle (HID) ]
                                    |
                       openepoc.read_from_hid (live)
                                    |
                       or openepoc.Decoder (offline)
                                    |
                          openepoc.Sample (typed)
                                    |
                  +-----------------+------------------+
                  |                 |                  |
              pylsl outlet     python-osc      your sink (websocket,
              (optional)       (optional)        ringbuffer, csv, ...)
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

Core (just decode + read from HID):

```bash
pip install git+https://github.com/fbarretto/openepoc.git
```

With LSL outlet:

```bash
pip install "openepoc[lsl] @ git+https://github.com/fbarretto/openepoc.git"
```

With OSC outlet:

```bash
pip install "openepoc[osc] @ git+https://github.com/fbarretto/openepoc.git"
```

Both outlets:

```bash
pip install "openepoc[stream] @ git+https://github.com/fbarretto/openepoc.git"
```

Offline analysis (MNE / numpy / scipy):

```bash
pip install "openepoc[analysis] @ git+https://github.com/fbarretto/openepoc.git"
```

Everything:

```bash
pip install "openepoc[all] @ git+https://github.com/fbarretto/openepoc.git"
```

### Local editable install (during development)

```bash
git clone git@github.com:fbarretto/openepoc.git
cd openepoc
python -m venv .venv
source .venv/bin/activate
pip install -e ".[stream]"
```

### Using openepoc from a downstream project

In your sketch's `pyproject.toml`:

```toml
[project]
dependencies = [
    "openepoc @ git+https://github.com/fbarretto/openepoc.git@main",
]
```

For active co-development, install editable from a local clone alongside your
sketch:

```bash
# layout: ~/code/openepoc and ~/code/your-sketch as siblings
cd your-sketch
pip install -e ../openepoc
pip install -e .
```

Edits to `openepoc/` are picked up immediately on the next Python run.

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

### CLI

The package installs an `openepoc` command.

```bash
openepoc wizard                  # interactive connection check + setup checklist
openepoc wizard --no-checklist   # skip the physical-setup preamble

openepoc verify                  # print 20 raw samples to stdout
openepoc verify --count 200      # arbitrary count
openepoc --research verify       # research-edition AES schema

openepoc stream --lsl                                # LSL outlet
openepoc stream --osc                                # OSC at 127.0.0.1:9000 /eeg
openepoc stream --lsl --osc                          # both
openepoc stream --osc --osc-per-channel              # one OSC msg per channel
openepoc --serial SN20130125000472 stream --lsl      # explicit serial (multi-dongle)
```

Sensor order (matches LSL channel labels and OSC per-channel addresses):

```
AF3, F7, F3, FC5, T7, P7, O1, O2, P8, T8, FC6, F4, F8, AF4
```

### Library

#### Live capture from the dongle

```python
from openepoc import read_from_hid

for sample in read_from_hid(is_research=False):
    sample["values"]   # list[float], 14 channels in CHANNELS order, microvolts-ish
    sample["quality"]  # dict[str, int], rolling per-channel contact quality
    sample["gyro"]     # (gx, gy)
    sample["battery"]  # int 0..100, or None if not in this packet
    sample["counter"]  # int 0..127, packet sequence
    sample["t"]        # wall-clock timestamp (float seconds)
```

#### Offline / replay decoding

If you have raw 32-byte encrypted packets (recorded from a previous session,
captured on a Linux host, or bytes from a fake source), decode them without
touching HID:

```python
from openepoc import Decoder

decoder = Decoder(serial="SN20130125000472", is_research=False)
for encrypted_packet in load_recording("session.bin"):
    sample = decoder.decode(encrypted_packet)
    train_model.feed(sample)
```

#### Multi-dongle / explicit device selection

```python
from openepoc import find_dongle, read_from_hid

target = find_dongle(serial="SN20130125000472")
for sample in read_from_hid(path=target["path"]):
    ...
```

#### Diagnostics

```python
from openepoc.diagnostics import enumerate_dongles, looks_sane, try_capture

devices = enumerate_dongles()
samples, qualities, battery, err = try_capture(timeout_s=5)
ok, detail = looks_sane(samples)
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
src/openepoc/
    reader.py        Decoder class + read_from_hid generator + find_dongle
    diagnostics.py   enumerate_dongles, try_capture, looks_sane
    lsl_outlet.py    pylsl StreamOutlet factory (lazy import; needs [lsl])
    osc_outlet.py    python-osc client + send helpers (lazy; needs [osc])
    wizard.py        physical-setup checklist + 5-step diagnostic
    cli.py           openepoc wizard | verify | stream
    py.typed         marker for downstream mypy/pyright
examples/
    stream.py        minimal LSL + OSC fan-out
```

## Public API

```python
from openepoc import (
    CHANNELS,           # tuple[str, ...] of 14 channel names in canonical order
    SAMPLE_RATE,        # 128
    KNOWN_DONGLES,      # tuple of (vid, pid) pairs
    SENSOR_BITS,        # bit-position table per channel
    QUALITY_BITS,       # bit positions for per-packet quality
    Sample,             # TypedDict for decoded samples
    Decoder,            # pure decoder: bytes -> Sample
    find_dongle,        # find a connected dongle, by serial / path / first match
    read_from_hid,      # generator yielding Samples from a live dongle
    read,               # alias for read_from_hid
    __version__,
)
from openepoc.diagnostics import (
    enumerate_dongles,
    looks_sane,
    try_capture,
)
from openepoc.lsl_outlet import make_outlet            # needs [lsl] extra
from openepoc.osc_outlet import (                      # needs [osc] extra
    make_client, send_bundle, send_per_channel,
)
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Wizard step 2 fails: "no Emotiv-like HID device found" but `system_profiler` sees the dongle | "Allow accessories to connect" denied/dismissed. See macOS permissions above. |
| `ioreg` shows the dongle as `!matched, !registered, UsbEnumerationState=2` | Same as above — accessory access blocked at the kernel layer. |
| `verify` prints nothing | Terminal needs Input Monitoring, or another Emotiv app is holding the HID interface |
| All-zero or flat values | Wrong AES schema — try `openepoc --research verify` |
| `hid.HIDException: open failed` | Dongle vanished mid-session; replug |
| Samples arrive but contact quality stays at 0 for some channels | Felt pads not saline-soaked, or sensor not making firm scalp contact |
| Battery shows under 10% | Charge via mini-USB on the back of the headband (~6h for full charge) |
| `pip install` fails on `pylsl` | Skip the LSL extra; install `openepoc` (core only) and use a different sink |

## License

MIT. Decoder logic vendored from [openyou/emokit](https://github.com/openyou/emokit) (also MIT).
