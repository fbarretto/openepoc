from __future__ import annotations

import argparse
import sys

from .reader import CHANNELS, read


def cmd_verify(args: argparse.Namespace) -> None:
    print("channels:", ", ".join(CHANNELS), file=sys.stderr)
    n = 0
    for sample in read(is_research=args.research):
        print(sample["t"], sample["values"], sample["battery"])
        n += 1
        if n >= args.count:
            break


def cmd_stream(args: argparse.Namespace) -> None:
    if not (args.lsl or args.osc):
        raise SystemExit("pass --lsl and/or --osc to select an outlet")

    outlet = None
    osc_client = None
    if args.lsl:
        from .lsl_outlet import make_outlet
        outlet = make_outlet()
        print(f"lsl outlet ready: EmotivEPOC ({len(CHANNELS)}ch)", file=sys.stderr)
    if args.osc:
        from .osc_outlet import make_client, send_bundle, send_per_channel
        osc_client = make_client(args.osc_host, args.osc_port)
        osc_send = send_per_channel if args.osc_per_channel else send_bundle
        print(f"osc client: {args.osc_host}:{args.osc_port} {args.osc_address}",
              file=sys.stderr)

    for sample in read(is_research=args.research):
        if outlet is not None:
            outlet.push_sample(sample["values"])
        if osc_client is not None:
            osc_send(osc_client, sample["values"], args.osc_address)


def main() -> None:
    p = argparse.ArgumentParser(prog="eeg-exp")
    p.add_argument("--research", action="store_true",
                   help="use research-edition AES key schema (default: consumer)")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="print N raw samples to stdout")
    v.add_argument("--count", type=int, default=20)
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser("stream", help="stream samples to LSL and/or OSC")
    s.add_argument("--lsl", action="store_true")
    s.add_argument("--osc", action="store_true")
    s.add_argument("--osc-host", default="127.0.0.1")
    s.add_argument("--osc-port", type=int, default=9000)
    s.add_argument("--osc-address", default="/eeg")
    s.add_argument("--osc-per-channel", action="store_true",
                   help="emit one OSC message per channel under <address>/<label>")
    s.set_defaults(func=cmd_stream)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
