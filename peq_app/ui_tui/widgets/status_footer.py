"""Status footer bar with theme flash support."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from peq_app.state.app_state import get_state


class StatusFooter(Horizontal):
    """Bottom status bar showing PipeWire info and keyboard shortcuts."""

    def compose(self) -> ComposeResult:
        yield Static("PEQ", classes="status-left")
        yield Static(
            "Tab: switch  ·  m: mute  ·  1-0: bands  ·  t: theme  ·  q: quit",
            classes="status-right",
        )

    def on_mount(self) -> None:
        self._state = get_state()
        self._state.observe(self._on_state_change)
        self._refresh()

    async def _on_state_change(self, event: str, data: object) -> None:
        if event in ("channel_selected", "volume_changed", "channels_updated"):
            self._refresh()

    def _refresh(self) -> None:
        state = self._state
        channel = state.selected_channel
        if channel:
            left = self.query_one(".status-left", Static)
            muted = "[MUTED] " if channel.is_muted else ""
            vol = int(channel.volume * 100)
            eq_active = " EQ" if channel.is_eq_active else ""
            left.update(f"PEQ  ·  {channel.name}  ·  {muted}{vol}%{eq_active}")

    def flash_theme(self, theme_name: str) -> None:
        """Briefly show the new theme name in the status bar."""
        left = self.query_one(".status-left", Static)
        left.update(f"Theme: {theme_name}")

    def show_narrow_warning(self, width: int, min_width: int) -> None:
        """Show a narrow-terminal warning in the right side of the footer."""
        right = self.query_one(".status-right", Static)
        right.update(f"⚠ Narrow: {width} cols — resize to ≥{min_width}")

    def clear_narrow_warning(self) -> None:
        """Restore the default shortcuts display."""
        right = self.query_one(".status-right", Static)
        right.update(
            "Tab: switch  ·  m: mute  ·  1-0: bands  ·  t: theme  ·  q: quit"
        )
