"""A single channel row in the channel panel.

Selection is indicated by background color only — no side-stripe borders.
All styling lives in ``app.tcss``; this widget has no inline CSS.
"""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from peq_app.state.app_state import get_state
from peq_app.state.models import Channel
from peq_app.ui_tui.widgets.mute_visualizer import MuteVisualizer


class ChannelRow(Horizontal):
    """A row in the channel panel showing mute visualizer, app name, volume, and selection state.

    Styles are defined in ``app.tcss``. Selection uses background tint
    (``-selected`` class) with no side-stripe border.
    """

    def __init__(self, channel: Channel, selected: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.channel_id = channel.id
        self._selected = selected

    def compose(self) -> ComposeResult:
        yield MuteVisualizer(self.channel_id, classes="channel-mute-btn")
        yield Static("", classes="channel-name")
        yield Static("", classes="channel-volume-text")

    def on_mount(self) -> None:
        state = get_state()
        channel = state.channels.get(self.channel_id)
        if channel:
            self.update_from_channel(channel, self._selected)

    def update_from_channel(self, channel: Channel, selected: bool) -> None:
        """Refresh display from a Channel model."""
        mute_viz = self.query_one(".channel-mute-btn", MuteVisualizer)
        name_widget = self.query_one(".channel-name", Static)
        vol_widget = self.query_one(".channel-volume-text", Static)

        if channel.is_master:
            name_widget.update("Master")
        else:
            name_widget.update(channel.name[:24])

        vol_pct = int(channel.volume * 100)
        mute_viz.muted = channel.is_muted
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
