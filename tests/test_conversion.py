import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from polarsteps_to_geo.core import convert, read_points, EXPORTERS
from polarsteps_to_geo.cli import main


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "locations.json"

    def write(self, data):
        self.source.write_text(json.dumps(data), encoding="utf-8")
        return self.source

    def test_sorted_gpx_and_default_path(self):
        self.write({"locations": [
            {"lat":52, "lon":4, "time":100.9},
            {"lat":53, "lon":5, "time":-0.9},
            {"lat":54, "lon":6, "time":100.1}]})
        output, count = convert(self.source)
        self.assertEqual(count, 3)
        self.assertEqual(output, self.source.with_suffix(".gpx"))
        root = ET.parse(output).getroot()
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        points = root.findall("g:trk/g:trkseg/g:trkpt", ns)
        self.assertEqual([p.attrib["lat"] for p in points], ["53.0", "52.0", "54.0"])
        self.assertEqual(points[0].find("g:time", ns).text, "1970-01-01T00:00:00Z")

    def test_empty(self):
        self.write({"locations": []})
        self.assertEqual(convert(self.source)[1], 0)

    def test_invalid_records_preserve_existing_output(self):
        output = self.source.with_suffix(".gpx")
        output.write_text("keep")
        for record in [None, {}, {"lat":91,"lon":0,"time":0},
                       {"lat":0,"lon":181,"time":0},
                       {"lat":True,"lon":0,"time":0},
                       {"lat":0,"lon":0,"time":float("nan")},
                       {"lat":0,"lon":0,"time":1e100},
                       {"lat":"1","lon":0,"time":0}]:
            with self.subTest(record=record):
                self.write({"locations":[record]})
                with self.assertRaisesRegex(ValueError, r"locations\[0\]"):
                    convert(self.source)
                self.assertEqual(output.read_text(), "keep")

    def test_bad_roots(self):
        for data in [[], {}, {"locations":{}}]:
            self.write(data)
            with self.assertRaises(ValueError):
                read_points(self.source)

    def test_same_file_and_unsupported_format(self):
        self.write({"locations":[]})
        for output in [self.source, self.source.with_suffix(".kml")]:
            with self.assertRaises(ValueError):
                convert(self.source, output)

    def test_export_failure_cleans_temp_and_preserves_output(self):
        self.write({"locations":[]})
        output = self.source.with_suffix(".gpx")
        output.write_text("keep")
        def broken(points, stream):
            stream.write("partial")
            raise OSError("disk failure")
        with patch.dict(EXPORTERS, {"gpx":broken}):
            with self.assertRaises(OSError):
                convert(self.source)
        self.assertEqual(output.read_text(), "keep")
        self.assertEqual(list(self.source.parent.glob(".polarsteps-*")), [])

    def test_cli_errors(self):
        self.source.write_text("{broken", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["-i",str(self.source)]), 1)
        self.assertIn("Error:", err.getvalue())

    def test_bom_and_cli_success(self):
        self.source.write_text('{"locations":[]}', encoding="utf-8-sig")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(["-i", str(self.source)]), 0)
        self.assertIn("0 points written", out.getvalue())


if __name__ == "__main__":
    unittest.main()
