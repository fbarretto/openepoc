# Examples

Runnable starting points showing common ways to consume `openepoc`. Plug in
the dongle, put the headset on, then pick one. Each script is self-contained
and copy-paste-friendly into your own project.

| # | Example | What it does | Extras needed |
|---|---|---|---|
| 01 | [`01_record_csv.py`](01_record_csv.py) | Record N seconds to a CSV file (default 5s, default `recording.csv`) | none |
| 02 | [`02_stream_osc.py`](02_stream_osc.py) | Stream samples to OSC, bundled or per-channel | `openepoc[osc]` |
| 03 | [`03_api_server.py`](03_api_server.py) | Expose readings over HTTP + WebSocket (FastAPI) | `fastapi`, `uvicorn` |
| 04 | [`04_touchdesigner/`](04_touchdesigner/README.md) | Receive OSC inside TouchDesigner | (uses 02) |

## Running them

From the repo root with your venv active:

```bash
python examples/01_record_csv.py rec.csv --duration 10
python examples/02_stream_osc.py --per-channel
python examples/03_api_server.py
```

## What each one teaches

**`01_record_csv.py`** — minimum viable consumer. Just iterates `read_from_hid()`
and writes rows. Use as the template for any "capture-then-analyze-offline"
workflow (training data for a model, replays for testing decoders, etc).

**`02_stream_osc.py`** — pattern for fanning samples out to a real-time
client. Same shape works for any sink: replace `send_bundle(...)` with your
own callable to push to MQTT, Redis, a websocket, a ring buffer, whatever.

**`03_api_server.py`** — pattern for serving live readings over the network.
Capture loop runs in a background thread, samples land in per-client
`asyncio.Queue` instances, the `/stream` WebSocket drains them. The same
structure works for SSE if you prefer that over WebSockets. The `/latest`
endpoint shows how to expose just the most recent sample for polling clients
that don't want a live stream.

**`04_touchdesigner/`** — recipe for consuming the OSC stream from `02` inside
TouchDesigner. No code in TD beyond an `OSC In CHOP`.

## Composing examples

The four are designed to combine. Common pairings:

- **02 + 04**: capture host runs `02_stream_osc.py --per-channel`, TD on the
  same or another machine consumes via `OSC In CHOP`.
- **03 + a webpage**: run `03_api_server.py`, hit the `/stream` WebSocket from
  a small p5.js / d3 / whatever frontend.
- **01 + offline analysis**: record sessions with `01`, batch-process the CSVs
  with pandas / MNE / your own pipeline.

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

See [the main README](../README.md) for the full public API and install
options.
