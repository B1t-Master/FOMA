"""Command-line entry point.

Usage:
    python -m foma                 run FOMA in the background (Ctrl+C to stop)
    python -m foma --once          run a single detection pass and exit
    python -m foma --config PATH   use a specific TOML configuration
    python -m foma --version       print the version and exit

Install the ``foma`` script entry point via ``pip install -e .`` for the
short ``foma`` command.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys

from . import __version__
from .app import FomaApp
from .config import DEFAULT_CONFIG_PATH, FomaConfig


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="foma",
        description="FOMA - Fear Of More Ads. Auto-skips YouTube ads in the background.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"path to the TOML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument("--once", action="store_true", help="run a single pass, then exit")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


async def _run_once(config: FomaConfig) -> int:
    app = FomaApp(config)
    app.telemetry.sample_ram()
    found = await app.orchestrator.run_once()
    summary = app.telemetry.summary()
    print(f"pass complete: found={found} summary={summary}")
    return 0


async def _run_forever(config: FomaConfig) -> int:
    app = FomaApp(config)

    if sys.platform == "win32":
        # asyncio signal handlers are POSIX-only; on Windows a plain
        # `signal.signal` handler runs on the main thread and just drains our
        # stop event. SIGTERM is unusable on Windows, so only SIGINT applies.
        signal.signal(signal.SIGINT, lambda _sig, _frame: app.request_stop())
    else:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, app.request_stop)
    try:
        await app.run()
    except asyncio.CancelledError:  # pragma: no cover - defensive
        app.request_stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = FomaConfig.load(args.config)
    except Exception as exc:
        print(f"failed to load configuration: {exc}", file=sys.stderr)
        return 2
    if args.once:
        return asyncio.run(_run_once(config))
    return asyncio.run(_run_forever(config))


if __name__ == "__main__":
    raise SystemExit(main())
