"""
openepoc reader for TouchDesigner — paste into a Script CHOP's docked
Callbacks DAT.

This file targets a Script CHOP (operator family: CHOP, type: Script).
Pasting it into a Script DAT (the table type) will fail with errors like
"'td.scriptDAT' object has no attribute 'rate'" — different operator
family, different API.

Outputs 14 EEG channels (AF3, F7, F3, FC5, T7, P7, O1, O2, P8, T8, FC6, F4,
F8, AF4) at 128 Hz as a time-sliced CHOP stream. A background thread drains
samples from the dongle into a ring buffer; each cook drains the buffer into
TD's CHOP samples.

See README.md in this folder for setup (TD Python version, install path,
permissions, how to extend with gyro / battery / contact quality channels).
"""

from __future__ import annotations

import threading
from collections import deque

CHANNELS = (
    "AF3", "F7", "F3", "FC5", "T7", "P7", "O1",
    "O2", "P8", "T8", "FC6", "F4", "F8", "AF4",
)
SAMPLE_RATE = 128

_buffer: deque = deque(maxlen=4096)
_reader_started = False
_reader_error: str | None = None


def _start_reader_once() -> None:
    global _reader_started, _reader_error
    if _reader_started:
        return
    _reader_started = True

    try:
        from openepoc import read_from_hid
    except ImportError as e:
        _reader_error = (
            f"openepoc not importable inside TouchDesigner's Python: {e}. "
            "See README.md in this folder."
        )
        return

    def loop() -> None:
        global _reader_error
        try:
            for sample in read_from_hid():
                _buffer.append(sample)
        except Exception as e:
            _reader_error = f"reader thread crashed: {e}"

    threading.Thread(target=loop, daemon=True).start()


def onSetupParameters(scriptOp):
    # Add a hidden 'tick' parameter bound to absTime.seconds. The expression
    # re-evaluates every frame, creating a dependency that forces the Script
    # CHOP to cook each frame even though it has no operator inputs. This is
    # the canonical workaround documented on the Derivative forum.
    try:
        page = scriptOp.appendCustomPage("Tick")
        p = page.appendFloat("Tick")[0]
        p.expr = "absTime.seconds"
    except Exception:
        pass


def onGetCookLevel(scriptOp):
    # Newer TD builds support a CookLevel enum to declare always-cook directly.
    # If the attribute isn't present (older builds), the absTime parameter
    # added in onSetupParameters keeps cooking ticking.
    try:
        return scriptOp.CookLevel.ALWAYS
    except AttributeError:
        return None


def onPulse(par):
    return


def onCook(scriptOp):
    _start_reader_once()

    if _reader_error:
        scriptOp.clear()
        scriptOp.addError(_reader_error)
        return

    samples = []
    while _buffer:
        samples.append(_buffer.popleft())

    scriptOp.clear()
    scriptOp.rate = SAMPLE_RATE
    chans = [scriptOp.appendChan(name) for name in CHANNELS]

    if not samples:
        scriptOp.numSamples = 1
        return

    scriptOp.numSamples = len(samples)
    for j, chan in enumerate(chans):
        for i, s in enumerate(samples):
            chan[i] = s["values"][j]
