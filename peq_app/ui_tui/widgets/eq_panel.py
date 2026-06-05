"""EQ panel — 10-band parametric equalizer display."""

from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static

from peq_app.config import DEFAULT_BAND_FREQUENCIES
from peq_app.state.app_state import get_state
from peq_app.state.models import Channel
from peq_app.ui_tui.widgets.eq_band_widget import EQBandWidget
from peq_app.ui_tui.widgets.volume_slider import VolumeSlider


def _format_freq(freq_hz: float) -> str:
    """Format frequency for display."""
    if freq_hz >= 1000:
        return f"{freq_hz / 1000:.0f}k"
    return f"{freq_hz:.0f}"


class EQPanel(Vertical):
    """The main EQ display area with 10 vertical band sliders."""

    def compose(self):
        yield Static("Master", id="eq-header")
        with Horizontal(id="volume-row"):
            yield Static("Volume", classes="volume-label")
            yield VolumeSlider(id="channel-volume")
        with Horizontal(id="eq-bands-container"):
            for i in range(10):
                yield EQBandWidget(band_index=i, id=f"band-{i}")
        with Horizontal(id="freq-labels"):
            for f in DEFAULT_BAND_FREQUENCIES:
                yield Static(_format_freq(f), classes="freq-label")

    def on_mount(self) -> None:
        self._state = get_state()
        self._state.observe(self._on_state_change)
        self.set_interval(0.2, self.refresh_bands)

    async def _on_state_change(self, event: str, data: object) -> None:
        if event in ("channel_selected", "eq_changed", "preset_applied", "volume_changed"):
            self.refresh_bands()

    def refresh_bands(self) -> None:
        """Update band widgets and volume slider from current state (skip if clean)."""
        if not self._state.is_dirty:
            return
        self._state.clear_dirty()
        channel = self._state.selected_channel
        if channel is None:
            return

        # Update header
        header = self.query_one("#eq-header", Static)
        if channel.is_master:
            header.update("Master EQ")
        else:
            header.update(f"[bold]{channel.name}[/bold]")

        # Update volume slider
        try:
            vol_slider = self.query_one("#channel-volume", VolumeSlider)
            vol_slider.volume = channel.volume
        except Exception:
            pass

        # Update each band widget
        for i, band in enumerate(channel.eq_bands):
            try:
                widget = self.query_one(f"#band-{i}", EQBandWidget)
                widget.update_from_band(band, i)
            except Exception:
                pass

    def highlight_band(self, index: int) -> None:
        """Visually highlight a band by index (for keyboard shortcuts)."""
        for i in range(10):
            try:
                widget = self.query_one(f"#band-{i}", EQBandWidget)
                if i == index:
                    widget.add_class("-highlighted")
                else:
                    widget.remove_class("-highlighted")
            except Exception:
                pass
