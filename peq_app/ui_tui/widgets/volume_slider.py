"""Volume slider widget."""

from __future__ import annotations

import asyncio
import time

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Click, MouseDown, MouseMove, MouseScrollDown, MouseScrollUp, MouseUp
from textual.reactive import reactive
from textual.widgets import Static

from peq_app.state.app_state import get_state

# Minimum interval between subprocess calls during drag (seconds)
_VOLUME_THROTTLE_S = 0.05


class VolumeSlider(Horizontal):
    """Horizontal volume slider bar."""

    volume: reactive[float] = reactive(1.0)

    _dragging: bool = False
    _last_set_time: float = 0.0
    _pending_volume: float | None = None
    _pending_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Static("", classes="slider-fill")

    def watch_volume(self, new_volume: float) -> None:
        """Update the fill width when volume changes."""
        try:
            fill = self.query_one(".slider-fill", Static)
            fill.styles.width = f"{int(new_volume * 100)}%"
        except Exception:
            pass

    def on_mouse_down(self, event: MouseDown) -> None:
        """Start drag — set volume based on click position."""
        self._dragging = True
        self._set_volume_from_event(event)
        event.stop()

    def on_mouse_up(self, event: MouseUp) -> None:
        """End drag — flush any pending volume change immediately."""
        self._dragging = False
        self._flush_volume()
        event.stop()

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._dragging:
            self._set_volume_from_event(event)
            event.stop()

    def on_click(self, event: Click) -> None:
        self._set_volume_from_event(event)
        event.stop()

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        state = get_state()
        channel_id = state.selected_channel_id
        if channel_id:
            channel = state.channels.get(channel_id)
            if channel:
                new_vol = max(0.0, channel.volume - 0.05)
                asyncio.create_task(state.set_volume(channel_id, new_vol))
        event.stop()

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        state = get_state()
        channel_id = state.selected_channel_id
        if channel_id:
            channel = state.channels.get(channel_id)
            if channel:
                new_vol = min(1.0, channel.volume + 0.05)
                asyncio.create_task(state.set_volume(channel_id, new_vol))
        event.stop()

    def _set_volume_from_event(self, event: MouseDown | MouseMove | Click) -> None:
        """Calculate volume from horizontal mouse position, throttled during drag."""
        if self.size.width <= 0:
            return
        fraction = max(0.0, min(1.0, event.x / self.size.width))

        now = time.monotonic()
        if self._dragging and (now - self._last_set_time) < _VOLUME_THROTTLE_S:
            # Throttle: stash the latest target and schedule a deferred flush
            self._pending_volume = fraction
            if self._pending_task is None or self._pending_task.done():
                self._pending_task = asyncio.create_task(self._deferred_flush())
            return

        self._last_set_time = now
        self._pending_volume = None
        state = get_state()
        channel_id = state.selected_channel_id
        if channel_id:
            asyncio.create_task(state.set_volume(channel_id, fraction))

    async def _deferred_flush(self) -> None:
        """Flush the most recent pending volume after the throttle window."""
        await asyncio.sleep(_VOLUME_THROTTLE_S)
        if self._pending_volume is not None:
            volume = self._pending_volume
            self._pending_volume = None
            self._last_set_time = time.monotonic()
            state = get_state()
            channel_id = state.selected_channel_id
            if channel_id:
                await state.set_volume(channel_id, volume)

    def _flush_volume(self) -> None:
        """Flush pending volume immediately on mouse up."""
        if self._pending_volume is not None:
            volume = self._pending_volume
            self._pending_volume = None
            self._last_set_time = time.monotonic()
            state = get_state()
            channel_id = state.selected_channel_id
            if channel_id:
                asyncio.create_task(state.set_volume(channel_id, volume))
