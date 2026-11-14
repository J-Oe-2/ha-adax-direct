"""Fit the adax_direct duty model from calibration CSVs (`adax-direct calibrate` output) and validate it.

Model: duty = clamp(base + slope * (target - room)_K, 0, 1); power = rated_W * duty.
Prints: cycle period, the least-squares base/slope over complete on->on cycles (cycles longer than 400 s, i.e.
continuous heating, are excluded from the fit), the median plug power while on (rated_W), and per-target energy:
plug-measured vs the model sampled every 60 s (as the integration polls). Enter base/slope/rated_W in the
heater's adax_direct options. Pure, deterministic; reads only the CSVs. Rows with targTemp 0 or missing values
are ignored; rows are grouped by target value.
"""
from __future__ import annotations

import csv
import datetime as dt
import statistics as st
import sys


def load(paths: list[str]) -> list[tuple[dt.datetime, float, float, float]]:
    rows = []
    for p in paths:
        with open(p, newline="") as fh:
            for r in csv.DictReader(fh):
                try:
                    t = dt.datetime.fromisoformat(r["utc"])
                    c, g, w = int(r["currTemp"]) / 100, int(r["targTemp"]) / 100, float(r["plug_W"])
                except (KeyError, ValueError, TypeError):
                    continue
                if g > 0:
                    rows.append((t, c, g, w))
    rows.sort()
    dedup = [r for i, r in enumerate(rows) if i == 0 or r[0] != rows[i - 1][0]]
    return dedup


def by_target(rows):
    groups: dict[float, list] = {}
    for r in rows:
        groups.setdefault(r[2], []).append(r)
    return groups


def run(paths: list[str], on_threshold: float = 100.0) -> int:
    rows = load(paths)
    if len(rows) < 30:
        sys.exit("ERROR: fewer than 30 usable rows")
    on = lambda w: w > on_threshold  # noqa: E731

    cycles = []
    for rs in by_target(rows).values():
        edges = [i for i in range(1, len(rs)) if on(rs[i][3]) and not on(rs[i - 1][3])]
        for i0, i1 in zip(edges, edges[1:]):
            seg = rs[i0:i1 + 1]
            period = (seg[-1][0] - seg[0][0]).total_seconds()
            if period > 400:
                continue
            on_s = sum((seg[k + 1][0] - seg[k][0]).total_seconds() for k in range(len(seg) - 1) if on(seg[k][3]))
            gap = st.mean(g - c for _, c, g, _ in seg[:-1])
            cycles.append((gap, on_s / period, period))
    if len(cycles) < 8:
        sys.exit(f"ERROR: only {len(cycles)} complete cycles — run longer or nearer the setpoint")
    xs, ys = [c[0] for c in cycles], [c[1] for c in cycles]
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        sys.exit("ERROR: all cycles at one gap — use at least two targets")
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    base = my - slope * mx
    rms = st.pstdev([y - (base + slope * x) for x, y in zip(xs, ys)])
    watts = st.median([w for *_, w in rows if w > 0.85 * max(r[3] for r in rows)])
    print(f"{len(rows)} rows, {len(cycles)} cycles, period median {st.median(c[2] for c in cycles):.0f} s")
    print(f"duty = {base:.3f} + {slope:.3f} * gap_K   (rms residual {rms:.3f}; 100% at {(1 - base) / slope:+.2f} K, "
          f"0% at {-base / slope:+.2f} K)")
    print(f"rated power (median while on): {watts:.0f} W")
    print(f"→ adax_direct options: rated_power_w {watts:.0f}, duty_base {base:.2f}, duty_slope {slope:.2f}")

    model = lambda c, g: watts * min(1.0, max(0.0, base + slope * (g - c)))  # noqa: E731
    print("validation (energy per target; model sampled every 60 s):")
    for g, rs in sorted(by_target(rows).items()):
        if len(rs) < 10:
            continue
        e_true = sum(rs[k][3] * (rs[k + 1][0] - rs[k][0]).total_seconds() for k in range(len(rs) - 1)) / 3.6e6
        e_mod, last, nxt = 0.0, None, rs[0][0]
        for t, c, gg, _ in rs:
            if t >= nxt:
                if last:
                    e_mod += last[1] * (t - last[0]).total_seconds()
                last, nxt = (t, model(c, gg)), t + dt.timedelta(seconds=60)
        e_mod /= 3.6e6
        mins = (rs[-1][0] - rs[0][0]).total_seconds() / 60
        err = f"{e_mod / e_true - 1:+.0%}" if e_true > 0 else "n/a"
        print(f"  target {g:4.1f} °C, {mins:4.0f} min: plug {e_true:.3f} kWh, model {e_mod:.3f} kWh ({err})")
    return 0

