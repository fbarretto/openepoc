from __future__ import annotations

import statistics
import time

from .reader import CHANNELS, KNOWN_DONGLES, read_from_hid


def enumerate_dongles() -> list[dict]:
    """Return all connected Emotiv-like HID devices (every known VID/PID pair)."""
    import hid

    matches: list[dict] = []
    seen_vids = {v for v, _ in KNOWN_DONGLES}
    for d in hid.enumerate():
        vid = d.get("vendor_id")
        product = (d.get("product_string") or "").lower()
        manuf = (d.get("manufacturer_string") or "").lower()
        if (vid, d.get("product_id")) in KNOWN_DONGLES:
            matches.append(d)
            continue
        if vid in seen_vids:
            matches.append(d)
            continue
        if "emotiv" in product or "emotiv" in manuf:
            matches.append(d)
    return matches


def looks_sane(values: list[list[float]]) -> tuple[bool, str]:
    """Crude check on a batch of sample values to flag flat or out-of-range data."""
    flat = [v for sample in values for v in sample]
    if not flat:
        return False, "no samples"
    mean = statistics.mean(flat)
    stdev = statistics.pstdev(flat)
    if stdev < 1e-3:
        return False, f"flat (mean={mean:.1f}, stdev={stdev:.4f})"
    if mean < 100 or mean > 32000:
        return False, f"out of expected range (mean={mean:.1f})"
    return True, f"mean={mean:.1f} stdev={stdev:.1f}"


def try_capture(
    is_research: bool = False,
    n: int = 32,
    timeout_s: float = 8.0,
    serial: str | None = None,
) -> tuple[list[list[float]], list[list[int]], int | None, str | None]:
    """
    Capture up to N samples from a connected dongle, with a wall-clock timeout.

    Returns (values, qualities, last_battery, error_message_or_None).
    Use this for health-check-style diagnostics; for real streaming, use
    read_from_hid() directly.
    """
    samples: list[list[float]] = []
    qualities: list[list[int]] = []
    battery: int | None = None
    try:
        deadline = time.time() + timeout_s
        for s in read_from_hid(serial=serial, is_research=is_research):
            samples.append(s["values"])
            qualities.append([s["quality"][c] for c in CHANNELS])
            if s["battery"] is not None:
                battery = s["battery"]
            if len(samples) >= n or time.time() >= deadline:
                break
    except Exception as e:
        return samples, qualities, battery, f"{type(e).__name__}: {e}"
    return samples, qualities, battery, None
