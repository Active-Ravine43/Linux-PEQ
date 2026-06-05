"""Vertical EQ band slider widget with mouse drag support.

Each band is a vertical bar: a track (background) with a fill (gain level).
Mouse drag on the bar adjusts gain. Mouse wheel for fine adjustment.
"""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.events import Click, MouseMove, MouseDown, MouseUp, MouseScrollDown, MouseScrollUp
from textual.reactive import reactive
from textual.widgets import Static

from peq_app.config import DEFAULT_BAND_FREQUENCIES, GAIN_MIN_DB, GAIN_MAX_DB
from peq_app.state.app_state import get_state
from peq_app.state.models import EQBand


def _format_freq(freq_hz: float) -> str:
    """Format frequency for display."""
    if freq_hz >= 1000:
        return f"{freq_hz / 1000:.0f}k"
    return f"{freq_hz:.0f}"


def _format_gain(gain_db: float) -> str:
    """Format gain label."""
    if gain_db > 0:
        return f"+{gain_db:.1f}"
    elif gain_db < 0:
        return f"{gain_db:.1f}"
    return "0.0"


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
        """Update display from an EQBand model."""
        self.gain_db = band.gain_db
        gain_label = self.query_one(".band-gain-label", Static)
        gain_label.update(_format_gain(band.gain_db))

        # Update fill height proportionally. Gain range -24 to +24.
        # Middle (0 dB) = 50% fill. +24 = 100%, -24 = 0%.
        pct = (band.gain_db - GAIN_MIN_DB) / (GAIN_MAX_DB - GAIN_MIN_DB)
        pct = max(0.0, min(1.0, pct))
        height_pct = int(pct * 100)

        fill = self.query_one(".band-fill", Static)
        fill.styles.height = f"{height_pct}%"

        # Color: neutral at 0 dB, accent at extremes
        if abs(band.gain_db) < 0.5:
            fill.styles.background = "#3a3a3e"  # neutral
        else:
            fill.styles.background = "#b8954a"  # accent

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
        # Dragging up → increase gain, down → decrease
        delta_y = self._drag_start_y - event.y
        # Scale: each row of movement ≈ 1 dB
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
