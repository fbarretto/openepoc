"""Record N seconds of EEG to CSV.

Usage:
    python 01_record_csv.py [output.csv] [--duration 5] [--research]

Output columns:
    t,counter,battery,gyro_x,gyro_y,AF3,F7,F3,FC5,T7,P7,O1,O2,P8,T8,FC6,F4,F8,AF4

Requires:
    pip install openepoc      # core only, no extras needed
"""

from __future__ import annotations

import argparse
import csv
import sys
import time

from openepoc import CHANNELS, read_from_hid


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("output", nargs="?", default="recording.csv")
    p.add_argument("--duration", type=float, default=5.0)
    p.add_argument("--research", action="store_true")
    p.add_argument("--serial", default=None)
    args = p.parse_args()

    print(f"recording {args.duration}s to {args.output}", file=sys.stderr)
    n = 0
    deadline = time.time() + args.duration

    with open(args.output, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "counter", "battery", "gyro_x", "gyro_y", *CHANNELS])
        for s in read_from_hid(serial=args.serial, is_research=args.research):
            w.writerow([
                f"{s['t']:.6f}",
                s["counter"],
                s["battery"] if s["battery"] is not None else "",
                s["gyro"][0],
                s["gyro"][1],
                *(f"{v:.2f}" for v in s["values"]),
            ])
            n += 1
            if time.time() >= deadline:
                break

    print(f"wrote {n} samples ({n / args.duration:.1f} Hz)", file=sys.stderr)


if __name__ == "__main__":
    main()
