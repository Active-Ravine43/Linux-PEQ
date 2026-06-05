"""A single channel row in the channel panel."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from peq_app.state.app_state import get_state
from peq_app.state.models import Channel


class ChannelRow(Horizontal):
    """A row in the channel panel showing app name, volume, and selection state."""

    DEFAULT_CSS = """
    ChannelRow {
        height: 3;
        padding: 0 2;
        border-bottom: solid #1f1f23;
    }
    ChannelRow:hover {
        background: #1a1a1e;
    }
    ChannelRow.-selected {
        background: #1f1d18;
        border-left: solid #b8954a;
    }
    """

    def __init__(self, channel: Channel, selected: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.channel_id = channel.id
        self._selected = selected

    def compose(self) -> ComposeResult:
        yield Static("", classes="channel-name")
        yield Static("", classes="channel-volume-text")

    def on_mount(self) -> None:
        state = get_state()
        channel = state.channels.get(self.channel_id)
        if channel:
            self.update_from_channel(channel, self._selected)

    def update_from_channel(self, channel: Channel, selected: bool) -> None:
        """Refresh display from a Channel model."""
        name_widget = self.query_one(".channel-name", Static)
        vol_widget = self.query_one(".channel-volume-text", Static)

        if channel.is_master:
            name_widget.update("Master")
        else:
            name_widget.update(channel.name[:24])

        vol_pct = int(channel.volume * 100)
        if channel.is_muted:
            vol_widget.update("MUTED")
        else:
            vol_widget.update(f"{vol_pct}%")

        if selected:
            self.add_class("-selected")
        else:
            self.remove_class("-selected")

    def on_click(self) -> None:
        """Select this channel on click."""
        state = get_state()
        asyncio.create_task(state.select_channel(self.channel_id))
