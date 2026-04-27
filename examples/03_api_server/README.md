# 03 — HTTP + WebSocket API

A FastAPI server that exposes live EEG over HTTP and a WebSocket. Capture
loop runs in a background thread; samples land in per-client async queues
that drain into the WebSocket. The same shape works for SSE if you prefer
that over WS.

## Endpoints

| Method | Path | What it returns |
|---|---|---|
| `GET` | `/`        | Server info (channels, rate, endpoint list) |
| `GET` | `/latest`  | Most recent sample as JSON |
| `WS`  | `/stream`  | Live sample stream, one JSON message per packet (~128 Hz) |
| `GET` | `/docs`    | Interactive OpenAPI docs (Swagger UI) |

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

This pulls openepoc + fastapi + `uvicorn[standard]`.

## Run

```bash
python server.py                            # 127.0.0.1:8000
python server.py --host 0.0.0.0 --port 8000 # bind to all interfaces
python server.py --research                 # research-edition AES schema
```

## Test it

```bash
curl http://127.0.0.1:8000/             # info
curl http://127.0.0.1:8000/latest       # most recent sample
open http://127.0.0.1:8000/docs         # interactive UI in browser
```

For the WebSocket: any client works. Quickest test from the command line:

```bash
pip install websockets
python -c "
import asyncio, json, websockets
async def main():
    async with websockets.connect('ws://127.0.0.1:8000/stream') as ws:
        for _ in range(20):
            print(json.loads(await ws.recv())['values'][:3])
asyncio.run(main())
"
```

## Architecture sketch

```
[ HID dongle ]
      |
      v
read_from_hid()   <-- runs in a daemon thread inside the FastAPI process
      |
      v
+-----+-------+
| latest cache| <- GET /latest reads this
| subscribers |
+-+---+---+---+
  |   |   |
  v   v   v
 WS1 WS2 WS3   <- each client has its own asyncio.Queue
```

Frontend ideas: a p5.js sketch that connects to `/stream`, draws a
14-line oscilloscope. Or wire `/latest` polling into a Grafana panel
for slow-rate dashboards.
