"""Data models for the audio backend layer."""

from dataclasses import dataclass


@dataclass
class AudioApp:
    """Represents a discovered audio-playing application."""

    name: str
    sink_input_id: int
    sink_id: int
    pid: int | None = None
    binary: str = ""


@dataclass
class PipeWireNode:
    """Represents a PipeWire graph node."""

    node_id: int
    name: str
    description: str
    media_class: str
    props: dict
