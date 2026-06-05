"""Main Textual application for the PEQ TUI.

Minimalist dark theme system with 3 variants:
  Amber (default) — warm desaturated gold accent
  Slate           — cool blue-grey accent
  Mono            — pure greyscale accent

Press ``t`` to cycle themes at runtime.
"""

from __future__ import annotations

import asyncio
import logging

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from peq_app.audio_backend.scanner import PWNodeScanner
from peq_app.audio_backend.volume import PWVolumeCtrl
from peq_app.config import IGNORED_BINARIES, SCAN_INTERVAL
from peq_app.state.app_state import get_state
from peq_app.state.models import Channel
from peq_app.ui_tui.widgets.channel_panel import ChannelPanel
from peq_app.ui_tui.widgets.channel_row import ChannelRow
from peq_app.ui_tui.widgets.eq_band_widget import EQBandWidget
from peq_app.ui_tui.widgets.eq_panel import EQPanel
from peq_app.ui_tui.widgets.preset_bar import PresetBar
from peq_app.ui_tui.widgets.status_footer import StatusFooter
from peq_app.ui_tui.widgets.mute_visualizer import MuteVisualizer
from peq_app.ui_tui.widgets.volume_slider import VolumeSlider

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Theme definitions
# ------------------------------------------------------------------

THEMES = {
    "amber": {
        "name": "Amber",
        "canvas": "#0d0d0f",
        "surface": "#121215",
        "surface_hover": "#1a1a1e",
        "surface_selected": "#1f1d18",
        "border": "#2a2a2e",
        "border_subtle": "#1f1f23",
        "text": "#d4d4d8",
        "text_dim": "#909099",
        "text_muted": "#84848e",
        "accent": "#b8954a",
        "accent_dim": "#8a7038",
        "danger": "#b84a4a",
        "danger_dim": "#8a3838",
        "band_track": "#1f1f23",
        "band_neutral": "#3a3a3e",
    },
    "slate": {
        "name": "Slate",
        "canvas": "#0d0f11",
        "surface": "#141618",
        "surface_hover": "#1c1e22",
        "surface_selected": "#181c22",
        "border": "#2a2d30",
        "border_subtle": "#1e2124",
        "text": "#d0d3d8",
        "text_dim": "#8a9099",
        "text_muted": "#808a94",
        "accent": "#7b9bb8",
        "accent_dim": "#5a7a94",
        "danger": "#b85a5a",
        "danger_dim": "#8a4242",
        "band_track": "#1e2124",
        "band_neutral": "#383c42",
    },
    "mono": {
        "name": "Mono",
        "canvas": "#0d0d0e",
        "surface": "#131314",
        "surface_hover": "#1b1b1c",
        "surface_selected": "#1a1a1b",
        "border": "#2b2b2d",
        "border_subtle": "#1f1f21",
        "text": "#d0d0d2",
        "text_dim": "#8a8a8e",
        "text_muted": "#808085",
        "accent": "#909090",
        "accent_dim": "#6e6e6e",
        "danger": "#a05050",
        "danger_dim": "#783c3c",
        "band_track": "#1f1f21",
        "band_neutral": "#39393b",
    },
}

THEME_ORDER = ["amber", "slate", "mono"]


class EQApp(App):
    """PEQ — Per-application Parametric Equalizer TUI."""

    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        ("tab", "focus_next_channel", "Next channel"),
        ("shift+tab", "focus_prev_channel", "Prev channel"),
        ("m", "toggle_mute", "Mute"),
        ("t", "cycle_theme", "Theme"),
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
        self._current_theme: str = "amber"

    @property
    def theme_colors(self) -> dict:
        """Current theme's color palette."""
        return THEMES[self._current_theme]

    def compose(self) -> ComposeResult:
        """Compose the widget tree."""
        yield Header(show_clock=True)
        with Container(id="app-container"):
            yield ChannelPanel()
            with Vertical(id="eq-area"):
                yield EQPanel(id="eq-panel")
                yield PresetBar(id="preset-bar")
        yield StatusFooter()

    async def on_mount(self) -> None:
        """Start scanning for audio apps and apply the default theme."""
        self._state.observe(self._on_state_event)
        self._scan_timer = asyncio.create_task(self._scan_loop())
        self._apply_theme()
        self._check_terminal_width()

    async def on_unmount(self) -> None:
        """Clean up."""
        if self._scan_timer:
            self._scan_timer.cancel()
        self._scanner.close()

    # ------------------------------------------------------------------
    # Theme switching
    # ------------------------------------------------------------------

    def action_cycle_theme(self) -> None:
        """Cycle to the next theme (amber → slate → mono → amber)."""
        current_idx = THEME_ORDER.index(self._current_theme)
        next_idx = (current_idx + 1) % len(THEME_ORDER)
        self._current_theme = THEME_ORDER[next_idx]
        self._apply_theme()

        try:
            footer = self.query_one(StatusFooter)
            footer.flash_theme(THEMES[self._current_theme]["name"])
        except Exception:
            pass

    def _apply_theme(self) -> None:
        """Walk every themed widget and apply the current palette.

        This is called on mount and on every theme cycle.  It must touch
        every widget whose color is set by CSS so that runtime overrides
        match the selected theme.
        """
        c = self.theme_colors

        # -- Screen --------------------------------------------------
        self.screen.styles.background = c["canvas"]
        self.screen.styles.color = c["text"]

        # -- Header --------------------------------------------------
        try:
            hdr = self.query_one(Header)
            hdr.styles.background = c["surface"]
        except Exception:
            pass

        # -- Channel panel container ---------------------------------
        try:
            cp = self.query_one("#channel-panel")
            cp.styles.background = c["canvas"]
            cp.styles.border_right = ("solid", c["border"])
        except Exception:
            pass

        # -- Channel header ------------------------------------------
        try:
            ch = self.query_one("#channel-header")
            ch.styles.background = c["surface"]
            ch.styles.border_bottom = ("solid", c["border"])
            ch.styles.color = c["text"]
        except Exception:
            pass

        # -- Channel rows (all) --------------------------------------
        for row in self.query(ChannelRow):
            self._theme_channel_row(row, c)

        # -- EQ panel ------------------------------------------------
        try:
            eqp = self.query_one("#eq-panel")
            eqp.styles.background = c["canvas"]
        except Exception:
            pass

        # -- EQ header -----------------------------------------------
        try:
            eqh = self.query_one("#eq-header")
            eqh.styles.color = c["text"]
        except Exception:
            pass

        # -- Volume label --------------------------------------------
        try:
            vl = self.query_one(".volume-label")
            vl.styles.color = c["text_dim"]
        except Exception:
            pass

        # -- Volume slider track + fill ------------------------------
        try:
            vs = self.query_one(VolumeSlider)
            vs.styles.background = c["band_track"]
        except Exception:
            pass
        try:
            sf = self.query_one(".slider-fill")
            sf.styles.background = c["accent"]
        except Exception:
            pass

        # -- EQ band widgets (all) — structural theme ------------------
        for band in self.query(EQBandWidget):
            self._theme_band_widget(band, c)

        # -- EQ band fills — data-driven refresh with new theme colours -
        channel = self._state.selected_channel
        if channel:
            for i, eq_band in enumerate(channel.eq_bands):
                try:
                    widget = self.query_one(f"#band-{i}", EQBandWidget)
                    widget.update_from_band(eq_band, i)
                except Exception:
                    pass

        # -- Frequency labels ----------------------------------------
        try:
            fl = self.query_one("#freq-labels")
            fl.styles.color = c["text_dim"]
        except Exception:
            pass
        for lbl in self.query(".freq-label"):
            lbl.styles.color = c["text_dim"]

        # -- Preset bar ----------------------------------------------
        try:
            pb = self.query_one("#preset-bar")
            pb.styles.background = c["surface"]
            pb.styles.border_top = ("solid", c["border"])
        except Exception:
            pass

        # -- Preset buttons ------------------------------------------
        for btn in self.query("Button"):
            if btn.id and btn.id.startswith("preset-"):
                btn.styles.background = c["band_track"]
                btn.styles.color = c["text"]
                btn.styles.border = ("solid", c["border"])

        # -- Status footer -------------------------------------------
        try:
            sf = self.query_one("#status-footer")
            sf.styles.background = c["surface"]
            sf.styles.border_top = ("solid", c["border"])
            sf.styles.color = c["text_dim"]
        except Exception:
            pass

        # -- Empty state ---------------------------------------------
        try:
            ee = self.query_one("#empty-eq")
            ee.styles.color = c["text_muted"]
        except Exception:
            pass

        # Refresh the screen so everything repaints
        self.screen.refresh()

    def _check_terminal_width(self) -> None:
        """Warn if terminal is too narrow for the full EQ layout."""
        width = self.size.width
        min_width = 100
        try:
            footer = self.query_one(StatusFooter)
            if width < min_width:
                if not hasattr(self, "_narrow_warning_shown"):
                    self._narrow_warning_shown = True
                footer.show_narrow_warning(width, min_width)
            else:
                footer.clear_narrow_warning()
        except Exception:
            pass

    def on_resize(self) -> None:
        """Re-check terminal width when the window is resized."""
        self._check_terminal_width()

    # ------------------------------------------------------------------
    # Per-widget theme helpers (also called from widgets on refresh)
    # ------------------------------------------------------------------

    def _theme_channel_row(self, row: ChannelRow, c: dict | None = None) -> None:
        """Apply theme colors to a single ChannelRow."""
        if c is None:
            c = self.theme_colors
        # Row background — selected gets accent tint, default gets canvas
        if row.has_class("-selected"):
            row.styles.background = c["surface_selected"]
        else:
            row.styles.background = c["canvas"]
        row.styles.border_bottom = ("solid", c["border_subtle"])
        try:
            row.query_one(".channel-name", Static).styles.color = c["text"]
        except Exception:
            pass
        try:
            row.query_one(".channel-volume-text", Static).styles.color = c["text_dim"]
        except Exception:
            pass
        try:
            mute_viz = row.query_one(".channel-mute-btn", MuteVisualizer)
            mute_viz.styles.background = c["band_track"]
            if mute_viz.has_class("-muted"):
                mute_viz.styles.color = c["danger"]
            else:
                mute_viz.styles.color = c["accent"]
        except Exception:
            pass

    def _theme_band_widget(self, band: EQBandWidget, c: dict | None = None) -> None:
        """Apply structural theme colors to a single EQBandWidget.

        Fill colour is data-driven (depends on gain_db), not theme-driven.
        This method handles the track background, labels, and caches the
        current accent/neutral for update_from_band to use.
        """
        if c is None:
            c = self.theme_colors
        # Cache colours on the widget so update_from_band doesn't re-query
        band.cache_theme_colors(c["accent"], c["band_neutral"])
        try:
            band.query_one(".band-track", Static).styles.background = c["band_track"]
        except Exception:
            pass
        try:
            band.query_one(".band-gain-label", Static).styles.color = c["text_dim"]
        except Exception:
            pass
        try:
            band.query_one(".band-freq-label", Static).styles.color = c["text_dim"]
        except Exception:
            pass

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
                    channel_id = (
                        f"{app.binary}.{app.pid}" if app.binary else f"app.{app.sink_input_id}"
                    )
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

                seen_ids: set[str] = set()
                for app in apps:
                    cid = f"{app.binary}.{app.pid}" if app.binary else f"app.{app.sink_input_id}"
                    seen_ids.add(cid)
                await self._state.sync_channels(seen_ids)

                for cid, channel in self._state.channels.items():
                    if not channel.is_master and channel.pipewire_node_id is not None:
                        vol = PWVolumeCtrl.get_volume(channel.pipewire_node_id)
                        if vol is not None:
                            # sync_volume_from_hardware re-asserts user-set
                            # volume against external overrides (e.g. PipeWire
                            # session manager restoring stream volumes).
                            await self._state.sync_volume_from_hardware(cid, vol)
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
        eq_panel = self.query_one(EQPanel)
        eq_panel.highlight_band(index)


def run_app() -> None:
    """Entry point for the TUI."""
    app = EQApp()
    app.run()
