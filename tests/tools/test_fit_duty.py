"""U-12: the duty-curve fit recovers the curve that generated the data."""
import csv
import datetime as dt

from adax_direct_tools.cli import main

HEADER = ["utc", "phase", "currTemp", "targTemp", "pow", "energ", "plug_W", "plug_reported"]


def write_csv(path):
    t = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    rows = []
    for phase, (gap, on_rows) in enumerate(((0.0, 2), (0.5, 4), (1.0, 5), (1.5, 7)), 1):
        for i in range(180):                       # 30 min at one row per 10 s
            utc = t.isoformat()
            plug = 1000 if i % 10 < on_rows else 0
            rows.append([utc, phase, round((20 - gap) * 100), 2000, 0, 0, plug, utc])
            t += dt.timedelta(seconds=10)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerows(rows)


def test_fit_duty_recovers_curve(tmp_path, capsys):
    path = tmp_path / "run.csv"
    write_csv(path)
    assert main(["fit", str(path)]) == 0
    out = capsys.readouterr().out
    assert "rated_power_w 1000, duty_base 0.21, duty_slope 0.32" in out
