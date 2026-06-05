"""Manages PipeWire filter-chain .conf file CRUD.

Each EQ chain lives as a .conf file in ~/.config/peq/filter-chains/
and is symlinked or written to ~/.config/pipewire/filter-chain.conf.d/
so the separate pipewire process picks it up.

The config format is a subset of PipeWire's filter-chain.conf module args,
generated programmatically and not intended for manual editing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from peq_app.config import (
    DEFAULT_BAND_FREQUENCIES,
    DEFAULT_BAND_TYPES,
    DEFAULT_Q,
    FILTER_CHAIN_DIR,
    PIPEWIRE_CONFIG_DIR,
)


def _build_filter_graph_json(
    channel_id: str,
    bands: list[dict] | None = None,
) -> dict:
    """Build a complete filter-chain context.modules config dict.

    Args:
        channel_id: Unique ID for this EQ chain (e.g. "firefox.12345")
        bands: Optional list of band dicts with keys freq_hz, gain_db, q, filter_type.
               Defaults to 10 flat bands.
    """
    if bands is None:
        bands = [
            {"freq_hz": f, "gain_db": 0.0, "q": DEFAULT_Q, "filter_type": t}
            for f, t in zip(DEFAULT_BAND_FREQUENCIES, DEFAULT_BAND_TYPES)
        ]

    graph_nodes = []
    graph_links = []

    for i, band in enumerate(bands):
        name = f"eq_band_{i + 1}"
        graph_nodes.append(
            {
                "type": "builtin",
                "name": name,
                "label": f"bq_{band['filter_type']}",
                "control": {
                    "Freq": band["freq_hz"],
                    "Q": band["q"],
                    "Gain": band["gain_db"],
                },
            }
        )
        if i > 0:
            graph_links.append(
                {
                    "output": f"eq_band_{i}:Out",
                    "input": f"eq_band_{i + 1}:In",
                }
            )

    safe_id = channel_id.replace(".", "_").replace("/", "_")

    return {
        "context.modules": [
            {
                "name": "libpipewire-module-filter-chain",
                "args": {
                    "node.description": f"PEQ: {channel_id}",
                    "media.name": f"peq_{safe_id}",
                    "filter.graph": {
                        "nodes": graph_nodes,
                        "links": graph_links,
                    },
                    "audio.channels": 2,
                    "audio.position": ["FL", "FR"],
                    "capture.props": {
                        "node.name": f"peq_{safe_id}_input",
                        "media.class": "Audio/Sink",
                    },
                    "playback.props": {
                        "node.name": f"peq_{safe_id}_output",
                        "node.passive": True,
                    },
                },
            }
        ]
    }


def _format_conf_value(value) -> str:
    """Format a Python value as a PipeWire conf value string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value == int(value):
            return f"{value:.1f}"
        return str(value)
    raise TypeError(f"Cannot format conf value of type {type(value)}: {value!r}")


def _format_conf_dict(d: dict, indent: int = 0) -> str:
    """Format a Python dict as PipeWire conf syntax."""
    pad = "    " * indent
    inner_pad = "    " * (indent + 1)
    lines = []

    for key, value in d.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key} = {{")
            lines.append(_format_conf_dict(value, indent + 1))
            lines.append(f"{pad}}}")
        elif isinstance(value, list):
            if all(isinstance(v, dict) for v in value):
                lines.append(f"{pad}{key} = [")
                for i, item in enumerate(value):
                    lines.append(f"{pad}    {{")
                    lines.append(_format_conf_dict(item, indent + 2))
                    lines.append(f"{pad}    }}")
                lines.append(f"{pad}]")
            else:
                formatted = ", ".join(_format_conf_value(v) for v in value)
                lines.append(f"{pad}{key} = [ {formatted} ]")
        else:
            lines.append(f"{pad}{key} = {_format_conf_value(value)}")

    return "\n".join(lines)


def write_filter_chain_conf(channel_id: str, bands: list[dict] | None = None) -> Path:
    """Write a filter-chain .conf file for the given channel.

    Returns the path to the written config file.
    """
    graph = _build_filter_graph_json(channel_id, bands)
    conf_text = _format_conf_dict(graph)

    safe_id = channel_id.replace(".", "_").replace("/", "_")
    conf_path = FILTER_CHAIN_DIR / f"{safe_id}.conf"

    conf_path.parent.mkdir(parents=True, exist_ok=True)
    conf_path.write_text(conf_text)

    # Symlink into PipeWire's filter-chain conf.d so the process picks it up
    pw_link_path = PIPEWIRE_CONFIG_DIR / f"peq_{safe_id}.conf"
    if pw_link_path.exists() or pw_link_path.is_symlink():
        pw_link_path.unlink()
    try:
        os.symlink(conf_path, pw_link_path)
    except OSError:
        # Fallback: copy the file
        import shutil

        shutil.copy2(conf_path, pw_link_path)

    return conf_path


def remove_filter_chain_conf(channel_id: str) -> None:
    """Remove a filter-chain .conf file and its PipeWire symlink."""
    safe_id = channel_id.replace(".", "_").replace("/", "_")

    conf_path = FILTER_CHAIN_DIR / f"{safe_id}.conf"
    if conf_path.exists():
        conf_path.unlink()

    pw_link_path = PIPEWIRE_CONFIG_DIR / f"peq_{safe_id}.conf"
    if pw_link_path.exists() or pw_link_path.is_symlink():
        pw_link_path.unlink()


def build_set_param_payload(
    band_index: int,
    freq_hz: float | None = None,
    gain_db: float | None = None,
    q: float | None = None,
) -> str:
    """Build a JSON payload string for pw-cli set-param.

    Only includes the parameters that are explicitly provided (non-None).
    """
    params = []
    band_name = f"eq_band_{band_index + 1}"
    if freq_hz is not None:
        params.extend([f"{band_name}:Freq", freq_hz])
    if gain_db is not None:
        params.extend([f"{band_name}:Gain", gain_db])
    if q is not None:
        params.extend([f"{band_name}:Q", q])
    payload = {"params": params}
    return json.dumps(payload)
