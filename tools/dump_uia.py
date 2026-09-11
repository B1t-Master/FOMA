r"""Debugging tool: dump what Windows UI Automation actually exposes.

Run while a YouTube ad is on screen (the "Skip" button must be visible) to see
whether the button is reachable through UIA and how FOMA's detector searches
for it:

    .venv\Scripts\python.exe tools\dump_uia.py [--depth 128] [--filter]

A full log is always written to tools/dump-uia.log. With --filter the console
shows only the browser-window summary, elements whose name contains "skip",
and the detector probe results.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
from pathlib import Path

from foma.detection.uia_detector import UIADetector

LOG_PATH = Path(__file__).with_name("dump-uia.log")

SKIP_MATCHER = re.compile(r"skip", re.IGNORECASE)
MATCHER = re.compile(r"(skip|ad|skip_ads)", re.IGNORECASE)

_output = io.StringIO()
_console: list[str] = []


def log(line: str = "", show: bool = True) -> None:
    _output.write(line + "\n")
    if show:
        _console.append(line)


def walk(
    control,
    depth: int,
    max_depth: int,
    hits: list,
    skip_hits: list,
    budget: list[int],
) -> None:
    if depth > max_depth or budget[0] <= 0:
        return
    try:
        children = control.GetChildren()
    except Exception:
        return
    for child in children:
        budget[0] -= 1
        if budget[0] <= 0:
            return
        try:
            name = child.Name or ""
        except Exception:
            name = ""
        try:
            typ = child.ControlTypeName
        except Exception:
            typ = "?"
        try:
            offscreen = child.IsOffscreen
        except Exception:
            offscreen = "?"
        if SKIP_MATCHER.search(name):
            skip_hits.append((depth, typ, name[:160], offscreen))
        if depth <= 4 or MATCHER.search(name):
            hits.append((depth, typ, name[:120], offscreen))
        walk(child, depth + 1, max_depth, hits, skip_hits, budget)


def probe(auto, window, detector, label: str) -> None:
    t0 = time.perf_counter()
    try:
        button = detector._find_skip_button(window)
    except Exception as exc:
        log(f"  _find_skip_button [{label}]: raised {type(exc).__name__}: {exc}")
        return
    elapsed = time.perf_counter() - t0
    if button is None:
        log(f"  _find_skip_button [{label}]: {elapsed:.2f}s -> NOT FOUND")
        return
    r = button.BoundingRectangle
    log(
        f"  _find_skip_button [{label}]: {elapsed:.2f}s -> FOUND "
        f"name={button.Name!r} rect=({r.left},{r.top},{r.right - r.left}x{r.bottom - r.top}) "
        f"offscreen={button.IsOffscreen}"
    )


def inspect_window(auto, window, depth: int) -> None:
    try:
        cls = window.ClassName
        visible = getattr(window, "IsVisible", True)
        title = (window.Name or "").strip()[:80]
    except Exception as exc:
        log(f"--- window (class read failed: {exc}) ---")
        return
    browser = cls in UIADetector()._classes
    if not browser:
        return
    log(f"--- BROWSER window class={cls!r} visible={visible} title={title!r} ---")
    hits: list[tuple] = []
    skip_hits: list[tuple] = []
    budget = [12000]
    t0 = time.perf_counter()
    walk(window, 1, depth, hits, skip_hits, budget)
    elapsed = time.perf_counter() - t0
    deepest = max((h[0] for h in hits), default=0)
    log(
        f"  walk(depth={depth}): {elapsed:.2f}s, nodes={12000 - budget[0]}, "
        f"matches={len(hits)}, deepest_match = {deepest}"
    )
    if skip_hits:
        log("  >>> elements whose name contains 'skip':")
        for d, typ, name, off in skip_hits:
            log(f"    d={d:<3} type={typ:<12} offscreen={off} name={name!r}")
    else:
        log("  >>> NO elements whose name contains 'skip' found")
    for d, typ, name, off in hits:
        log(f"    d={d:<3} type={typ:<12} offscreen={off} name={name!r}", show=False)

    d_def = UIADetector()
    d128 = UIADetector(search_depth=128)
    probe(auto, window, d_def, f"search_depth={d_def._search_depth} (default)")
    probe(auto, window, d128, "search_depth=128")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump UIA state for FOMA debugging.")
    parser.add_argument("--depth", type=int, default=128, help="max tree depth to walk")
    parser.add_argument(
        "--filter",
        action="store_true",
        help="only show browser summary, skip matches and probe results on the console",
    )
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    log(f"=== dump_uia started {time.strftime('%H:%M:%S')} ===")

    auto = __import__("uiautomation")
    root = auto.GetRootControl()
    log(f"=== root: {root.Name!r}  (children: {len(root.GetChildren())}) ===")
    for window in root.GetChildren():
        try:
            inspect_window(auto, window, args.depth)
        except Exception as exc:
            log(f"  inspect_window failed: {type(exc).__name__}: {exc}")

    LOG_PATH.write_text(_output.getvalue(), encoding="utf-8")
    for line in _console if args.filter else _output.getvalue().splitlines():
        print(line)
    print(f"\n(full log written to {LOG_PATH})")


if __name__ == "__main__":
    main()
