"""Thin bootstrap so PyInstaller has a concrete script to analyze."""

from foma.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())