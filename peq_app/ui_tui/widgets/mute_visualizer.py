"""3-column animated mute / visualizer widget with wave animation.

Displays a cycling 3-bar audio-visualizer wave when unmuted, and a
mute icon (🔇) when muted.  Clicking toggles mute via the global
AppState singleton.

Reduced-motion support: set ``PEQ_REDUCED_MOTION=1`` to replace the
animated wave with a static unmuted indicator (▆).
"""

from __future__ import annotations

import asyncio
import os

from textual.events import Click
from textual.reactive import reactive
from textual.widgets import Static

from peq_app.state.app_state import get_state

# ------------------------------------------------------------------
# Reduced-motion check
# ------------------------------------------------------------------

_REDUCED_MOTION = os.environ.get("PEQ_REDUCED_MOTION", "").strip() in ("1", "true", "yes")
_STATIC_UNMUTED = " ▆ "

# ------------------------------------------------------------------
# Pre-computed visualizer frames (14 frames, 3 bars each)
# ------------------------------------------------------------------

BLOCKS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

VISUALIZER_FRAMES: list[str] = []
for _t in range(14):
    chars: list[str] = []
    for bar in range(3):
        pos = (_t + bar * 5) % 14  # offset each bar for wave effect
        idx = pos if pos < 8 else 14 - pos  # triangle-wave fold
        chars.append(BLOCKS[idx])
    VISUALIZER_FRAMES.append("".join(chars))


# ------------------------------------------------------------------
# Widget
# ------------------------------------------------------------------


class MuteVisualizer(Static):
    """3-col animated mute/visualizer.

    When unmuted: cycles through a wave pattern of block-element bars
    (or shows a static indicator if reduced-motion is enabled).
    When muted:   displays the mute icon (U+1F507).
    Clicking toggles mute.  Manages its own animation ``Timer``.
    """

    muted: reactive[bool] = reactive(True)

    def __init__(self, channel_id: str, **kwargs) -> None:
        super().__init__("🔇", **kwargs)
        self.channel_id = channel_id
        self._frame = 0
        self._timer = None  # textual.Timer, set by set_interval
        self._reduced_motion = _REDUCED_MOTION

    # -- Reactive watcher --------------------------------------------------

    def watch_muted(self, muted: bool) -> None:
        """React to mute state changes: update icon / text, color, and timer."""
        if muted:
            self.add_class("-muted")
            self.styles.color = self._resolve_theme_color("danger", "#a05050")
            self.update("🔇")
            self._stop_animation()
        else:
            self.remove_class("-muted")
            self.styles.color = self._resolve_theme_color("accent", "#84848e")
            if self._reduced_motion:
                self.update(_STATIC_UNMUTED)
            else:
                self._frame = 0
                self.update(VISUALIZER_FRAMES[0])
                self._start_animation()

    def _resolve_theme_color(self, key: str, fallback: str) -> str:
        """Read a colour from the app's active theme, or return *fallback*."""
        try:
            if self.app is not None:
                c = getattr(self.app, "theme_colors", None)
                if isinstance(c, dict):
                    return c.get(key, fallback)
        except Exception:
            pass
        return fallback

    # -- Animation lifecycle -----------------------------------------------

    def _start_animation(self) -> None:
        """Begin the 14-frame wave cycle if not already running."""
        if self._reduced_motion:
            return
        if self._timer is None:
            self._timer = self.set_interval(0.15, self._advance_frame)

    def _stop_animation(self) -> None:
        """Stop the animation timer if running."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _advance_frame(self) -> None:
        """Advance to the next frame of the wave animation."""
        if not self.muted:
            self._frame = (self._frame + 1) % 14
            self.update(VISUALIZER_FRAMES[self._frame])

    # -- Click handling ----------------------------------------------------

    def on_click(self, event: Click) -> None:
        """Toggle mute on click. Stop propagation to prevent row selection."""
        event.stop()
        state = get_state()
        asyncio.create_task(state.toggle_mute(self.channel_id))

    # -- Cleanup -----------------------------------------------------------

    def on_unmount(self) -> None:
        """Ensure timer is cleaned up when widget is removed."""
        self._stop_animation()
