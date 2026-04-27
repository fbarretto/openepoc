from __future__ import annotations

import sys

from .diagnostics import enumerate_dongles, looks_sane, try_capture
from .reader import CHANNELS

PHYSICAL_CHECKLIST = """\
Physical setup checklist - Emotiv EPOC 1.0
------------------------------------------
1. Charge the headset.
   Mini-USB port is on the back of the headband. First charge takes about
   6 hours. The headset LED turns off when fully charged.

2. Hydrate the felt pads.
   Each of the 16 felt pads (14 EEG + 2 reference) must be soaked in saline
   solution. Multipurpose contact lens solution works well. Squeeze out the
   excess so the pads are damp, not dripping.

3. Assemble the sensors.
   Snap each saline-soaked felt pad into its gold sensor housing, then click
   each sensor into a numbered socket on the headset arm. The two reference
   sensors (CMS / DRL) go on the rubber arms that sit behind your earlobes.

4. Insert the USB dongle into your Mac.
   Use the dongle that came in the same box as the headset - they are
   factory-paired and not interchangeable.

5. Power on the headset.
   Slide the switch on the back-left of the headband. The LED behind the
   switch should glow solid (not blinking). The dongle LED should also go
   solid once it sees the headset.

6. Put the headset on.
   AF3 / AF4 sit on your forehead just above the eyebrows. The two rubber
   arms with reference sensors clip behind your earlobes. Adjust the band
   until every sensor is in firm but comfortable contact with your scalp.
"""


def _step(n: int, total: int, label: str) -> None:
    print(f"[{n}/{total}] {label}", flush=True)


def run(skip_checklist: bool = False) -> int:
    total = 5

    if not skip_checklist:
        print(PHYSICAL_CHECKLIST)
        try:
            input("Press Enter once everything above is done (Ctrl+C to abort)... ")
        except (KeyboardInterrupt, EOFError):
            print()
            return 1
        print()

    _step(1, total, "checking python deps")
    try:
        import hid  # noqa: F401
        import Crypto  # noqa: F401
    except ImportError as e:
        print(f"  FAIL: {e}")
        print("  fix: pip install -e .")
        return 1
    print("  ok")

    _step(2, total, "scanning USB HID devices for Emotiv dongle")
    devs = enumerate_dongles()
    if not devs:
        print("  FAIL: no Emotiv-like HID device found")
        print("  fix: plug the dongle in. verify the OS sees it with:")
        print("    system_profiler SPUSBDataType | grep -i -A4 emotiv")
        print("  on Apple Silicon, also check:")
        print("    System Settings > Privacy & Security > Allow accessories to connect")
        return 1
    for d in devs:
        print(
            f"  found: VID={d['vendor_id']:#06x} PID={d['product_id']:#06x} "
            f"product={d.get('product_string')!r} "
            f"manuf={d.get('manufacturer_string')!r}"
        )

    _step(3, total, "trying consumer AES key schema (8s capture window)")
    samples, qualities, battery, err = try_capture(is_research=False)
    if err:
        print(f"  ERROR: {err}")
    if not samples:
        print("  FAIL: dongle is visible but no packets arrived")
        print("  fix:")
        print("   - power on the headset (switch on back-left); LED must be solid")
        print("   - grant Input Monitoring to your terminal in")
        print("     System Settings > Privacy & Security > Input Monitoring")
        print(f"     (interpreter: {sys.executable})")
        print("   - quit any EmotivPRO / Xavier / Emotiv Control Panel apps")
        return 1
    sane, detail = looks_sane(samples)
    print(f"  got {len(samples)} packets; {detail}")

    schema = "consumer"
    if not sane:
        _step(4, total, "values look unsound; retrying with research schema")
        samples_r, qualities_r, battery_r, err_r = try_capture(is_research=True)
        if err_r:
            print(f"  ERROR: {err_r}")
        sane_r, detail_r = looks_sane(samples_r)
        print(f"  research schema: {detail_r}")
        if sane_r:
            samples, qualities, battery = samples_r, qualities_r, battery_r
            schema = "research"
            sane = True
        else:
            print("  FAIL: neither schema produces sane values")
            print("  likely causes:")
            print("   - dongle/headset pair mismatch (do not mix dongles)")
            print("   - unit uses a non-standard key derivation")
            print("  open an issue with your headset serial prefix and a hex dump")
            print("  of one raw HID report.")
            return 1
    else:
        _step(4, total, "schema validation")
        print("  consumer schema PASSED")

    _step(5, total, "summary")
    last_q = qualities[-1] if qualities else [0] * len(CHANNELS)
    q_line = " ".join(f"{c}={q // 540}" for c, q in zip(CHANNELS, last_q))
    print(f"  schema:   {schema}")
    print(
        f"  battery:  {battery}%"
        if battery is not None
        else "  battery:  unknown"
    )
    print(f"  contacts: {q_line}    (0 = nothing, 4 = excellent)")
    print()
    print("ready. next:")
    prefix = "" if schema == "consumer" else "--research "
    print(f"  openepoc {prefix}verify --count 50")
    print(f"  openepoc {prefix}stream --lsl --osc")
    return 0
