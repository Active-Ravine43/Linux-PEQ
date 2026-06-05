"""Preset bar — quick EQ preset buttons."""

from __future__ import annotations

import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static

from peq_app.state.app_state import get_state
from peq_app.state.models import BUILTIN_PRESETS


class PresetBar(Horizontal):
    """Horizontal bar of preset buttons below the EQ panel."""

    def compose(self) -> ComposeResult:
        for preset in BUILTIN_PRESETS[:5]:  # First 5 presets
            yield Button(preset.name, id=f"preset-{preset.name.lower().replace(' ', '-')}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Apply the selected preset."""
        state = get_state()
        channel_id = state.selected_channel_id
        if channel_id is None:
            return

        preset_name = str(event.button.label)
        for preset in BUILTIN_PRESETS:
            if preset.name == preset_name:
                asyncio.create_task(state.apply_preset(channel_id, preset))
                return
