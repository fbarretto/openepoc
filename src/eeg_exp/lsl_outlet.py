from __future__ import annotations

from .reader import CHANNELS, SAMPLE_RATE


def make_outlet(name: str = "EmotivEPOC", source_id: str = "emotiv-epoc-1"):
    from pylsl import StreamInfo, StreamOutlet

    info = StreamInfo(
        name=name,
        type="EEG",
        channel_count=len(CHANNELS),
        nominal_srate=SAMPLE_RATE,
        channel_format="float32",
        source_id=source_id,
    )
    channels = info.desc().append_child("channels")
    for label in CHANNELS:
        ch = channels.append_child("channel")
        ch.append_child_value("label", label)
        ch.append_child_value("unit", "microvolts")
        ch.append_child_value("type", "EEG")
    return StreamOutlet(info)
