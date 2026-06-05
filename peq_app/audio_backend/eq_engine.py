"""Parametric EQ engine — filter-chain lifecycle and runtime control.

This is the core of peq. Each EQ channel runs as a separate PipeWire
process (pipewire -c filter-chain.conf) with its own filter-chain config
file. Runtime band adjustments are sent via pw-cli set-param.

Architecture:
  EQ Creation:  write .conf → launch pipewire subprocess → capture node ID
  EQ Update:    pw-cli set-param <node_id> Props '{...}'
  EQ Teardown:  SIGTERM subprocess → remove .conf file
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from peq_app.audio_backend.config_manager import (
    build_set_param_payload,
    remove_filter_chain_conf,
    write_filter_chain_conf,
)
from peq_app.config import (
    FILTER_CHAIN_DIR,
    PIPEWIRE,
    PIPEWIRE_CONFIG_DIR,
    PW_CLI,
)

logger = logging.getLogger(__name__)

# How long to wait for the filter-chain node to appear after launch
NODE_APPEAR_TIMEOUT = 5.0
# Poll interval while waiting
NODE_POLL_INTERVAL = 0.2


class EQChainError(Exception):
    """Raised when an EQ chain operation fails."""


class PWEQEngine:
    """Manages per-channel parametric EQ filter chains."""

    def __init__(self) -> None:
        # Track running processes: {channel_id: subprocess.Popen}
        self._processes: dict[str, subprocess.Popen] = {}
        # Track node IDs: {channel_id: filter_node_id}
        self._nodes: dict[str, int] = {}

    # ------------------------------------------------------------------
    # EQ Chain Lifecycle
    # ------------------------------------------------------------------

    def create_eq_chain(
        self,
        channel_id: str,
        bands: list[dict] | None = None,
    ) -> int:
        """Create a new EQ filter-chain for a channel.

        Writes the filter-chain .conf file, launches a pipewire subprocess,
        waits for the virtual sink node to appear, and returns its node ID.

        Args:
            channel_id: Unique channel identifier (e.g. "firefox.12345").
            bands: Optional list of band config dicts. Defaults to flat 10-band EQ.

        Returns:
            The PipeWire node ID of the filter-chain sink (for set-param).

        Raises:
            EQChainError: If the chain fails to create or the node doesn't appear.
        """
        if channel_id in self._processes:
            self.destroy_eq_chain(channel_id)

        safe_id = channel_id.replace(".", "_").replace("/", "_")
        expected_node_name = f"peq_{safe_id}_input"

        # 1. Write the config file
        conf_path = write_filter_chain_conf(channel_id, bands)
        logger.info("Wrote filter-chain config: %s", conf_path)

        # 2. Launch the pipewire process
        try:
            proc = subprocess.Popen(
                [
                    PIPEWIRE,
                    "-c",
                    "filter-chain.conf",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                # Don't create a new process group so signals propagate naturally
            )
            self._processes[channel_id] = proc
            logger.info("Launched pipewire (pid=%d) for channel %s", proc.pid, channel_id)
        except OSError as exc:
            remove_filter_chain_conf(channel_id)
            raise EQChainError(f"Failed to launch pipewire process: {exc}") from exc

        # 3. Wait for the sink node to appear
        node_id = self._wait_for_node(expected_node_name, timeout=NODE_APPEAR_TIMEOUT)
        if node_id is None:
            # Clean up on failure
            self.destroy_eq_chain(channel_id)
            raise EQChainError(
                f"Filter-chain node '{expected_node_name}' did not appear "
                f"within {NODE_APPEAR_TIMEOUT}s"
            )

        self._nodes[channel_id] = node_id
        logger.info("EQ chain %s ready: node_id=%d", channel_id, node_id)
        return node_id

    def destroy_eq_chain(self, channel_id: str) -> None:
        """Tear down an EQ filter-chain: kill the pipewire process and remove config."""
        proc = self._processes.pop(channel_id, None)
        self._nodes.pop(channel_id, None)

        if proc is not None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
            logger.info("Stopped pipewire process for channel %s", channel_id)

        remove_filter_chain_conf(channel_id)

    def destroy_all(self) -> None:
        """Tear down all EQ chains."""
        for channel_id in list(self._processes.keys()):
            self.destroy_eq_chain(channel_id)

    def get_node_id(self, channel_id: str) -> int | None:
        """Return the filter-chain node ID for a channel, or None."""
        return self._nodes.get(channel_id)

    # ------------------------------------------------------------------
    # Runtime EQ Band Control (pw-cli set-param)
    # ------------------------------------------------------------------

    def update_band(
        self,
        node_id: int,
        band_index: int,
        freq_hz: float | None = None,
        gain_db: float | None = None,
        q: float | None = None,
    ) -> bool:
        """Update one EQ band's parameters at runtime.

        Only the provided (non-None) parameters are changed; others
        remain at their current values.

        Args:
            node_id: The filter-chain sink node ID.
            band_index: 0-based band index (0–9).
            freq_hz: New center frequency in Hz.
            gain_db: New gain in dB (-24.0 to +24.0).
            q: New Q factor (0.1–10.0).

        Returns:
            True if the update was sent successfully.
        """
        payload = build_set_param_payload(band_index, freq_hz, gain_db, q)
        try:
            result = subprocess.run(
                [PW_CLI, "set-param", str(node_id), "Props", payload],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                logger.error("pw-cli set-param failed: %s", result.stderr.strip())
                return False
            return True
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.error("pw-cli set-param error: %s", exc)
            return False

    def update_all_bands(
        self,
        node_id: int,
        bands: list[dict],
    ) -> bool:
        """Update all 10 EQ bands in a single set-param call.

        Args:
            node_id: The filter-chain sink node ID.
            bands: List of 10 dicts, each with optional 'freq_hz', 'gain_db', 'q' keys.

        Returns:
            True if the update was sent successfully.
        """
        params = []
        for i, band in enumerate(bands):
            band_name = f"eq_band_{i + 1}"
            if "freq_hz" in band:
                params.extend([f"{band_name}:Freq", band["freq_hz"]])
            if "gain_db" in band:
                params.extend([f"{band_name}:Gain", band["gain_db"]])
            if "q" in band:
                params.extend([f"{band_name}:Q", band["q"]])

        payload = json.dumps({"params": params})
        try:
            result = subprocess.run(
                [PW_CLI, "set-param", str(node_id), "Props", payload],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False

    def enumerate_params(self, node_id: int) -> dict[str, dict[str, float]]:
        """Read all current EQ band parameters from a filter-chain node.

        Returns:
            Dict mapping band name ("eq_band_1", ...) to its param dict.
        """
        try:
            result = subprocess.run(
                [PW_CLI, "enum-params", str(node_id), "Props"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return {}
            return _parse_enum_params(result.stdout)
        except (subprocess.TimeoutExpired, OSError):
            return {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_for_node(self, node_name: str, timeout: float) -> int | None:
        """Poll pw-cli until a node with the given name appears.

        Returns the node ID, or None on timeout.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            node_id = _find_node_by_name(node_name)
            if node_id is not None:
                return node_id
            time.sleep(NODE_POLL_INTERVAL)
        return None


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _find_node_by_name(name: str) -> int | None:
    """Find a PipeWire node ID by node.name using pw-cli ls Node."""
    try:
        result = subprocess.run(
            [PW_CLI, "ls", "Node"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.splitlines()
        current_id = None
        for line in lines:
            # Match "id N, type ..."
            id_match = re.match(r"^\s*id\s+(\d+),", line)
            if id_match:
                current_id = int(id_match.group(1))
                continue
            # Match 'node.name = "something"'
            name_match = re.match(r'^\s*node\.name\s*=\s*"([^"]+)"', line)
            if name_match and name_match.group(1) == name and current_id is not None:
                return current_id
        return None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _parse_enum_params(output: str) -> dict[str, dict[str, float]]:
    """Parse pw-cli enum-params output into a structured dict.

    Extracts band parameters like eq_band_1:Freq, eq_band_1:Gain, etc.
    """
    bands: dict[str, dict[str, float]] = {}

    # The output is Spa:Pod format. We look for patterns like:
    #   String "eq_band_1:Freq"
    #   Float 100.000000
    pattern = re.compile(
        r'String\s+"(eq_band_\d+):(\w+)"\s*\n\s*Float\s+([-\d.]+)',
        re.MULTILINE,
    )

    for match in pattern.finditer(output):
        band_name = match.group(1)
        param_name = match.group(2)
        value = float(match.group(3))
        bands.setdefault(band_name, {})[param_name] = value

    return bands
