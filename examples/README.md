# Examples

Each example is a self-contained folder with its own `requirements.txt`,
its own README, and its own runnable script. They all consume `openepoc`
straight from this repo via `pip install -r requirements.txt`, so any
update to the library is picked up next install (or immediately if you
install editable from a local clone — see the main repo README).

| # | Example | What it does |
|---|---|---|
| 01 | [`01_record_csv/`](01_record_csv/README.md) | Record N seconds of EEG (default 5) to a CSV file |
| 02 | [`02_stream_osc/`](02_stream_osc/README.md) | Stream samples to OSC, bundled or per-channel |
| 03 | [`03_api_server/`](03_api_server/README.md) | Expose readings over HTTP + WebSocket (FastAPI) |
| 04 | [`04_touchdesigner/`](04_touchdesigner/README.md) | Read straight inside TouchDesigner via a Script CHOP. Includes a working `openepoc.toe` project. |

## Pattern

Every example follows the same shape:

```
examples/<name>/
    README.md            what it does, run commands, notes
    requirements.txt     openepoc + any extra deps
    <script>.py          self-contained script
```

To run any of them:

```bash
cd examples/<name>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python <script>.py
```

Each `requirements.txt` pulls openepoc as a git dependency:

```
openepoc @ git+https://github.com/fbarretto/openepoc.git
```

…with extras as needed (e.g. `openepoc[osc]` for the OSC streamer). When
you push a change to the library, re-running `pip install -r requirements.txt`
in the example's venv updates the dependency.

For active co-development (editing the library and an example in the same
session), install editable from your local clone instead:

```bash
pip install -e ../..             # the openepoc repo root
pip install fastapi              # plus any example-specific deps
```

## What each one teaches

**`01_record_csv/`** — minimum viable consumer. Just iterates `read_from_hid()`
and writes rows. Use as the template for any "capture-then-analyze-offline"
workflow (training data for a model, replays for testing decoders, etc).

**`02_stream_osc/`** — pattern for fanning samples out to a real-time
client. Same shape works for any sink: replace `send_bundle(...)` with your
own callable to push to MQTT, Redis, a websocket, a ring buffer, whatever.

**`03_api_server/`** — pattern for serving live readings over the network.
Capture loop runs in a background thread, samples land in per-client
`asyncio.Queue` instances, the `/stream` WebSocket drains them. The same
structure works for SSE if you prefer that over WebSockets. The `/latest`
endpoint shows how to expose just the most recent sample for polling clients
that don't want a live stream.

**`04_touchdesigner/`** — the Script CHOP path runs entirely inside TD's
own Python interpreter, so there's no OSC bridge or separate process. Two
ways to use it: open the bundled `openepoc.toe` project, or paste
`openepoc_chop.py` into a Script CHOP's docked Callbacks DAT in your own
project. The folder's README walks through TD's Python compatibility,
install path, the per-group channel toggles, and troubleshooting.

## Composing examples

The four are designed to combine. Common pairings:

- **04 alone (preferred for TD)**: open `openepoc.toe` or paste
  `openepoc_chop.py` into a Script CHOP. No other process needed.
- **02 + 04 (fallback)**: only if TD is on a different machine than the
  dongle, or TD's Python can't load `hidapi` for some platform reason —
  run `02_stream_osc/stream.py --per-channel` and consume the OSC stream
  in TD with an `OSC In CHOP` instead of the Script CHOP path.
- **03 + a webpage**: run the API server, hit the `/stream` WebSocket from
  a small p5.js / d3 / whatever frontend.
- **01 + offline analysis**: record sessions with `01`, batch-process the
  CSVs with pandas / MNE / your own pipeline.

## Building your own

The library API to start from in a new project:

```python
from openepoc import read_from_hid, Decoder, find_dongle, Sample, CHANNELS

# live capture
for sample in read_from_hid():
    ...

# offline / replay (no dongle needed)
decoder = Decoder(serial="SN20130125000472")
sample = decoder.decode(encrypted_32_bytes)
```

For real-time signal processing (e.g. filtering DC drift, mains hum, or
high-frequency noise), the optional `openepoc.filters` module gives you a
composable Pipeline:

```python
from openepoc.filters import Pipeline, HighPass, Notch, LowPass

pipe = Pipeline([HighPass(0.5), Notch(60), LowPass(40)])
for s in pipe.apply(read_from_hid()):
    s["values"]   # filtered

pipe[1].enabled = False    # bypass the notch live
```

(Install the `[filters]` extra: `pip install "openepoc[filters]"` — pulls
numpy + scipy.)

See [the main README](../README.md) for the full public API and install
options.
