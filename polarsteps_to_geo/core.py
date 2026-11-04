"""Read Polarsteps locations and export a chronologically sorted track."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import tempfile
from typing import TextIO, Callable


@dataclass(frozen=True, slots=True)
class Point:
    lat: float
    lon: float
    time: datetime


def read_points(path: Path) -> list[Point]:
    """Validate every record; preserve original whole-second timestamp semantics."""
    with path.open(encoding="utf-8-sig") as source:
        data = json.load(source)
    if not isinstance(data, dict) or not isinstance(data.get("locations"), list):
        raise ValueError("Expected an object containing a 'locations' array.")
    points = []
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    for index, record in enumerate(data["locations"]):
        try:
            if not isinstance(record, dict):
                raise ValueError("expected an object")
            values = {}
            for key in ("lat", "lon", "time"):
                value = record.get(key)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"'{key}' must be a number")
                if not math.isfinite(value):
                    raise ValueError(f"'{key}' must be finite")
                values[key] = value
            if not -90 <= values["lat"] <= 90:
                raise ValueError("latitude must be between -90 and 90")
            if not -180 <= values["lon"] <= 180:
                raise ValueError("longitude must be between -180 and 180")
            timestamp = epoch + timedelta(seconds=int(values["time"]))
            points.append(Point(float(values["lat"]), float(values["lon"]), timestamp))
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"locations[{index}]: {exc}") from exc
    points.sort(key=lambda point: point.time)
    return points


def write_gpx(points: list[Point], stream: TextIO) -> None:
    """Write GPX 1.1 incrementally, without constructing a second XML tree."""
    stream.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    stream.write('<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="polarsteps-to-geo">\n')
    stream.write('  <trk><trkseg>\n')
    for point in points:
        timestamp = point.time.isoformat().replace("+00:00", "Z")
        stream.write(f'    <trkpt lat="{point.lat}" lon="{point.lon}"><time>{timestamp}</time></trkpt>\n')
    stream.write('  </trkseg></trk>\n</gpx>\n')


# Additional exporters use the same Point model and callable signature.
EXPORTERS: dict[str, Callable[[list[Point], TextIO], None]] = {"gpx": write_gpx}


def convert(source: str | Path, destination: str | Path | None = None) -> tuple[Path, int]:
    source = Path(source)
    destination = Path(destination) if destination is not None else source.with_suffix(".gpx")
    if source.resolve() == destination.resolve() or (
        source.exists() and destination.exists() and os.path.samefile(source, destination)
    ):
        raise ValueError("Input and output must be different files.")
    kind = destination.suffix.lower().lstrip(".")
    if kind not in EXPORTERS:
        raise ValueError(f"Unsupported output format '{kind}'. Supported: {', '.join(EXPORTERS)}")
    points = read_points(source)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            dir=destination.parent, prefix=".polarsteps-", suffix=".tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            EXPORTERS[kind](points, stream)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination, len(points)
