"""
Composable, stateful real-time filters for EEG sample streams.

Each Filter holds per-channel IIR state across calls (so DC offsets and
phase relationships survive across packets). A Pipeline chains filters
and supports runtime toggling of any filter via its .enabled attribute.

Requires the [filters] extra:
    pip install "openepoc[filters]"

Typical usage:

    from openepoc import read_from_hid
    from openepoc.filters import Pipeline, HighPass, Notch, LowPass

    pipe = Pipeline([
        HighPass(0.5),    # drop DC drift
        Notch(60),        # mains hum (US: 60, EU: 50)
        LowPass(40),      # cut high-frequency noise / EMG
    ])

    for sample in pipe.apply(read_from_hid()):
        sample["values"]   # filtered, same shape as before

    # Toggle live (e.g. from another thread):
    pipe[1].enabled = False    # bypass the notch

For TouchDesigner Script CHOPs, build the Pipeline at module scope and
call pipe.process(values) inside onCook against the drained samples.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from .reader import CHANNELS, SAMPLE_RATE, Sample


def _require_scipy():
    try:
        import numpy as np
        from scipy import signal as sps
    except ImportError as e:
        raise ImportError(
            "openepoc.filters requires numpy and scipy. "
            "Install with: pip install 'openepoc[filters]'"
        ) from e
    return np, sps


class _IIRFilter:
    """
    Stateful IIR filter applied per-channel.

    Holds one zi state vector per channel so consecutive calls produce
    a continuous filtered signal across packet boundaries.
    """

    def __init__(self, sos, n_channels: int = len(CHANNELS)):
        np, sps = _require_scipy()
        self.sos = sos
        self._np = np
        self._sps = sps
        zi_proto = sps.sosfilt_zi(sos)
        self.zi = np.array([zi_proto.copy() for _ in range(n_channels)])
        self.enabled: bool = True

    def reset(self) -> None:
        """Zero the per-channel state. Call this if filtered output spikes
        after toggling enabled or after a discontinuity in the input."""
        np, sps = self._np, self._sps
        zi_proto = sps.sosfilt_zi(self.sos)
        for i in range(len(self.zi)):
            self.zi[i] = zi_proto.copy()

    def process(self, values):
        """Filter one sample (one value per channel). Returns a numpy array."""
        np, sps = self._np, self._sps
        if not self.enabled:
            return np.asarray(values, dtype=np.float64)
        arr = np.asarray(values, dtype=np.float64)
        out = np.empty_like(arr)
        for i in range(len(arr)):
            y, self.zi[i] = sps.sosfilt(self.sos, [arr[i]], zi=self.zi[i])
            out[i] = y[0]
        return out


def HighPass(
    cutoff_hz: float,
    *,
    order: int = 4,
    sample_rate: float = SAMPLE_RATE,
    n_channels: int = len(CHANNELS),
) -> _IIRFilter:
    """Butterworth high-pass. Use ~0.5 Hz to remove DC / slow drift."""
    np, sps = _require_scipy()
    sos = sps.butter(order, cutoff_hz, btype="highpass", fs=sample_rate, output="sos")
    return _IIRFilter(sos, n_channels)


def LowPass(
    cutoff_hz: float,
    *,
    order: int = 4,
    sample_rate: float = SAMPLE_RATE,
    n_channels: int = len(CHANNELS),
) -> _IIRFilter:
    """Butterworth low-pass. ~30-45 Hz cuts EMG and HF noise without losing beta."""
    np, sps = _require_scipy()
    sos = sps.butter(order, cutoff_hz, btype="lowpass", fs=sample_rate, output="sos")
    return _IIRFilter(sos, n_channels)


def BandPass(
    low_hz: float,
    high_hz: float,
    *,
    order: int = 4,
    sample_rate: float = SAMPLE_RATE,
    n_channels: int = len(CHANNELS),
) -> _IIRFilter:
    """Butterworth band-pass. e.g. (8, 13) for alpha, (13, 30) for beta."""
    np, sps = _require_scipy()
    sos = sps.butter(
        order, [low_hz, high_hz], btype="bandpass", fs=sample_rate, output="sos"
    )
    return _IIRFilter(sos, n_channels)


def Notch(
    freq_hz: float,
    *,
    q: float = 30.0,
    sample_rate: float = SAMPLE_RATE,
    n_channels: int = len(CHANNELS),
) -> _IIRFilter:
    """Single-frequency notch. Use 60 (US) or 50 (EU) to kill mains hum."""
    np, sps = _require_scipy()
    b, a = sps.iirnotch(freq_hz, q, fs=sample_rate)
    sos = sps.tf2sos(b, a)
    return _IIRFilter(sos, n_channels)


class Pipeline:
    """
    Chains filters in order. Each filter's `.enabled` flag is honored, so
    you can toggle any stage without rebuilding the pipeline.

    Indexing returns the underlying filter so you can flip flags directly:

        pipe = Pipeline([HighPass(0.5), Notch(60), LowPass(40)])
        pipe[1].enabled = False    # bypass the notch
        pipe.append(BandPass(8, 13))   # add an alpha band-pass at the end
    """

    def __init__(self, filters: list[_IIRFilter] | None = None):
        self.filters: list[_IIRFilter] = list(filters) if filters else []

    def __getitem__(self, i: int) -> _IIRFilter:
        return self.filters[i]

    def __len__(self) -> int:
        return len(self.filters)

    def append(self, f: _IIRFilter) -> None:
        self.filters.append(f)

    def reset(self) -> None:
        for f in self.filters:
            f.reset()

    def process(self, values):
        """Run one sample through every enabled filter; returns ndarray."""
        out = values
        for f in self.filters:
            if f.enabled:
                out = f.process(out)
        return out

    def apply(self, samples: Iterable[Sample]) -> Iterator[Sample]:
        """Wrap a Sample iterator, yielding samples with filtered 'values'."""
        np, _ = _require_scipy()
        for s in samples:
            v = self.process(s["values"])
            yield {**s, "values": v.tolist() if hasattr(v, "tolist") else list(v)}
