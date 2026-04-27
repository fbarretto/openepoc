# 01 — Record N seconds to CSV

Records the headset's 14 EEG channels (plus counter, gyro, battery) to a
CSV file. Default 5 seconds, default `recording.csv`. Pure stdlib output —
the only dependency is openepoc itself.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python record.py                            # 5s -> recording.csv
python record.py session.csv --duration 60  # 60s -> session.csv
python record.py - --duration 5             # 5s -> stdout
python record.py --research                 # research-edition AES schema
python record.py --serial SN20130125000472  # explicit headset (multi-dongle)
```

## Output

```
t,counter,battery,gyro_x,gyro_y,AF3,F7,F3,FC5,T7,P7,O1,O2,P8,T8,FC6,F4,F8,AF4
1777249956.260644,82,,0,3,496.00,379.00,1030.00,...
```

`t` is wall-clock seconds. `battery` is empty when the dongle didn't include
a battery byte in that packet (it ticks through periodically). EEG values
are raw 14-bit signed; multiply by ~0.51 to convert to microvolts.
