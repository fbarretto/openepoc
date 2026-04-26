from __future__ import annotations

import time
from typing import Iterator, TypedDict

CHANNELS = (
    "AF3", "F7", "F3", "FC5", "T7", "P7", "O1",
    "O2", "P8", "T8", "FC6", "F4", "F8", "AF4",
)
SAMPLE_RATE = 128


class Sample(TypedDict):
    t: float
    values: list[float]
    quality: list[int]
    gyro: tuple[int, int]
    battery: int


def read(is_research: bool = False) -> Iterator[Sample]:
    from emokit.emotiv import Emotiv

    with Emotiv(display_output=False, is_research=is_research) as headset:
        while True:
            packet = headset.dequeue()
            if packet is None:
                time.sleep(0.001)
                continue
            yield Sample(
                t=time.time(),
                values=[float(packet.sensors[c]["value"]) for c in CHANNELS],
                quality=[int(packet.sensors[c]["quality"]) for c in CHANNELS],
                gyro=(int(packet.gyro_x), int(packet.gyro_y)),
                battery=int(packet.battery),
            )
