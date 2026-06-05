"""Preset bar — quick EQ preset buttons fill the full width."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button

from peq_app.state.app_state import get_state
from peq_app.state.models import BUILTIN_PRESETS


class PresetBar(Horizontal):
    """Horizontal bar of preset buttons below the EQ panel.

    Buttons use ``width: 1fr`` in CSS so they distribute evenly
    across the full bar width regardless of terminal size.
    """

    @staticmethod
    def _preset_id(name: str) -> str:
        """Build a CSS-safe widget id from a preset name."""
        safe = "".join(c if c.isalnum() else "-" for c in name.lower())
        # Collapse consecutive hyphens and strip leading/trailing
        while "--" in safe:
            safe = safe.replace("--", "-")
        return f"preset-{safe.strip('-')}"

    def compose(self) -> ComposeResult:
        for preset in BUILTIN_PRESETS:
            yield Button(
                preset.name,
                id=self._preset_id(preset.name),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Apply the selected preset to the current channel."""
        state = get_state()
        channel_id = state.selected_channel_id
        if channel_id is None:
            return

        preset_name = str(event.button.label)
        for preset in BUILTIN_PRESETS:
            if preset.name == preset_name:
                asyncio.create_task(state.apply_preset(channel_id, preset))
                return
