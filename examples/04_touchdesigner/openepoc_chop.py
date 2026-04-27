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

# Channel-group toggles default to True if the corresponding custom parameter
# hasn't been created yet (i.e. user hasn't clicked Setup Parameters). Once
# the parameters exist, their UI values override these defaults — so you can
# turn channel groups on and off live from TD's parameter editor without
# editing this file.
GYRO_CHANNELS = ("gyro_x", "gyro_y")
QUALITY_CHANNELS = tuple(f"q_{c}" for c in CHANNELS)


def _emit(scriptOp, par_name: str, default: bool = True) -> bool:
    p = getattr(scriptOp.par, par_name, None)
    if p is None:
        return default
    return bool(p.eval())

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
    # IMPORTANT: this only runs when you click "Setup Parameters" in the
    # Script CHOP's parameter panel, not when this DAT is edited.
    try:
        # Tick page: forces continuous cooking via an absTime.seconds
        # dependency. Without this, a Script CHOP with no operator inputs
        # cooks once at startup and never again.
        tick_page = scriptOp.appendCustomPage("Tick")
        tick_result = tick_page.appendFloat("Tick", label="Tick")
        tick_par = (
            tick_result[0]
            if isinstance(tick_result, (list, tuple))
            else tick_result
        )
        tick_par.default = 0.0
        tick_par.defaultExpr = "absTime.seconds"
        tick_par.defaultMode = ParMode.EXPRESSION

        # Channels page: toggles for each output group. Flip these in TD's
        # parameter editor to filter what the CHOP exposes. Defaults: all on.
        ch_page = scriptOp.appendCustomPage("Channels")
        for name, label in (
            ("Eeg", "EEG (14 ch)"),
            ("Gyro", "Gyro (gyro_x, gyro_y)"),
            ("Quality", "Contact quality (q_*)"),
            ("Battery", "Battery"),
            ("Counter", "Packet counter"),
        ):
            par = ch_page.appendToggle(name, label=label)
            par = par[0] if isinstance(par, (list, tuple)) else par
            par.default = True
    except Exception as e:
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

    emit_eeg = _emit(scriptOp, "Eeg")
    emit_gyro = _emit(scriptOp, "Gyro")
    emit_quality = _emit(scriptOp, "Quality")
    emit_battery = _emit(scriptOp, "Battery")
    emit_counter = _emit(scriptOp, "Counter")

    scriptOp.clear()
    scriptOp.rate = SAMPLE_RATE

    eeg_chans = [scriptOp.appendChan(name) for name in CHANNELS] if emit_eeg else []
    gyro_chans = (
        [scriptOp.appendChan(name) for name in GYRO_CHANNELS] if emit_gyro else []
    )
    quality_chans = (
        [scriptOp.appendChan(name) for name in QUALITY_CHANNELS]
        if emit_quality
        else []
    )
    battery_chan = scriptOp.appendChan("battery") if emit_battery else None
    counter_chan = scriptOp.appendChan("counter") if emit_counter else None

    if not samples:
        scriptOp.numSamples = 1
        return

    scriptOp.numSamples = len(samples)
    if emit_eeg:
        for j, chan in enumerate(eeg_chans):
            for i, s in enumerate(samples):
                chan[i] = s["values"][j]
    for i, s in enumerate(samples):
        if emit_gyro:
            gyro_chans[0][i] = s["gyro"][0]
            gyro_chans[1][i] = s["gyro"][1]
        if emit_quality:
            for j, name in enumerate(CHANNELS):
                quality_chans[j][i] = s["quality"][name]
        if emit_battery:
            battery_chan[i] = s["battery"] if s["battery"] is not None else 0
        if emit_counter:
            counter_chan[i] = s["counter"]
