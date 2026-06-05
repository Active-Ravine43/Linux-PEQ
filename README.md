# PEQ — Per-application Parametric Equalizer

A Linux audio equalizer with per-application volume control and independent 10-band parametric EQ, built as a Textual TUI.

## Requirements

- Linux with PipeWire 1.x (and pipewire-pulse compat)
- Python 3.12+
- System tools: `pipewire`, `pw-cli`, `pactl` (all included with PipeWire)

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m peq_app
```

Or use the Makefile:

```bash
make        # create venv + install
make run    # launch the TUI
```

## Usage

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Next / previous channel |
| `m` | Toggle mute on selected channel |
| `1`–`0` | Focus EQ bands 1–10 |
| `q` | Quit |

**Mouse:** Click a channel to select it. Drag EQ band bars vertically to adjust gain. Scroll on bands for fine-tuning. Click/drag the volume slider bar.

## Architecture

```
peq_app/
├── audio_backend/     # PipeWire interaction (pulsectl, pw-cli, pactl)
│   ├── scanner.py     # App discovery
│   ├── volume.py      # Volume read/write
│   ├── eq_engine.py   # Filter-chain lifecycle + runtime param control
│   ├── router.py      # Audio stream routing
│   └── config_manager.py  # Filter-chain .conf file CRUD
├── state/             # Observable application state
│   ├── models.py      # Channel, EQBand, EQPreset
│   └── app_state.py   # Singleton + observer pattern
└── ui_tui/            # Textual terminal UI
    ├── app.py         # Main EQApp
    └── widgets/       # Channel panel, EQ bands, volume slider, presets
```

Each EQ channel runs as a lightweight `pipewire -c filter-chain.conf` child process. Runtime band adjustments use `pw-cli set-param` on the filter-chain sink node (~1ms latency).

## CLI Mode

```bash
# List audio apps
python -m peq_app --scan

# Create an EQ sink for a sink input
python -m peq_app --create-eq 125
```

## Design

Minimalist dark theme — off-black canvas, single muted amber accent, 1px borders. Designed for someone tweaking EQ at their desk in a dim room.
