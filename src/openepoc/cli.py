from __future__ import annotations

import argparse
import sys

from .reader import CHANNELS, read_from_hid


def cmd_verify(args: argparse.Namespace) -> None:
    print("channels:", ", ".join(CHANNELS), file=sys.stderr)
    n = 0
    for sample in read_from_hid(serial=args.serial, is_research=args.research):
        print(sample["t"], sample["values"], sample["battery"])
        n += 1
        if n >= args.count:
            break


def cmd_wizard(args: argparse.Namespace) -> None:
    from .wizard import run

    raise SystemExit(run(skip_checklist=args.no_checklist))


def cmd_stream(args: argparse.Namespace) -> None:
    if not (args.lsl or args.osc):
        raise SystemExit("pass --lsl and/or --osc to select an outlet")

    outlet = None
    osc_client = None
    osc_send = None
    if args.lsl:
        try:
            from .lsl_outlet import make_outlet
        except ImportError:
            raise SystemExit(
                "LSL support requires pylsl. Install with:\n"
                "  pip install 'openepoc[lsl]'"
            )
        outlet = make_outlet()
        print(f"lsl outlet ready: EmotivEPOC ({len(CHANNELS)}ch)", file=sys.stderr)
    if args.osc:
        try:
            from .osc_outlet import make_client, send_bundle, send_per_channel
        except ImportError:
            raise SystemExit(
                "OSC support requires python-osc. Install with:\n"
                "  pip install 'openepoc[osc]'"
            )
        osc_client = make_client(args.osc_host, args.osc_port)
        osc_send = send_per_channel if args.osc_per_channel else send_bundle
        print(
            f"osc client: {args.osc_host}:{args.osc_port} {args.osc_address}",
            file=sys.stderr,
        )

    for sample in read_from_hid(serial=args.serial, is_research=args.research):
        if outlet is not None:
            outlet.push_sample(sample["values"])
        if osc_client is not None:
            osc_send(osc_client, sample["values"], args.osc_address)


def main() -> None:
    p = argparse.ArgumentParser(prog="openepoc")
    p.add_argument(
        "--research",
        action="store_true",
        help="use research-edition AES key schema (default: consumer)",
    )
    p.add_argument(
        "--serial",
        default=None,
        help="headset serial (auto-detected from the dongle if omitted)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser(
        "wizard", help="interactive connection check + setup checklist"
    )
    w.add_argument(
        "--no-checklist",
        action="store_true",
        help="skip the physical-setup preamble and Enter prompt",
    )
    w.set_defaults(func=cmd_wizard)

    v = sub.add_parser("verify", help="print N raw samples to stdout")
    v.add_argument("--count", type=int, default=20)
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser("stream", help="stream samples to LSL and/or OSC")
    s.add_argument("--lsl", action="store_true")
    s.add_argument("--osc", action="store_true")
    s.add_argument("--osc-host", default="127.0.0.1")
    s.add_argument("--osc-port", type=int, default=9000)
    s.add_argument("--osc-address", default="/eeg")
    s.add_argument(
        "--osc-per-channel",
        action="store_true",
        help="emit one OSC message per channel under <address>/<label>",
    )
    s.set_defaults(func=cmd_stream)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
