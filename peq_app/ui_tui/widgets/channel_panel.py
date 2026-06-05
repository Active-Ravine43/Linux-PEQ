"""Channel list panel — displays master + app channels."""

from __future__ import annotations

from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from peq_app.state.app_state import get_state
from peq_app.ui_tui.widgets.channel_row import ChannelRow


def _sanitize_id(channel_id: str) -> str:
    """Convert a channel ID into a valid Textual widget identifier.

    Textual IDs allow only letters, numbers, underscores, hyphens, and
    must not start with a number. Channel IDs can contain dots (e.g.
    ``sd_dummy.9911``), so we replace invalid characters.
    """
    sanitized = channel_id.replace(".", "_").replace("/", "_").replace("-", "_")
    # Prepend 'c-' so it never starts with a digit
    return f"c-{sanitized}"


class ChannelPanel(Vertical):
    """Left-hand panel listing all audio channels."""

    def compose(self):
        yield Static("CHANNELS", id="channel-header")
        with VerticalScroll(id="channel-list"):
            # Channels are dynamically added/removed via refresh
            pass

    def on_mount(self) -> None:
        self._state = get_state()
        self._state.observe(self._on_state_change)
        self.set_interval(0.5, self.refresh_channels)

    async def _on_state_change(self, event: str, data: object) -> None:
        if event in ("channels_updated", "channel_selected", "volume_changed"):
            self.refresh_channels()

    def refresh_channels(self) -> None:
        """Re-render the channel list from current state."""
        scroll = self.query_one("#channel-list", VerticalScroll)
        current_ids = {w.id for w in scroll.query(ChannelRow)}

        for cid, channel in self._state.channels.items():
            widget_id = f"channel-row-{_sanitize_id(cid)}"
            if widget_id in current_ids:
                # Update existing row
                row = scroll.query_one(f"#{widget_id}", ChannelRow)
                row.update_from_channel(channel, cid == self._state.selected_channel_id)
            else:
                # Add new row
                row = ChannelRow(
                    channel, selected=(cid == self._state.selected_channel_id), id=widget_id
                )
                scroll.mount(row)
                # Apply current theme to the newly created row
                if self.app is not None:
                    try:
                        self.app._theme_channel_row(row)  # type: ignore[union-attr]
                    except Exception:
                        pass

        # Remove stale rows
        valid_ids = {f"channel-row-{_sanitize_id(cid)}" for cid in self._state.channels}
        for widget_id in current_ids - valid_ids:
            try:
                scroll.query_one(f"#{widget_id}", ChannelRow).remove()
            except Exception:
                pass
