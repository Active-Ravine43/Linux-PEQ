"""Core data models for the application state layer.

These models represent the UI-facing state. They are distinct from
audio_backend/models.py which represents PipeWire-level entities.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from peq_app.config import DEFAULT_BAND_FREQUENCIES, DEFAULT_BAND_TYPES, DEFAULT_Q


@dataclass
class EQBand:
    """A single parametric EQ band."""

    freq_hz: float
    gain_db: float = 0.0
    q: float = DEFAULT_Q
    filter_type: str = "peaking"
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "freq_hz": self.freq_hz,
            "gain_db": self.gain_db,
            "q": self.q,
            "filter_type": self.filter_type,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> EQBand:
        return cls(
            freq_hz=d["freq_hz"],
            gain_db=d.get("gain_db", 0.0),
            q=d.get("q", DEFAULT_Q),
            filter_type=d.get("filter_type", "peaking"),
            enabled=d.get("enabled", True),
        )


@dataclass
class Channel:
    """Represents an audio channel — either the master output or a per-app EQ channel."""

    id: str
    name: str
    pipewire_node_id: int | None = None
    filter_pid: int | None = None
    filter_node_id: int | None = None
    volume: float = 1.0
    is_muted: bool = False
    eq_bands: list[EQBand] = field(default_factory=lambda: _default_bands())
    is_master: bool = False
    app_binary: str = ""

    @property
    def is_eq_active(self) -> bool:
        """True if this channel has a running EQ filter chain."""
        return self.filter_node_id is not None and self.filter_pid is not None

    def band_params_for_engine(self) -> list[dict]:
        """Export bands as the format expected by eq_engine/config_manager."""
        return [
            {
                "freq_hz": b.freq_hz,
                "gain_db": b.gain_db,
                "q": b.q,
                "filter_type": b.filter_type,
            }
            for b in self.eq_bands
        ]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "volume": self.volume,
            "is_muted": self.is_muted,
            "is_master": self.is_master,
            "app_binary": self.app_binary,
            "eq_bands": [b.to_dict() for b in self.eq_bands],
        }

    @classmethod
    def from_dict(cls, d: dict) -> Channel:
        bands = [EQBand.from_dict(b) for b in d.get("eq_bands", [])]
        return cls(
            id=d["id"],
            name=d["name"],
            volume=d.get("volume", 1.0),
            is_muted=d.get("is_muted", False),
            is_master=d.get("is_master", False),
            app_binary=d.get("app_binary", ""),
            eq_bands=bands if bands else _default_bands(),
        )


@dataclass
class EQPreset:
    """A named collection of EQ band settings."""

    name: str
    bands: list[dict]  # list of {freq_hz, gain_db, q, filter_type}

    def to_dict(self) -> dict:
        return {"name": self.name, "bands": self.bands}

    @classmethod
    def from_dict(cls, d: dict) -> EQPreset:
        return cls(name=d["name"], bands=d["bands"])


# ------------------------------------------------------------------
# Factory helpers
# ------------------------------------------------------------------

def _default_bands() -> list[EQBand]:
    """Build the default 10-band flat EQ."""
    return [
        EQBand(freq_hz=f, filter_type=t)
        for f, t in zip(DEFAULT_BAND_FREQUENCIES, DEFAULT_BAND_TYPES)
    ]


def master_channel() -> Channel:
    """Create the master channel (controls hardware output EQ)."""
    return Channel(
        id="master",
        name="Master",
        is_master=True,
    )


# ------------------------------------------------------------------
# Built-in presets
# ------------------------------------------------------------------

BUILTIN_PRESETS: list[EQPreset] = [
    EQPreset(name="Flat", bands=[
        {"freq_hz": f, "gain_db": 0.0, "q": DEFAULT_Q, "filter_type": t}
        for f, t in zip(DEFAULT_BAND_FREQUENCIES, DEFAULT_BAND_TYPES)
    ]),
    EQPreset(name="Bass Boost", bands=[
        {"freq_hz": 31, "gain_db": 6.0, "q": 0.5, "filter_type": "lowshelf"},
        {"freq_hz": 63, "gain_db": 4.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 125, "gain_db": 2.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 250, "gain_db": 1.0, "q": 0.707, "filter_type": "peaking"},
        *[{"freq_hz": f, "gain_db": 0.0, "q": DEFAULT_Q, "filter_type": t}
          for f, t in zip(DEFAULT_BAND_FREQUENCIES[4:], DEFAULT_BAND_TYPES[4:])],
    ]),
    EQPreset(name="Vocal Boost", bands=[
        {"freq_hz": 31, "gain_db": -3.0, "q": 0.5, "filter_type": "lowshelf"},
        {"freq_hz": 63, "gain_db": -2.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 125, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 250, "gain_db": -1.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 500, "gain_db": 2.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 1000, "gain_db": 3.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 2000, "gain_db": 3.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 4000, "gain_db": 2.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 8000, "gain_db": 1.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 16000, "gain_db": 0.0, "q": 0.707, "filter_type": "highshelf"},
    ]),
    EQPreset(name="Loudness", bands=[
        {"freq_hz": 31, "gain_db": 4.0, "q": 0.5, "filter_type": "lowshelf"},
        {"freq_hz": 63, "gain_db": 3.0, "q": 0.5, "filter_type": "peaking"},
        {"freq_hz": 125, "gain_db": 1.5, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 250, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 500, "gain_db": -1.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 1000, "gain_db": -2.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 2000, "gain_db": -1.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 4000, "gain_db": 1.0, "q": 0.707, "filter_type": "peaking"},
        {"freq_hz": 8000, "gain_db": 3.0, "q": 0.5, "filter_type": "peaking"},
        {"freq_hz": 16000, "gain_db": 4.0, "q": 0.5, "filter_type": "highshelf"},
    ]),
]
