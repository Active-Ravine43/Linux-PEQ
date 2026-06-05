"""Application discovery via pulsectl (PipeWire-Pulse compatibility layer).

Polls PipeWire for active audio sink-inputs (playback streams) and
returns them as AudioApp dataclass instances.
"""

from __future__ import annotations

import pulsectl

from peq_app.audio_backend.models import AudioApp


class PWNodeScanner:
    """Scans PipeWire for active audio applications using pulsectl."""

    def __init__(self) -> None:
        self._pulse = pulsectl.Pulse("peq-scanner")

    def scan(self) -> list[AudioApp]:
        """Return all currently active audio playback applications."""
        apps: list[AudioApp] = []
        try:
            for si in self._pulse.sink_input_list():
                props = si.proplist or {}
                name = props.get("application.name") or props.get("media.name") or f"Sink Input {si.index}"
                binary = props.get("application.process.binary", "")
                pid_str = props.get("application.process.id")
                pid = int(pid_str) if pid_str else None

                apps.append(AudioApp(
                    name=name,
                    sink_input_id=si.index,
                    sink_id=si.sink,
                    pid=pid,
                    binary=binary,
                ))
        except Exception:
            pass
        return apps

    def get_default_sink(self) -> str | None:
        """Return the name of the default audio sink."""
        try:
            info = self._pulse.server_info()
            return info.default_sink_name
        except Exception:
            return None

    def close(self) -> None:
        """Release the PulseAudio connection."""
        self._pulse.close()
