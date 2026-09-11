# FOMA — Fear Of More Ads

A small, quiet background tool that **skips YouTube ads for you** while you watch. It runs on Windows, watches Chrome and Firefox, and the moment YouTube shows a "Skip" button, FOMA clicks it the way you would right behind your back. Also eliminates the physical need to make precise, timed mouse movements to target small UI buttons for users with fine motor control challenges, tremors, or repetitive strain injuries (RSI). Just a better Youtube viewing experience.

No browser extension. No screenshots. No moving parts in the page itself.

Instead of looking at pixels, FOMA reads the **accessibility tree** the browser already publishes (the same data screen readers use). That tree describes every on-screen element with its name and exact position, so a "Skip" button is found by _what it is_, not by matching colours or templates. That makes FOMA immune to zoom, resolution, dark mode, and YouTube redesigns that break any pixel-based approach.

```
poll (0.5s) → detect (UI Automation) → click "Skip" at its real X/Y → cooldown → repeat
                   │                                          │
                   └────────▶ event bus ──────▶ console + JSONL logs
```

## Why not pixels?

| Approach               | Zoom / resolution | Dark mode | UI rebuilds | Trusted clicks |
| ---------------------- | ----------------- | --------- | ----------- | -------------- |
| Pixel color matching   | breaks            | breaks    | breaks      | no             |
| Screenshot templates   | breaks            | breaks    | breaks      | no             |
| OCR                    | ok                | ok        | breaks      | no             |
| **UI Automation (us)** | ok                | ok        | ok          | ok             |

Two more things worth knowing:

- YouTube ignores clicks that don't come from a real user — scripts and extensions clicking an element are detected and ignored (the event's `isTrusted` flag is `false`). FOMA sidesteps this by driving the **real mouse through Windows**, so the click is indistinguishable from your own.
- When UI Automation can't see things (older browsers), FOMA can fall back to **screen-capture template matching** using crops you drop into `assets/templates`.

## Requirements

- Windows 10 or 11 (v1 is Windows-only)
- Python **3.11+**
- A modern Chrome (138+), Edge or Firefox — all export UI Automation natively. (Really old Chrome needs `--force-renderer-accessibility`.)

## Install

```powershell
cd FOMA
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,fallback]"
```

## How to run

1. **Open PowerShell** in the FOMA folder (it's `C:\Users\Admin\OneDrive\Desktop\repos\FOMA` here):

   ```powershell
   cd C:\Users\Admin\OneDrive\Desktop\repos\FOMA
   ```

2. **Activate the virtual environment** (one time per terminal):

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   (If you didn't install yet: the venv was created in **Install**, below.)
   No activation? No problem — just call the interpreter directly:
   `\.venv\Scripts\python.exe -m foma` works the same.

3. **Start it:**

   ```powershell
   python -m foma
   ```

   That's it. Leave the window open — FOMA sits quietly in the background and
   will click the next "Skip" it sees. You can keep it running while you browse.
   Stop it anytime with **Ctrl+C**.

4. **Watch it work.** Play a YouTube video with an ad. When the Skip button
   appears you'll see:

   ```
   [12:04:41] AD_DETECTED rect=(1250,882,120x40) detector=uia detect_ms=2047
   [12:04:41] SKIP_CLICKED at=(1310,902) click_ms=31
   ```

   Eyeing the terminal for the next ad is a great way to verify the install.

Want a quick sanity check instead of waiting for an ad? Run one scan and exit:
`python -m foma --once` — it logs whether a Skip button was found right now.

## Usage

```powershell
python -m foma          # run in the foreground (Ctrl+C to stop)
python -m foma --once   # single scan, then exit (good smoke test)
python -m foma --config .\config.toml   # use a different config file
foma                    # same as `python -m foma`, once installed
```

Want it to start by itself at login? See **Deployment** — `deploy/install.ps1` registers a silent on-logon task.

## Project structure

```
FOMA/
├── config.toml            # your settings
├── pyproject.toml         # package metadata & tooling config
├── deploy/                # autostart + standalone-exe packaging
├── tools/
│   └── dump_uia.py        # debug tool: "what does Windows actually see?"
├── assets/templates/      # where fallback button crops go
├── src/foma/
│   ├── __main__.py        # the CLI: --once / --config / --version
│   ├── app.py             # wires all the pieces together (composition root)
│   ├── config.py          # reads & validates config.toml
│   ├── events.py          # tiny pub/sub event bus (future SSE/dashboard)
│   ├── detection/
│   │   ├── uia_detector.py      # main detector: scans the accessibility tree
│   │   └── screen_detector.py   # fallback: mss + OpenCV template match
│   ├── engines/
│   │   ├── orchestrator.py      # the main loop: scan → click → cooldown
│   │   ├── clicker.py           # the real, trusted mouse click
│   │   └── state.py             # idle / skipping / skipped / paused
│   ├── telemetry/metrics.py     # latency windows + RAM sampling
│   └── loggers/
│       ├── console_logger.py    # human-readable console output
│       └── jsonl_logger.py      # machine-readable daily logs
└── tests/                 # 74 tests, no browser needed
```

The core is deliberately lean — it only depends on `uiautomation`, `pynput` and `psutil`. The screen fallback stack (`mss`, `opencv`, `numpy`) is imported lazily, so it never slows down UIA-only use.

Each piece is small and dependency-injected, so swapping a detector or adding a dashboard later is a change in one place.

## How it performs (measured)

Real numbers from the current build on this machine:

| Metric       | Measured                                  |
| ------------ | ----------------------------------------- |
| Cold start   | ~26 MB RSS with only UIA loaded           |
| Steady state | ~57 MB once UI Automation + COM warm up   |
| Detect       | ~2.0–2.2 s on a busy YouTube window       |
| Click        | ~30 ms end-to-end (pynput → OS injection) |
| No-ad scan   | returns in < 0.5 s on smaller windows     |

Notes:

- Sleep comes cheap — the poll loop only consumes real CPU while actually scanning, and scanning runs in a worker thread so YouTube never stutters.
- The scan is depth/range limited, so a slow "no ads" run costs at most a few seconds and falls back to quiet sleep.
- If you keep YouTube open for hours, bumping `poll_interval_s` to 2 saves CPU with no real downside — ads don't appear that fast.

## Tests

The suite is written against fake UI components, so it runs anywhere, no browser needed:

```powershell
.\.venv\Scripts\python.exe -m pytest      # 74 unit tests
.\.venv\Scripts\python.exe -m foma --once # live smoke test against real screen
```

What's covered: finding the button by name, case-insensitivity, choosing the _right_ button among decoys ("Skip navigation" vs "Skip"), off-screen rejection, wrong control types, empty/broken trees, node-budget and depth limits, cooldown behaviour, click latency, RAM sampling, JSONL rotation, console output, and the full orchestrator loop. The real-ad behaviour is verified manually: run `python -m foma`, watch a video with an ad, confirm `AD_DETECTED` + `SKIP_CLICKED`.

## Limitations

Be honest about what FOMA won't do:

- **Windows only.** It leans on Windows UI Automation and Win32 — there's no macOS/Linux build yet.
- **Needs a browser that exports UI Automation.** That's all modern Chrome/Edge/Firefox; old Chrome needs the accessibility flag.
- **The tab must be visible.** If the video tab is on another workspace or minimized in a way the OS reports off-screen, FOMA deliberately does nothing rather than click blindly.
- **It grabs the empty hand sometimes.** Ad designs change; if YouTube stops labelling the button "Skip" in a recognisable way, FOMA just won't click until the pattern list is updated (that's what `name_patterns` is for).
- **CPU while scanning.** A big YouTube window means a slightly heavier scan (a second or two every few seconds).
- **Terms of Service.** Skipping ads automatically may not sit well with YouTube's ToS. It's your machine and your call — use at your own discretion.

## Future improvements

- **GitHub action workflows to protect main**
- **Browser-extension companion, if Google allows it.** An extension could react instantly (no polling, no mouse) — YouTube has historically not offered a supported API for skipping ads, so this stays a "nice if it ever becomes possible" item. FOMA stays useful meanwhile because it needs no page access at all.
- **Native apps on other operating systems.**
- **A live dashboard or SSE stream.** The internal event bus is already pub/sub-ready, so a web page or local dashboard could subscribe without touching the core.
- **Smarter scanning.** Region budgeting (only scan the player area once the tab is identified) and faster negative scans.
- **Better fallback templates.** Bundled default templates so the screen-capture mode works out of the box.

## Deployment

- `deploy/install.ps1` — registers an **on-logon scheduled task** that starts FOMA silently with `pythonw` (no console window).
- `deploy/uninstall.ps1` — removes that task.
- `deploy/build.ps1` + `deploy/foma.spec` — package a standalone `.exe` with PyInstaller, so target machines don't need Python at all.

## Branching

| Branch    | What lives there                             |
| --------- | -------------------------------------------- |
| `main`    | stable, working snapshots                    |
| `develop` | where things get integrated before releasing |
| `deploy`  | deployment scripts and release packaging     |
