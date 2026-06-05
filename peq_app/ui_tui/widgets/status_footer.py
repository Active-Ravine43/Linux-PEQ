"""Status footer bar."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from peq_app.state.app_state import get_state


class StatusFooter(Horizontal):
    """Bottom status bar showing PipeWire info and shortcuts."""

    def compose(self) -> ComposeResult:
        yield Static("PEQ", classes="status-left")
        yield Static("Tab: switch  ·  m: mute  ·  1-0: bands  ·  q: quit", classes="status-right")

    def on_mount(self) -> None:
        self.set_interval(2.0, self._refresh)

    def _refresh(self) -> None:
        state = get_state()
        channel = state.selected_channel
        if channel:
            left = self.query_one(".status-left", Static)
            muted = "[MUTED] " if channel.is_muted else ""
            vol = int(channel.volume * 100)
            eq_active = "EQ" if channel.is_eq_active else ""
            left.update(f"PEQ  ·  {channel.name}  ·  {muted}{vol}%  {eq_active}")
