"""Tests for AppState — mutations, observer pattern, dirty flag, persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from peq_app.config import GAIN_MAX_DB, GAIN_MIN_DB
from peq_app.state.app_state import AppState
from peq_app.state.models import (
    BUILTIN_PRESETS,
    Channel,
    EQBand,
    EQPreset,
    master_channel,
)


def _fresh_state() -> AppState:
    """Return a reset AppState singleton for testing.

    Since AppState is a singleton we need to clear instance data between tests.
    """
    # Force a fresh singleton
    AppState._instance = None  # type: ignore[attr-defined]
    state = AppState()
    return state


class TestAppStateInit:
    """AppState initialization."""

    def test_singleton(self) -> None:
        s1 = _fresh_state()
        s2 = AppState()
        assert s1 is s2

    def test_master_channel_present(self) -> None:
        state = _fresh_state()
        assert "master" in state.channels
        assert state.channels["master"].is_master is True
        assert state.selected_channel_id == "master"

    def test_is_dirty_initially_true(self) -> None:
        state = _fresh_state()
        # After _init_master, no notification has fired.
        # The dirty flag starts True so initial refresh works.
        assert state.is_dirty is True


class TestChannelManagement:
    """Adding, removing, syncing channels."""

    @pytest.mark.asyncio
    async def test_add_channel(self) -> None:
        state = _fresh_state()
        ch = Channel(id="test.add", name="Test Add", volume=0.8, app_binary="test")
        await state.add_channel(ch)
        assert "test.add" in state.channels
        assert state.channels["test.add"].volume == 0.8

    @pytest.mark.asyncio
    async def test_add_duplicate_channel_updates(self) -> None:
        state = _fresh_state()
        ch1 = Channel(id="test.dup", name="First", volume=0.5, app_binary="test")
        await state.add_channel(ch1)
        ch2 = Channel(id="test.dup", name="Second", volume=0.9, app_binary="test")
        await state.add_channel(ch2)
        assert state.channels["test.dup"].name == "Second"
        assert state.channels["test.dup"].volume == 0.9

    @pytest.mark.asyncio
    async def test_remove_channel(self) -> None:
        state = _fresh_state()
        ch = Channel(id="test.remove", name="Remove Me", app_binary="test")
        await state.add_channel(ch)
        assert "test.remove" in state.channels
        await state.remove_channel("test.remove")
        assert "test.remove" not in state.channels

    @pytest.mark.asyncio
    async def test_remove_channel_reselects_master(self) -> None:
        state = _fresh_state()
        ch = Channel(id="test.reselect", name="Reselect", app_binary="test")
        await state.add_channel(ch)
        await state.select_channel("test.reselect")
        assert state.selected_channel_id == "test.reselect"
        await state.remove_channel("test.reselect")
        assert state.selected_channel_id == "master"

    @pytest.mark.asyncio
    async def test_select_channel(self) -> None:
        state = _fresh_state()
        ch = Channel(id="test.select", name="Select Me", app_binary="test")
        await state.add_channel(ch)
        await state.select_channel("test.select")
        assert state.selected_channel_id == "test.select"
        assert state.selected_channel is state.channels["test.select"]

    @pytest.mark.asyncio
    async def test_select_nonexistent_channel_noop(self) -> None:
        state = _fresh_state()
        await state.select_channel("nonexistent")
        assert state.selected_channel_id == "master"

    @pytest.mark.asyncio
    async def test_sync_channels_removes_stale(self) -> None:
        state = _fresh_state()
        ch = Channel(id="test.stale", name="Stale", app_binary="test")
        await state.add_channel(ch)
        assert "test.stale" in state.channels
        await state.sync_channels(set())  # No apps running
        assert "test.stale" not in state.channels

    @pytest.mark.asyncio
    async def test_sync_channels_keeps_current(self) -> None:
        state = _fresh_state()
        ch = Channel(id="test.current", name="Current", app_binary="test")
        await state.add_channel(ch)
        await state.sync_channels({"test.current"})
        assert "test.current" in state.channels


class TestVolume:
    """Volume and mute mutations."""

    @pytest.mark.asyncio
    async def test_set_volume_clamps_low(self) -> None:
        state = _fresh_state()
        await state.set_volume("master", -0.5)
        assert state.channels["master"].volume == 0.0

    @pytest.mark.asyncio
    async def test_set_volume_clamps_high(self) -> None:
        state = _fresh_state()
        await state.set_volume("master", 1.5)
        assert state.channels["master"].volume == 1.0

    @pytest.mark.asyncio
    async def test_set_volume_records_user_intent(self) -> None:
        state = _fresh_state()
        await state.set_volume("master", 0.42)
        assert state.channels["master"].user_volume == 0.42

    @pytest.mark.asyncio
    async def test_set_volume_nonexistent_channel_noop(self) -> None:
        state = _fresh_state()
        await state.set_volume("nonexistent", 0.5)  # Should not raise

    @pytest.mark.asyncio
    async def test_toggle_mute(self) -> None:
        state = _fresh_state()
        assert state.channels["master"].is_muted is False
        await state.toggle_mute("master")
        assert state.channels["master"].is_muted is True
        await state.toggle_mute("master")
        assert state.channels["master"].is_muted is False

    @pytest.mark.asyncio
    async def test_set_mute(self) -> None:
        state = _fresh_state()
        await state.set_mute("master", True)
        assert state.channels["master"].is_muted is True

    @pytest.mark.asyncio
    async def test_sync_volume_from_hardware_accepts_initial(self) -> None:
        """When user hasn't set volume yet, accept hardware value."""
        state = _fresh_state()
        # Master starts at 1.0 with no user_volume
        await state.sync_volume_from_hardware("master", 0.75)
        assert state.channels["master"].volume == 0.75

    @pytest.mark.asyncio
    async def test_sync_volume_from_hardware_reasserts_user(self) -> None:
        """When user has set volume, re-assert it against hardware."""
        state = _fresh_state()
        await state.set_volume("master", 0.5)
        await state.sync_volume_from_hardware("master", 0.9)
        # User's 0.5 should be re-asserted
        assert state.channels["master"].volume == 0.5


class TestEQBands:
    """EQ band mutations."""

    @pytest.mark.asyncio
    async def test_set_band_gain(self) -> None:
        state = _fresh_state()
        await state.set_band("master", 0, gain_db=5.0)
        assert state.channels["master"].eq_bands[0].gain_db == 5.0

    @pytest.mark.asyncio
    async def test_set_band_gain_clamps(self) -> None:
        state = _fresh_state()
        await state.set_band("master", 0, gain_db=100.0)
        assert state.channels["master"].eq_bands[0].gain_db == GAIN_MAX_DB
        await state.set_band("master", 0, gain_db=-100.0)
        assert state.channels["master"].eq_bands[0].gain_db == GAIN_MIN_DB

    @pytest.mark.asyncio
    async def test_set_band_clamps_q(self) -> None:
        state = _fresh_state()
        await state.set_band("master", 0, q=100.0)
        assert state.channels["master"].eq_bands[0].q == 10.0
        await state.set_band("master", 0, q=-5.0)
        assert state.channels["master"].eq_bands[0].q == 0.1

    @pytest.mark.asyncio
    async def test_set_band_out_of_range_noop(self) -> None:
        state = _fresh_state()
        await state.set_band("master", 999, gain_db=99.0)  # Should not raise

    @pytest.mark.asyncio
    async def test_set_all_bands(self) -> None:
        state = _fresh_state()
        bands = [
            {"freq_hz": 31, "gain_db": 0.0, "q": 0.707, "filter_type": "lowshelf"},
            {"freq_hz": 63, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
            {"freq_hz": 125, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
            {"freq_hz": 250, "gain_db": 3.0, "q": 0.707, "filter_type": "peaking"},
            {"freq_hz": 500, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
            {"freq_hz": 1000, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
            {"freq_hz": 2000, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
            {"freq_hz": 4000, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
            {"freq_hz": 8000, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
            {"freq_hz": 16000, "gain_db": 0.0, "q": 0.707, "filter_type": "highshelf"},
        ]
        await state.set_all_bands("master", bands)
        assert state.channels["master"].eq_bands[3].gain_db == 3.0

    @pytest.mark.asyncio
    async def test_apply_preset(self) -> None:
        state = _fresh_state()
        preset = BUILTIN_PRESETS[1]  # Bass Boost
        await state.apply_preset("master", preset)
        assert state.channels["master"].eq_bands[0].gain_db == 6.0  # 31 Hz

    @pytest.mark.asyncio
    async def test_apply_preset_nonexistent_noop(self) -> None:
        state = _fresh_state()
        preset = BUILTIN_PRESETS[0]
        await state.apply_preset("nonexistent", preset)  # Should not raise


class TestObserverPattern:
    """Observer notifications fire correctly."""

    @pytest.mark.asyncio
    async def test_observer_notified_on_channel_add(self) -> None:
        state = _fresh_state()
        events: list[tuple[str, object]] = []

        async def cb(event: str, data: object) -> None:
            events.append((event, data))

        state.observe(cb)
        ch = Channel(id="test.obs", name="Obs", app_binary="test")
        await state.add_channel(ch)
        assert len(events) >= 1
        assert events[0][0] == "channels_updated"

    @pytest.mark.asyncio
    async def test_observer_notified_on_volume_change(self) -> None:
        state = _fresh_state()
        events: list[tuple[str, object]] = []

        async def cb(event: str, data: object) -> None:
            events.append((event, data))

        state.observe(cb)
        await state.set_volume("master", 0.5)
        vol_events = [e for e in events if e[0] == "volume_changed"]
        assert len(vol_events) >= 1
        assert vol_events[0][1] == {"channel_id": "master", "volume": 0.5}

    @pytest.mark.asyncio
    async def test_observer_notified_on_channel_selection(self) -> None:
        state = _fresh_state()
        events: list[tuple[str, object]] = []

        async def cb(event: str, data: object) -> None:
            events.append((event, data))

        state.observe(cb)
        await state.select_channel("master")
        sel_events = [e for e in events if e[0] == "channel_selected"]
        assert len(sel_events) >= 1

    @pytest.mark.asyncio
    async def test_unobserve_stops_notifications(self) -> None:
        state = _fresh_state()
        events: list[tuple[str, object]] = []

        async def cb(event: str, data: object) -> None:
            events.append((event, data))

        state.observe(cb)
        await state.set_volume("master", 0.1)
        assert len(events) >= 1
        state.unobserve(cb)
        events.clear()
        await state.set_volume("master", 0.9)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_observer_exception_does_not_prevent_others(self) -> None:
        state = _fresh_state()
        good_events: list[str] = []

        async def bad_cb(event: str, data: object) -> None:
            raise RuntimeError("observer error")

        async def good_cb(event: str, data: object) -> None:
            good_events.append(event)

        state.observe(bad_cb)
        state.observe(good_cb)
        await state.set_volume("master", 0.5)
        assert "volume_changed" in good_events


class TestDirtyFlag:
    """Dirty flag is set on mutation, cleared explicitly."""

    @pytest.mark.asyncio
    async def test_dirty_set_on_mutation(self) -> None:
        state = _fresh_state()
        state.clear_dirty()
        assert state.is_dirty is False
        await state.set_volume("master", 0.5)
        assert state.is_dirty is True

    @pytest.mark.asyncio
    async def test_clear_dirty(self) -> None:
        state = _fresh_state()
        state.clear_dirty()
        assert state.is_dirty is False

    @pytest.mark.asyncio
    async def test_dirty_set_on_channel_select(self) -> None:
        state = _fresh_state()
        state.clear_dirty()
        await state.select_channel("master")
        assert state.is_dirty is True


class TestPersistence:
    """State save/load round-trips."""

    def test_save_and_load_round_trip(self) -> None:
        state = _fresh_state()
        # Set up some test channels
        state.channels["test.save"] = Channel(
            id="test.save",
            name="Saved App",
            volume=0.6,
            is_muted=True,
            app_binary="save_test",
        )
        state.channels["test.save"].eq_bands[2].gain_db = 4.0

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir)
            with mock.patch("peq_app.state.app_state.STATE_DIR", state_path):
                state.save_state()
                assert (state_path / "state.json").exists()

                # Create a fresh state and load
                AppState._instance = None  # type: ignore[attr-defined]
                new_state = AppState()
                with mock.patch("peq_app.state.app_state.STATE_DIR", state_path):
                    new_state.load_state()
                assert "test.save" in new_state.channels
                assert new_state.channels["test.save"].volume == 0.6
                assert new_state.channels["test.save"].is_muted is True
                assert new_state.channels["test.save"].eq_bands[2].gain_db == 4.0

    def test_load_state_no_file(self) -> None:
        state = _fresh_state()
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir)
            with mock.patch("peq_app.state.app_state.STATE_DIR", state_path):
                state.load_state()  # Should not raise
        # Master should still be present
        assert "master" in state.channels

    def test_save_state_file_error_handled(self) -> None:
        state = _fresh_state()
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir) / "state"
            state_dir.mkdir()
            # Make state.json a directory so write_text fails with IsADirectoryError
            (state_dir / "state.json").mkdir()
            with mock.patch("peq_app.state.app_state.STATE_DIR", state_dir):
                state.save_state()  # Should not raise — OSError is caught


class TestEQChainLifecycle:
    """EQ filter-chain lifecycle tracking."""

    @pytest.mark.asyncio
    async def test_set_eq_chain_created(self) -> None:
        state = _fresh_state()
        await state.set_eq_chain_created("master", filter_pid=12345, filter_node_id=678)
        assert state.channels["master"].filter_pid == 12345
        assert state.channels["master"].filter_node_id == 678

    @pytest.mark.asyncio
    async def test_set_eq_chain_destroyed(self) -> None:
        state = _fresh_state()
        state.channels["master"].filter_pid = 12345
        state.channels["master"].filter_node_id = 678
        await state.set_eq_chain_destroyed("master")
        assert state.channels["master"].filter_pid is None
        assert state.channels["master"].filter_node_id is None


class TestPresets:
    """Preset accessor."""

    def test_presets_returns_builtins(self) -> None:
        state = _fresh_state()
        assert len(state.presets) == len(BUILTIN_PRESETS)
        assert state.presets is not BUILTIN_PRESETS  # Returns a copy
