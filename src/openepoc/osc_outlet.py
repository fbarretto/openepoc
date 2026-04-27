from __future__ import annotations

from .reader import CHANNELS


def make_client(host: str = "127.0.0.1", port: int = 9000):
    from pythonosc.udp_client import SimpleUDPClient

    return SimpleUDPClient(host, port)


def send_bundle(client, values, address: str = "/eeg") -> None:
    client.send_message(address, values)


def send_per_channel(client, values, prefix: str = "/eeg") -> None:
    for label, value in zip(CHANNELS, values):
        client.send_message(f"{prefix}/{label}", value)
