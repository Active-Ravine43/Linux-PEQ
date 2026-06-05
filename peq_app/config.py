"""Application constants and path configuration."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

APP_NAME = "peq"

# Config directories
XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
CONFIG_DIR = XDG_CONFIG_HOME / APP_NAME
FILTER_CHAIN_DIR = CONFIG_DIR / "filter-chains"
STATE_DIR = CONFIG_DIR / "state"
PRESETS_FILE = CONFIG_DIR / "presets.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# PipeWire paths
PIPEWIRE_CONFIG_DIR = XDG_CONFIG_HOME / "pipewire" / "filter-chain.conf.d"

# System binaries
PW_CLI = "pw-cli"
WPCTL = "wpctl"
PACTL = "pactl"
PIPEWIRE = "pipewire"

# EQ defaults
DEFAULT_BAND_FREQUENCIES = [
    31.0,
    63.0,
    125.0,
    250.0,
    500.0,
    1000.0,
    2000.0,
    4000.0,
    8000.0,
    16000.0,
]
DEFAULT_Q = 0.707
GAIN_MIN_DB = -24.0
GAIN_MAX_DB = 24.0
Q_MIN = 0.1
Q_MAX = 10.0

# Default band filter types
DEFAULT_BAND_TYPES = [
    "lowshelf",  # 31 Hz
    "peaking",  # 63 Hz
    "peaking",  # 125 Hz
    "peaking",  # 250 Hz
    "peaking",  # 500 Hz
    "peaking",  # 1 kHz
    "peaking",  # 2 kHz
    "peaking",  # 4 kHz
    "peaking",  # 8 kHz
    "highshelf",  # 16 kHz
]

# Polling interval for app discovery (seconds)
SCAN_INTERVAL = 1.0

# Binary names to ignore (system utilities that produce audio but aren't user-facing)
IGNORED_BINARIES = {
    "sd_dummy",  # speech-dispatcher dummy output
    "speech-dispatcher",  # accessibility speech synth
}


def ensure_dirs() -> None:
    """Create all required config directories."""
    for d in (FILTER_CHAIN_DIR, STATE_DIR, PIPEWIRE_CONFIG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    """Load persisted user settings from disk.

    Returns an empty dict if the file doesn't exist or can't be parsed.
    """
    ensure_dirs()
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load settings from %s: %s", SETTINGS_FILE, exc)
    return {}


def save_settings(settings: dict) -> None:
    """Persist user settings to disk as JSON."""
    ensure_dirs()
    try:
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to save settings to %s: %s", SETTINGS_FILE, exc)
