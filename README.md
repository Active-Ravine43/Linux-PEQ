# PEQ — Per-application Parametric Equalizer

A Linux audio equalizer with per-application volume control and independent 10-band parametric EQ, built as a Textual TUI.

## Requirements

- Linux with PipeWire 1.x (and pipewire-pulse compat)
- Python 3.12+
- System tools: `pipewire`, `pw-cli`, `pactl` (all included with PipeWire)

## Quick Start

```bash
# Clone + set up
git clone <repo-url> && cd Linux-Audio-Management-App
make                    # creates venv + installs dependencies
make run                # launch the TUI
```

After setup, you can launch the app from anywhere:

```bash
# From the project directory — just type:
./scripts/Linux-PEQ

# Or install system-wide (requires sudo):
make install-system
Linux-PEQ               # now works from any directory

# Or install per-user (no sudo):
make install-user
Linux-PEQ               # works if ~/.local/bin is in PATH
```

## CLI Mode

```bash
Linux-PEQ --scan           # list audio apps
Linux-PEQ --create-eq 125  # create EQ sink for a sink input
Linux-PEQ --help            # show all options
```

## Usage

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Next / previous channel |
| `m` | Toggle mute on selected channel |
| `1`–`0` | Focus EQ bands 1–10 |
| `t` | Cycle theme (Amber → Slate → Mono → Amber) |
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

## Code Quality

```bash
make format            # format code with black + isort
make format-check      # check formatting (CI mode, no changes)
make lint              # lint with pylint (errors + warnings only)
make lint-full         # lint with pylint (all checks)
make lint-all          # format-check + full lint
make test              # run test suite
```

- **Formatter:** [Black](https://github.com/psf/black) (line length 100) + [isort](https://github.com/PyCQA/isort) (Black profile)
- **Linter:** [Pylint](https://github.com/pylint-dev/pylint) — config in `pyproject.toml`
- **Testing:** [pytest](https://github.com/pytest-dev/pytest)

## Design

Minimalist dark theme with 3 variants: **Amber** (default, warm gold accent), **Slate** (cool blue-grey), and **Mono** (pure greyscale). Off-black canvas, single muted accent per theme, 1px borders. Press `t` to cycle themes at runtime. Designed for someone tweaking EQ at their desk in a dim room.

**Presets:** Flat, Bass Boost, Vocal Boost, Loudness — one-click buttons below the EQ panel.
