"""Command-line entry point."""
import argparse
import sys
from .core import convert


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Convert Polarsteps locations.json to GPX.")
    parser.add_argument("-i", "--input", default="locations.json", help="Input JSON (default: locations.json)")
    parser.add_argument("-o", "--output", help="Output GPX (default: input path with .gpx extension)")
    args = parser.parse_args(argv)
    try:
        path, count = convert(args.input, args.output)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"{count} points written to {path}")
    return 0
