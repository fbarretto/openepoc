"""HTTP + WebSocket API for live EEG readings.

Endpoints:
    GET  /          server info (channels, rate, endpoints)
    GET  /latest    most recent sample as JSON
    WS   /stream    live sample stream (one JSON msg per packet, ~128 Hz)

Usage:
    pip install fastapi uvicorn
    python 03_api_server.py
    python 03_api_server.py --host 0.0.0.0 --port 8000

Once running:
    curl http://127.0.0.1:8000/latest
    # browse: http://127.0.0.1:8000/docs       (interactive OpenAPI)
    # browse: http://127.0.0.1:8000/stream     (websocket; use a ws client)
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from openepoc import CHANNELS, SAMPLE_RATE, read_from_hid

log = logging.getLogger("openepoc.api")

_state: dict = {"latest": None, "loop": None}
_subscribers: list[asyncio.Queue] = []
_subs_lock = threading.Lock()


def _capture_loop(loop: asyncio.AbstractEventLoop, is_research: bool, serial: str | None) -> None:
    try:
        for sample in read_from_hid(serial=serial, is_research=is_research):
            _state["latest"] = sample
            with _subs_lock:
                for q in list(_subscribers):
                    loop.call_soon_threadsafe(_safe_put, q, sample)
    except Exception:
        log.exception("capture thread crashed")


def _safe_put(q: asyncio.Queue, item) -> None:
    if q.full():
        try:
            q.get_nowait()
        except asyncio.QueueEmpty:
            pass
    q.put_nowait(item)


def make_app(is_research: bool = False, serial: str | None = None) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI):
        loop = asyncio.get_running_loop()
        _state["loop"] = loop
        t = threading.Thread(
            target=_capture_loop, args=(loop, is_research, serial), daemon=True
        )
        t.start()
        log.info("capture thread started")
        yield

    app = FastAPI(title="openepoc", lifespan=lifespan)

    @app.get("/")
    def info() -> dict:
        return {
            "package": "openepoc",
            "channels": list(CHANNELS),
            "sample_rate": SAMPLE_RATE,
            "endpoints": {
                "info": "/",
                "latest": "/latest",
                "stream": "/stream (websocket)",
                "docs": "/docs",
            },
        }

    @app.get("/latest")
    def latest():
        s = _state["latest"]
        if s is None:
            return JSONResponse({"error": "no samples yet"}, status_code=503)
        return s

    @app.websocket("/stream")
    async def stream(ws: WebSocket) -> None:
        await ws.accept()
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        with _subs_lock:
            _subscribers.append(q)
        try:
            while True:
                sample = await q.get()
                await ws.send_json(sample)
        except WebSocketDisconnect:
            pass
        finally:
            with _subs_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    return app


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--research", action="store_true")
    p.add_argument("--serial", default=None)
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    import uvicorn

    uvicorn.run(make_app(args.research, args.serial), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
