# 02 — Stream EEG over OSC

Streams the 14 EEG channels over OSC at 128 Hz. Bundled mode (one message
with 14 floats at `/eeg`) or per-channel mode (one message per channel
under `/eeg/<label>`).

Receivers: TouchDesigner OSC In CHOP, Max/MSP, SuperCollider, Unity, Pd,
p5.js (via osc-bridge), and most creative-coding clients.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

This pulls openepoc with the `[osc]` extra (`python-osc`).

## Run

```bash
python stream.py                                    # default 127.0.0.1:9000 /eeg
python stream.py --per-channel                      # /eeg/AF3, /eeg/F7, ...
python stream.py --host 192.168.1.42 --port 9000    # remote receiver
python stream.py --address /brain --per-channel     # custom prefix
python stream.py --research                         # research-edition AES schema
```

Per-channel mode is friendlier for receivers that auto-discover OSC
addresses (TouchDesigner does this — channels appear named, not as
`chan1..chan14`).

For a TouchDesigner-side recipe, see `../04_touchdesigner/README.md`.
Most TD users will prefer the in-process Script CHOP path over the OSC
bridge, but OSC is the right choice when TD is on a different machine
than the dongle.
