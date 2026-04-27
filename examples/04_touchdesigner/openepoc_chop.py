"""
openepoc reader for TouchDesigner — paste into a Script CHOP's docked
Callbacks DAT.

This file targets a Script CHOP (operator family: CHOP, type: Script).
Pasting it into a Script DAT (the table type) will fail with errors like
"'td.scriptDAT' object has no attribute 'rate'" — different operator
family, different API.

Outputs at 128 Hz as a CHOP stream:
  - 14 EEG channels: AF3 F7 F3 FC5 T7 P7 O1 O2 P8 T8 FC6 F4 F8 AF4
  - 2 gyro channels: gyro_x gyro_y (head pan/tilt — no accel on EPOC 1.0)
  - 14 contact-quality channels: q_AF3 q_F7 ... q_AF4 (raw 0-2200ish)
  - battery (0-100, 0 when not in this packet)
  - counter (0-127 packet sequence)

A background thread drains samples from the dongle into a ring buffer;
each cook drains the buffer into TD's CHOP samples. Toggle any of the
EMIT_* flags below to drop a channel group; use a Select CHOP downstream
to filter for visualization.

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

# Optional extra channels. Set any of these to False to drop the group.
# EPOC 1.0 has a 2-axis gyroscope only (no accelerometer — that's EPOC+).
EMIT_GYRO = True
EMIT_QUALITY = True
EMIT_BATTERY = True
EMIT_COUNTER = True

GYRO_CHANNELS = ("gyro_x", "gyro_y")
QUALITY_CHANNELS = tuple(f"q_{c}" for c in CHANNELS)

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
    # Add a 'Tick' parameter whose default expression is absTime.seconds.
    # absTime.seconds advances every frame, the parameter re-evaluates,
    # the dependency forces the Script CHOP to cook every frame.
    # IMPORTANT: this only runs when you click "Setup Parameters" in the
    # Script CHOP's parameter panel, not when this DAT is edited.
    try:
        page = scriptOp.appendCustomPage("Tick")
        result = page.appendFloat("Tick", label="Tick")
        p = result[0] if isinstance(result, (list, tuple)) else result
        p.default = 0.0
        p.defaultExpr = "absTime.seconds"
        p.defaultMode = ParMode.EXPRESSION
    except Exception as e:
        # If something goes wrong, surface it on next cook.
        global _reader_error
        if _reader_error is None:
            _reader_error = f"onSetupParameters failed: {e}"


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
    eeg_chans = [scriptOp.appendChan(name) for name in CHANNELS]
    gyro_chans = (
        [scriptOp.appendChan(name) for name in GYRO_CHANNELS] if EMIT_GYRO else []
    )
    quality_chans = (
        [scriptOp.appendChan(name) for name in QUALITY_CHANNELS]
        if EMIT_QUALITY
        else []
    )
    battery_chan = scriptOp.appendChan("battery") if EMIT_BATTERY else None
    counter_chan = scriptOp.appendChan("counter") if EMIT_COUNTER else None

    if not samples:
        scriptOp.numSamples = 1
        return

    scriptOp.numSamples = len(samples)
    for j, chan in enumerate(eeg_chans):
        for i, s in enumerate(samples):
            chan[i] = s["values"][j]
    for i, s in enumerate(samples):
        if EMIT_GYRO:
            gyro_chans[0][i] = s["gyro"][0]
            gyro_chans[1][i] = s["gyro"][1]
        if EMIT_QUALITY:
            for j, name in enumerate(CHANNELS):
                quality_chans[j][i] = s["quality"][name]
        if EMIT_BATTERY:
            battery_chan[i] = s["battery"] if s["battery"] is not None else 0
        if EMIT_COUNTER:
            counter_chan[i] = s["counter"]
