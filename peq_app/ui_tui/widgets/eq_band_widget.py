"""Vertical EQ band slider widget with mouse drag support.

Each band is a vertical bar: a track (background) with a fill (gain level).
Mouse drag on the bar adjusts gain. Mouse wheel for fine adjustment.

Colours come from the app's active theme — no hard-coded hex values.
"""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Click, MouseDown, MouseMove, MouseScrollDown, MouseScrollUp, MouseUp
from textual.reactive import reactive
from textual.widgets import Static

from peq_app.config import DEFAULT_BAND_FREQUENCIES, GAIN_MAX_DB, GAIN_MIN_DB
from peq_app.state.app_state import get_state
from peq_app.state.models import EQBand


def _format_freq(freq_hz: float) -> str:
    """Format frequency for display."""
    if freq_hz >= 1000:
        return f"{freq_hz / 1000:.0f}k"
    return f"{freq_hz:.0f}"


def _format_gain(gain_db: float) -> str:
    """Format gain label — always 5 chars wide for consistent band sizing."""
    if abs(gain_db) < 0.05:
        return " 0.0 "
    return f"{gain_db:+5.1f}"


class EQBandWidget(Vertical):
    """A single vertical EQ band with draggable gain control."""

    gain_db: reactive[float] = reactive(0.0)
    _dragging: bool = False
    _drag_start_y: int = 0
    _drag_start_gain: float = 0.0

    def __init__(self, band_index: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.band_index = band_index
        self.freq_hz = DEFAULT_BAND_FREQUENCIES[band_index]

    def compose(self) -> ComposeResult:
        """Band layout: gain label | fill bar | freq label."""
        yield Static("0.0", classes="band-gain-label")
        yield Static("", classes="band-fill")
        yield Static(_format_freq(self.freq_hz), classes="band-freq-label")

    def update_from_band(self, band: EQBand, index: int) -> None:
        """Update display from an EQBand model. Uses app theme for colours."""
        self.gain_db = band.gain_db
        gain_label = self.query_one(".band-gain-label", Static)
        gain_label.update(_format_gain(band.gain_db))

        # Fill height: middle (0 dB) = 50% fill. +24 = 100%, -24 = 0%.
        pct = (band.gain_db - GAIN_MIN_DB) / (GAIN_MAX_DB - GAIN_MIN_DB)
        pct = max(0.0, min(1.0, pct))
        height_pct = int(pct * 100)

        fill = self.query_one(".band-fill", Static)
        fill.styles.height = f"{height_pct}%"

        # Resolve theme colours from the app
        accent = "#b8954a"
        neutral = "#3a3a3e"
        try:
            if self.app is not None:
                c = getattr(self.app, "theme_colors", None)
                if isinstance(c, dict):
                    accent = c.get("accent", accent)
                    neutral = c.get("band_neutral", neutral)
        except Exception:
            pass

        fill.styles.background = accent if abs(band.gain_db) >= 0.5 else neutral

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def on_mouse_down(self, event: MouseDown) -> None:
        """Start drag."""
        self._dragging = True
        self._drag_start_y = event.y
        self._drag_start_gain = self.gain_db
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        """End drag."""
        self._dragging = False
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        """Update gain while dragging."""
        if not self._dragging:
            return
        delta_y = self._drag_start_y - event.y
        gain_change = delta_y * 1.0
        new_gain = max(GAIN_MIN_DB, min(GAIN_MAX_DB, self._drag_start_gain + gain_change))

        state = get_state()
        channel_id = state.selected_channel_id
        if channel_id:
            asyncio.create_task(state.set_band(channel_id, self.band_index, gain_db=new_gain))
        event.stop()

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        """Fine-tune: scroll down decreases gain."""
        state = get_state()
        channel_id = state.selected_channel_id
        if channel_id:
            new_gain = max(GAIN_MIN_DB, self.gain_db - 0.5)
            asyncio.create_task(state.set_band(channel_id, self.band_index, gain_db=new_gain))
        event.stop()

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        """Fine-tune: scroll up increases gain."""
        state = get_state()
        channel_id = state.selected_channel_id
        if channel_id:
            new_gain = min(GAIN_MAX_DB, self.gain_db + 0.5)
            asyncio.create_task(state.set_band(channel_id, self.band_index, gain_db=new_gain))
        event.stop()
