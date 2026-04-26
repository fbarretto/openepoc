# eeg-exp

Boilerplate Python project for capturing live raw EEG from an **Emotiv EPOC 1.0**
(original 14-channel headset, 128 Hz, USB dongle) and re-streaming it as **LSL**
and/or **OSC**. Intended as a starting point for downstream experiments: model
training, BCI control, generative interfaces, sonification, etc.

## How it works

The EPOC 1.0 dongle enumerates as a USB HID device delivering 32-byte
AES-128-ECB encrypted reports at 128 Hz. The official Cortex SDK no longer
supports this model, so we use the reverse-engineered
[openyou/emokit](https://github.com/openyou/emokit) library, which derives the
AES key from the headset serial. From there, samples are pushed to:

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

On Ventura+ you must grant **Input Monitoring** to both your terminal
(Terminal.app / iTerm2) AND the Python interpreter binary in
`System Settings > Privacy & Security > Input Monitoring`. Otherwise HID reads
silently return nothing — no error is raised.

Also: quit any installed EmotivPRO / Xavier / Emotiv Control Panel apps before
running. Their background services grab the HID interface exclusively.

## Usage

Verify the headset is decrypting correctly (prints 20 raw samples):

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
    reader.py       emokit wrapper, yields Sample dicts
    lsl_outlet.py   pylsl StreamOutlet factory
    osc_outlet.py   python-osc client + send helpers
    cli.py          eeg-exp verify | stream
examples/
    stream.py       minimal LSL + OSC fan-out
```

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `verify` prints nothing | Input Monitoring not granted, or another Emotiv app is holding the HID interface |
| All-zero or flat values | Wrong AES schema — try `--research` |
| `hid.HIDException: open failed` | Dongle not detected; replug, check `system_profiler SPUSBDataType` |
| Samples arrive but contact quality dict looks wrong | Normal — quality byte rotates through sensor IDs each packet |

## License

MIT
