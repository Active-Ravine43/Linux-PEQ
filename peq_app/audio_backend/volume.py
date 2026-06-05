"""Volume control via pactl (PulseAudio-compat CLI).

Uses pactl set-sink-input-volume and pactl list sink-inputs for reads,
since pactl only provides get-sink-volume (not get-sink-input-volume).
"""

from __future__ import annotations

import re
import subprocess

from peq_app.config import PACTL


class PWVolumeCtrl:
    """Reads and sets volume for PipeWire sink inputs and sinks using pactl."""

    @staticmethod
    def get_volume(sink_input_id: int) -> float | None:
        """Get current volume (0.0–1.0) of a sink input.

        Parses 'pactl list sink-inputs' since pactl lacks get-sink-input-volume.
        """
        try:
            result = subprocess.run(
                [PACTL, "list", "sink-inputs"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            return _parse_sink_input_volume(result.stdout, sink_input_id)
        except (subprocess.TimeoutExpired, OSError):
            return None

    @staticmethod
    def set_volume(sink_input_id: int, volume: float) -> bool:
        """Set volume (0.0–1.0) for a sink input."""
        clamped = max(0.0, min(1.0, volume))
        try:
            result = subprocess.run(
                [PACTL, "set-sink-input-volume", str(sink_input_id), f"{clamped:.4f}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def get_mute(sink_input_id: int) -> bool | None:
        """Check if a sink input is muted."""
        try:
            result = subprocess.run(
                [PACTL, "list", "sink-inputs"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return _parse_sink_input_mute(result.stdout, sink_input_id)
        except (subprocess.TimeoutExpired, OSError):
            return None

    @staticmethod
    def set_mute(sink_input_id: int, muted: bool) -> bool:
        """Set mute state for a sink input."""
        val = "1" if muted else "0"
        try:
            result = subprocess.run(
                [PACTL, "set-sink-input-mute", str(sink_input_id), val],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def toggle_mute(sink_input_id: int) -> bool:
        """Toggle mute state."""
        try:
            result = subprocess.run(
                [PACTL, "set-sink-input-mute", str(sink_input_id), "toggle"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def get_sink_volume(sink_name: str) -> float | None:
        """Get current volume of a named sink via pactl get-sink-volume."""
        try:
            result = subprocess.run(
                [PACTL, "get-sink-volume", sink_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            match = re.search(r"(\d+)%", result.stdout)
            if match:
                return int(match.group(1)) / 100.0
            return None
        except (subprocess.TimeoutExpired, OSError, ValueError):
            return None

    @staticmethod
    def set_sink_volume(sink_name: str, volume: float) -> bool:
        """Set volume for a named sink."""
        clamped = max(0.0, min(1.0, volume))
        try:
            result = subprocess.run(
                [PACTL, "set-sink-volume", sink_name, f"{clamped:.4f}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False


def _parse_sink_input_volume(output: str, target_id: int) -> float | None:
    """Extract volume from pactl list sink-inputs for a specific sink input."""
    in_target = False
    for line in output.splitlines():
        if f"Sink Input #{target_id}" in line:
            in_target = True
            continue
        if in_target:
            vol_match = re.match(r"\s*Volume:.*?(\d+)%", line)
            if vol_match:
                return int(vol_match.group(1)) / 100.0
            if line.startswith("Sink Input #"):
                break  # moved to next sink input
    return None


def _parse_sink_input_mute(output: str, target_id: int) -> bool | None:
    """Extract mute state from pactl list sink-inputs for a specific sink input."""
    in_target = False
    for line in output.splitlines():
        if f"Sink Input #{target_id}" in line:
            in_target = True
            continue
        if in_target:
            mute_match = re.match(r"\s*Mute:\s*(yes|no)", line)
            if mute_match:
                return mute_match.group(1) == "yes"
            if line.startswith("Sink Input #"):
                break
    return None
