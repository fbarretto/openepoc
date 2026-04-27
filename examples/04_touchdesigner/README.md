# TouchDesigner integration

OSC is the cleanest path from `openepoc` into TouchDesigner. The host machine
runs `examples/02_stream_osc.py`, TD listens with an `OSC In CHOP`. Both
machines can be the same physical box (loopback) or different ones on the same
LAN.

This folder doesn't ship a binary `.tox` — TD components are saved from inside
TouchDesigner and not generated from text. What follows is the network recipe
that takes ~2 minutes to build the first time.

## 1. Start the OSC stream on the capture host

```bash
cd /path/to/openepoc
source .venv/bin/activate
python examples/02_stream_osc.py --per-channel
```

Default destination is `127.0.0.1:9000`, address pattern `/eeg/<channel>`.
With `--per-channel`, each EEG channel arrives at its own OSC address
(`/eeg/AF3`, `/eeg/F7`, ...) which makes TD setup trivial. Without
`--per-channel`, all 14 channels arrive in one bundled message at `/eeg`,
and TD will create channels named `chan1..chan14` that you'll want to rename.

## 2. In TouchDesigner: minimal network

```
[ OSC In CHOP ] -> [ Null CHOP ] -> [ rest of your network ]
```

### OSC In CHOP parameters

- **Network Port**: `9000`
- **Active**: `On`

That's it for per-channel mode. TD discovers each `/eeg/<label>` and creates
one CHOP channel per name. AF3, F7, etc. show up automatically.

For bundled mode (without `--per-channel`):
- The CHOP gets channels named `chan1..chan14`
- Use a `Rename CHOP` after it with the from/to lists
  (`From: chan1 chan2 chan3 ...`, `To: AF3 F7 F3 FC5 ...`)
- Order matches `openepoc.CHANNELS`: `AF3, F7, F3, FC5, T7, P7, O1, O2, P8, T8, FC6, F4, F8, AF4`

## 3. Cross-machine setup

If TD runs on a different box than the capture host, point the streamer at
TD's IP:

```bash
python examples/02_stream_osc.py --per-channel --host 192.168.1.42
```

Make sure firewall allows UDP on the chosen port.

## 4. What to do with the channels

Once channels reach TD, anything is fair game:

- `Math CHOP` to scale microvolts into 0..1 for parameter binding
- `Filter CHOP` for moving averages / smoothing (raw EEG is noisy)
- `Analyze CHOP` for FFT into bands (alpha/beta/theta)
- `Audio Spectrum CHOP` for sonification
- Per-channel CHOP-to-DAT exports for logging

A common starting pattern: low-pass filter to ~30 Hz to drop high-frequency
noise, then `Analyze CHOP` to turn each channel into a band-power feed
(alpha / beta / theta), bind those to visual parameters.

## 5. Health check

If channels are dead-flat at 0:

- Run `openepoc wizard --no-checklist` on the capture host to confirm packets
  are arriving from the dongle in the first place
- Check the OSC In CHOP's `Bytes In` parameter — if it's 0, packets aren't
  reaching TD: firewall, port, or wrong host
- Confirm felt pads are saline-soaked and the headset is on

If the stream rate looks wrong (TD shows 0.something Hz instead of 128 Hz),
TD is sometimes slow to compute the rate display — wait 5 seconds.
