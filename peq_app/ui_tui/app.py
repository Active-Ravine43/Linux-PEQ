"""Main Textual application for the PEQ TUI."""

from __future__ import annotations

import asyncio
import logging

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static

from peq_app.audio_backend.scanner import PWNodeScanner
from peq_app.audio_backend.volume import PWVolumeCtrl
from peq_app.config import SCAN_INTERVAL, IGNORED_BINARIES
from peq_app.state.app_state import get_state
from peq_app.state.models import Channel
from peq_app.ui_tui.widgets.channel_panel import ChannelPanel
from peq_app.ui_tui.widgets.eq_panel import EQPanel
from peq_app.ui_tui.widgets.preset_bar import PresetBar
from peq_app.ui_tui.widgets.status_footer import StatusFooter
from peq_app.ui_tui.widgets.volume_slider import VolumeSlider

logger = logging.getLogger(__name__)


class EQApp(App):
    """PEQ — Per-application Parametric Equalizer TUI."""

    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        ("tab", "focus_next_channel", "Next channel"),
        ("shift+tab", "focus_prev_channel", "Prev channel"),
        ("m", "toggle_mute", "Mute"),
        ("1", "select_band(0)", "Band 1"),
        ("2", "select_band(1)", "Band 2"),
        ("3", "select_band(2)", "Band 3"),
        ("4", "select_band(3)", "Band 4"),
        ("5", "select_band(4)", "Band 5"),
        ("6", "select_band(5)", "Band 6"),
        ("7", "select_band(6)", "Band 7"),
        ("8", "select_band(7)", "Band 8"),
        ("9", "select_band(8)", "Band 9"),
        ("0", "select_band(9)", "Band 10"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._state = get_state()
        self._scanner = PWNodeScanner()
        self._scan_timer: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        """Compose the widget tree."""
        yield Header(show_clock=True)
        with Container(id="app-container"):
            yield ChannelPanel()
            with Vertical(id="eq-area"):
                yield EQPanel()
                yield PresetBar()
        yield StatusFooter()

    async def on_mount(self) -> None:
        """Start scanning for audio apps."""
        self._state.observe(self._on_state_event)
        self._scan_timer = asyncio.create_task(self._scan_loop())

    async def on_unmount(self) -> None:
        """Clean up."""
        if self._scan_timer:
            self._scan_timer.cancel()
        self._scanner.close()

    # ------------------------------------------------------------------
    # Scanning loop
    # ------------------------------------------------------------------

    async def _scan_loop(self) -> None:
        """Periodically scan for audio apps and update state."""
        while True:
            try:
                apps = self._scanner.scan()
                for app in apps:
                    if app.binary in IGNORED_BINARIES:
                        continue
                    channel_id = f"{app.binary}.{app.pid}" if app.binary else f"app.{app.sink_input_id}"
                    name = app.name or app.binary or f"App {app.sink_input_id}"

                    existing = self._state.channels.get(channel_id)
                    if existing is None:
                        channel = Channel(
                            id=channel_id,
                            name=name,
                            pipewire_node_id=app.sink_input_id,
                            volume=1.0,
                            app_binary=app.binary,
                        )
                        await self._state.add_channel(channel)
                    elif existing.pipewire_node_id != app.sink_input_id:
                        existing.pipewire_node_id = app.sink_input_id

                # Build set of currently seen app IDs
                seen_ids: set[str] = set()
                for app in apps:
                    cid = f"{app.binary}.{app.pid}" if app.binary else f"app.{app.sink_input_id}"
                    seen_ids.add(cid)
                await self._state.sync_channels(seen_ids)

                # Refresh volumes for all channels
                for cid, channel in self._state.channels.items():
                    if not channel.is_master and channel.pipewire_node_id is not None:
                        vol = PWVolumeCtrl.get_volume(channel.pipewire_node_id)
                        if vol is not None and abs(vol - channel.volume) > 0.01:
                            await self._state.set_volume(cid, vol)
                        muted = PWVolumeCtrl.get_mute(channel.pipewire_node_id)
                        if muted is not None and muted != channel.is_muted:
                            await self._state.set_mute(cid, muted)

            except Exception:
                logger.exception("Scan loop error")

            await asyncio.sleep(SCAN_INTERVAL)

    # ------------------------------------------------------------------
    # State observer
    # ------------------------------------------------------------------

    async def _on_state_event(self, event: str, data: object) -> None:
        """Handle state change notifications."""
        # The TUI widgets are reactive — they read from AppState directly
        # on refresh. This callback is for side effects (audio backend calls).

        if event == "volume_changed" and isinstance(data, dict):
            cid = data.get("channel_id")
            channel = self._state.channels.get(cid)
            if channel and channel.pipewire_node_id is not None:
                if "volume" in data:
                    PWVolumeCtrl.set_volume(channel.pipewire_node_id, data["volume"])
                if "muted" in data:
                    PWVolumeCtrl.set_mute(channel.pipewire_node_id, data["muted"])

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_focus_next_channel(self) -> None:
        """Select the next channel in the list."""
        channel_ids = [cid for cid in self._state.channels]
        if not channel_ids:
            return
        current = self._state.selected_channel_id
        try:
            idx = channel_ids.index(current) if current else -1
        except ValueError:
            idx = -1
        next_idx = (idx + 1) % len(channel_ids)
        asyncio.create_task(self._state.select_channel(channel_ids[next_idx]))

    def action_focus_prev_channel(self) -> None:
        """Select the previous channel in the list."""
        channel_ids = [cid for cid in self._state.channels]
        if not channel_ids:
            return
        current = self._state.selected_channel_id
        try:
            idx = channel_ids.index(current) if current else 0
        except ValueError:
            idx = 0
        prev_idx = (idx - 1) % len(channel_ids)
        asyncio.create_task(self._state.select_channel(channel_ids[prev_idx]))

    def action_toggle_mute(self) -> None:
        """Toggle mute for the selected channel."""
        cid = self._state.selected_channel_id
        if cid:
            asyncio.create_task(self._state.toggle_mute(cid))

    def action_select_band(self, index: int) -> None:
        """Select an EQ band by index (0-9)."""
        # This is handled by the EQ panel's focus
        eq_panel = self.query_one(EQPanel)
        eq_panel.highlight_band(index)


def run_app() -> None:
    """Entry point for the TUI."""
    app = EQApp()
    app.run()
