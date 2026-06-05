"""Audio routing via pactl (PulseAudio-compat CLI).

Moves sink inputs between sinks (e.g. routing an app through its EQ chain).
"""

from __future__ import annotations

import subprocess

from peq_app.config import PACTL


class PWRouter:
    """Routes audio streams between PipeWire sinks using pactl."""

    @staticmethod
    def move_sink_input(sink_input_id: int, sink_name: str) -> bool:
        """Move a sink input to a different sink by name.

        Args:
            sink_input_id: The ID of the sink input to move.
            sink_name: The name of the destination sink (e.g. "peq_firefox_12345_input").
        """
        try:
            result = subprocess.run(
                [PACTL, "move-sink-input", str(sink_input_id), sink_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def get_sink_by_name(name: str) -> int | None:
        """Find a sink index by its name. Returns None if not found."""
        try:
            result = subprocess.run(
                [PACTL, "list", "short", "sinks"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2 and parts[1] == name:
                    return int(parts[0])
            return None
        except (subprocess.TimeoutExpired, OSError, ValueError):
            return None

    @staticmethod
    def get_default_sink_name() -> str | None:
        """Get the default sink name from pactl."""
        try:
            result = subprocess.run(
                [PACTL, "info"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in result.stdout.splitlines():
                if "Default Sink:" in line:
                    return line.split(":", 1)[1].strip()
            return None
        except (subprocess.TimeoutExpired, OSError):
            return None
