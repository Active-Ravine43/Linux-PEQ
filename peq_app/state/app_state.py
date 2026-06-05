"""Application state singleton with observer pattern.

AppState is the single source of truth for all channel data. The TUI
and audio backend communicate through it: backend mutations notify
observers, and UI interactions mutate state (which triggers backend calls).

Mutation types (events):
  - "channels_updated"   — app list changed (app started/stopped)
  - "channel_selected"   — user selected a different channel
  - "volume_changed"     — volume or mute changed for a channel
  - "eq_changed"         — one or more EQ bands changed
  - "preset_applied"     — a preset was applied to a channel
  - "eq_chain_created"   — EQ filter-chain process started
  - "eq_chain_destroyed" — EQ filter-chain process stopped
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Awaitable

from peq_app.config import STATE_DIR, ensure_dirs
from peq_app.state.models import (
    BUILTIN_PRESETS,
    Channel,
    EQBand,
    EQPreset,
    master_channel,
)

logger = logging.getLogger(__name__)

Observer = Callable[[str, object], Awaitable[None]]
"""An async observer callback: async def callback(event: str, data: object) -> None"""


class AppState:
    """Singleton application state with observer notifications."""

    _instance: AppState | None = None

    def __new__(cls) -> AppState:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self.channels: dict[str, Channel] = {}
        self.selected_channel_id: str | None = None
        self._observers: list[Observer] = []
        self._lock = asyncio.Lock()

        ensure_dirs()
        self._init_master()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _init_master(self) -> None:
        """Create the master channel if it doesn't exist."""
        master = master_channel()
        self.channels[master.id] = master
        self.selected_channel_id = master.id

    # ------------------------------------------------------------------
    # Observer management
    # ------------------------------------------------------------------

    def observe(self, callback: Observer) -> None:
        """Register an async callback to be notified of state changes."""
        self._observers.append(callback)

    def unobserve(self, callback: Observer) -> None:
        """Remove a previously registered observer."""
        if callback in self._observers:
            self._observers.remove(callback)

    async def _notify(self, event: str, data: object = None) -> None:
        """Notify all observers of a state change."""
        for observer in self._observers:
            try:
                await observer(event, data)
            except Exception:
                logger.exception("Observer failed for event %s", event)

    # ------------------------------------------------------------------
    # Channel management
    # ------------------------------------------------------------------

    async def add_channel(self, channel: Channel) -> None:
        """Add or update a discovered app channel."""
        async with self._lock:
            is_new = channel.id not in self.channels
            self.channels[channel.id] = channel
        await self._notify("channels_updated", {"added": [channel] if is_new else [], "updated": [channel] if not is_new else []})

    async def remove_channel(self, channel_id: str) -> None:
        """Remove a channel (app stopped)."""
        async with self._lock:
            if channel_id in self.channels:
                del self.channels[channel_id]
                if self.selected_channel_id == channel_id:
                    self.selected_channel_id = "master"
        await self._notify("channels_updated", {"removed": [channel_id]})

    async def sync_channels(self, app_ids: set[str]) -> None:
        """Sync channels with current running apps. Removes stale, adds new."""
        current_ids = {cid for cid in self.channels if cid != "master"}
        removed = current_ids - app_ids
        added = app_ids - current_ids

        async with self._lock:
            for rid in removed:
                del self.channels[rid]
                if self.selected_channel_id == rid:
                    self.selected_channel_id = "master"

        if removed:
            await self._notify("channels_updated", {"removed": list(removed)})
        if added:
            await self._notify("channels_updated", {"added_ids": list(added)})

    async def select_channel(self, channel_id: str) -> None:
        """Set the currently selected channel."""
        async with self._lock:
            if channel_id in self.channels:
                self.selected_channel_id = channel_id
        await self._notify("channel_selected", channel_id)

    @property
    def selected_channel(self) -> Channel | None:
        """The currently selected channel, or None."""
        return self.channels.get(self.selected_channel_id or "")

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    async def set_volume(self, channel_id: str, volume: float) -> None:
        """Set volume for a channel (0.0–1.0)."""
        async with self._lock:
            channel = self.channels.get(channel_id)
            if channel:
                channel.volume = max(0.0, min(1.0, volume))
        await self._notify("volume_changed", {"channel_id": channel_id, "volume": volume})

    async def set_mute(self, channel_id: str, muted: bool) -> None:
        """Set mute state for a channel."""
        async with self._lock:
            channel = self.channels.get(channel_id)
            if channel:
                channel.is_muted = muted
        await self._notify("volume_changed", {"channel_id": channel_id, "muted": muted})

    async def toggle_mute(self, channel_id: str) -> None:
        """Toggle mute for a channel."""
        async with self._lock:
            channel = self.channels.get(channel_id)
            if channel:
                channel.is_muted = not channel.is_muted
                muted = channel.is_muted
        await self._notify("volume_changed", {"channel_id": channel_id, "muted": muted})

    # ------------------------------------------------------------------
    # EQ bands
    # ------------------------------------------------------------------

    async def set_band(
        self,
        channel_id: str,
        band_index: int,
        gain_db: float | None = None,
        freq_hz: float | None = None,
        q: float | None = None,
    ) -> None:
        """Update a single EQ band for a channel."""
        async with self._lock:
            channel = self.channels.get(channel_id)
            if not channel or band_index >= len(channel.eq_bands):
                return
            band = channel.eq_bands[band_index]
            if gain_db is not None:
                band.gain_db = max(-24.0, min(24.0, gain_db))
            if freq_hz is not None:
                band.freq_hz = freq_hz
            if q is not None:
                band.q = max(0.1, min(10.0, q))

        await self._notify("eq_changed", {
            "channel_id": channel_id,
            "band_index": band_index,
            "gain_db": gain_db,
            "freq_hz": freq_hz,
            "q": q,
        })

    async def set_all_bands(self, channel_id: str, bands: list[dict]) -> None:
        """Replace all EQ band settings for a channel (preset application)."""
        async with self._lock:
            channel = self.channels.get(channel_id)
            if not channel:
                return
            for i, b in enumerate(bands):
                if i < len(channel.eq_bands):
                    channel.eq_bands[i].gain_db = b.get("gain_db", 0.0)
                    channel.eq_bands[i].q = b.get("q", channel.eq_bands[i].q)
                    channel.eq_bands[i].filter_type = b.get("filter_type", channel.eq_bands[i].filter_type)

        await self._notify("preset_applied", {"channel_id": channel_id, "bands": bands})

    async def apply_preset(self, channel_id: str, preset: EQPreset) -> None:
        """Apply a named EQ preset to a channel."""
        await self.set_all_bands(channel_id, preset.bands)

    # ------------------------------------------------------------------
    # EQ chain lifecycle
    # ------------------------------------------------------------------

    async def set_eq_chain_created(self, channel_id: str, filter_pid: int, filter_node_id: int) -> None:
        """Record that an EQ filter-chain process has started for a channel."""
        async with self._lock:
            channel = self.channels.get(channel_id)
            if channel:
                channel.filter_pid = filter_pid
                channel.filter_node_id = filter_node_id
        await self._notify("eq_chain_created", {"channel_id": channel_id, "node_id": filter_node_id})

    async def set_eq_chain_destroyed(self, channel_id: str) -> None:
        """Record that an EQ filter-chain process has stopped."""
        async with self._lock:
            channel = self.channels.get(channel_id)
            if channel:
                channel.filter_pid = None
                channel.filter_node_id = None
        await self._notify("eq_chain_destroyed", channel_id)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_state(self) -> None:
        """Persist current channel state to disk."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "channels": {
                cid: ch.to_dict()
                for cid, ch in self.channels.items()
                if not ch.is_master  # Master is reconstructed, not saved
            },
        }
        path = STATE_DIR / "state.json"
        path.write_text(json.dumps(data, indent=2))

    def load_state(self) -> None:
        """Load persisted channel state from disk."""
        path = STATE_DIR / "state.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            for cid, ch_data in data.get("channels", {}).items():
                channel = Channel.from_dict(ch_data)
                self.channels[channel.id] = channel
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.exception("Failed to load state from %s", path)

    # ------------------------------------------------------------------
    # Presets
    # ------------------------------------------------------------------

    @property
    def presets(self) -> list[EQPreset]:
        """All available presets (built-in + user)."""
        return list(BUILTIN_PRESETS)


# Module-level convenience accessor
def get_state() -> AppState:
    """Return the AppState singleton."""
    return AppState()
