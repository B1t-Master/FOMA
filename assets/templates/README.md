# Screen-fallback templates

Drop small PNG crops of the "Skip ad" button here to enable the screen-capture
fallback (used only when UI Automation cannot see the browser).

Tips:

- Crop tightly around the button text; ~40–120 px wide is plenty.
- Capture at a couple of zoom levels (100% and 125%) for robustness; the matcher
  also tries the same image at scales 1.0 / 0.9 / 0.8 / 0.7.
- The fallback only activates when `screen_fallback = true` in `config.toml`.
- Remember: `mss`, `opencv-python-headless` and `numpy` are bundled in the
  `fallback` extra — install with `pip install -e ".[fallback]"`.