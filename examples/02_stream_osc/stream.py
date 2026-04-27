"""Stream EEG samples over OSC.

Bundled mode (default): one OSC message at /eeg with 14 floats per packet.
Per-channel mode (--per-channel): one message per channel under /eeg/<label>.

Usage:
    python 02_stream_osc.py
    python 02_stream_osc.py --host 127.0.0.1 --port 9000
    python 02_stream_osc.py --per-channel --address /brain
    python 02_stream_osc.py --research

Receive end (TouchDesigner, Max, p5.js, Unity, etc.) listens on the same host:port.
For a TouchDesigner recipe, see examples/04_touchdesigner/README.md.

Requires:
    pip install "openepoc[osc]"
"""

from __future__ import annotations

import argparse
import sys

from openepoc import CHANNELS, read_from_hid
from openepoc.osc_outlet import make_client, send_bundle, send_per_channel


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9000)
    p.add_argument("--address", default="/eeg")
    p.add_argument("--per-channel", action="store_true",
                   help=f"emit one message per channel under <address>/<label> "
                        f"({', '.join(CHANNELS[:3])}, ...)")
    p.add_argument("--research", action="store_true")
    p.add_argument("--serial", default=None)
    args = p.parse_args()

    client = make_client(args.host, args.port)
    send = send_per_channel if args.per_channel else send_bundle
    mode = "per-channel" if args.per_channel else "bundled"
    print(
        f"streaming {len(CHANNELS)}ch ({mode}) -> {args.host}:{args.port}{args.address}",
        file=sys.stderr,
    )

    try:
        for s in read_from_hid(serial=args.serial, is_research=args.research):
            send(client, s["values"], args.address)
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)


if __name__ == "__main__":
    main()
