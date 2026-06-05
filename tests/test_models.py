"""Tests for core data models — EQBand, Channel, EQPreset."""

from peq_app.config import DEFAULT_BAND_FREQUENCIES, DEFAULT_BAND_TYPES, DEFAULT_Q
from peq_app.state.models import (
    BUILTIN_PRESETS,
    Channel,
    EQBand,
    EQPreset,
    _default_bands,
    master_channel,
)


class TestEQBand:
    """EQBand model creation, defaults, and serialization."""

    def test_default_creation(self) -> None:
        band = EQBand(freq_hz=1000.0)
        assert band.freq_hz == 1000.0
        assert band.gain_db == 0.0
        assert band.q == DEFAULT_Q
        assert band.filter_type == "peaking"
        assert band.enabled is True

    def test_full_creation(self) -> None:
        band = EQBand(freq_hz=500.0, gain_db=3.0, q=0.5, filter_type="lowshelf", enabled=False)
        assert band.freq_hz == 500.0
        assert band.gain_db == 3.0
        assert band.q == 0.5
        assert band.filter_type == "lowshelf"
        assert band.enabled is False

    def test_to_dict(self) -> None:
        band = EQBand(freq_hz=2000.0, gain_db=-2.0, q=1.0, filter_type="peaking")
        d = band.to_dict()
        assert d == {
            "freq_hz": 2000.0,
            "gain_db": -2.0,
            "q": 1.0,
            "filter_type": "peaking",
            "enabled": True,
        }

    def test_from_dict(self) -> None:
        d = {
            "freq_hz": 4000.0,
            "gain_db": 1.5,
            "q": 0.8,
            "filter_type": "highshelf",
            "enabled": False,
        }
        band = EQBand.from_dict(d)
        assert band.freq_hz == 4000.0
        assert band.gain_db == 1.5
        assert band.q == 0.8
        assert band.filter_type == "highshelf"
        assert band.enabled is False

    def test_from_dict_minimal(self) -> None:
        """from_dict fills defaults for missing fields."""
        band = EQBand.from_dict({"freq_hz": 8000.0})
        assert band.gain_db == 0.0
        assert band.q == DEFAULT_Q
        assert band.filter_type == "peaking"
        assert band.enabled is True

    def test_round_trip(self) -> None:
        """to_dict → from_dict should produce an equivalent band."""
        original = EQBand(freq_hz=250.0, gain_db=-4.5, q=0.4, filter_type="peaking", enabled=False)
        restored = EQBand.from_dict(original.to_dict())
        assert restored.freq_hz == original.freq_hz
        assert restored.gain_db == original.gain_db
        assert restored.q == original.q
        assert restored.filter_type == original.filter_type
        assert restored.enabled == original.enabled


class TestChannel:
    """Channel model creation, serialization, and helpers."""

    def test_master_channel(self) -> None:
        ch = master_channel()
        assert ch.id == "master"
        assert ch.name == "Master"
        assert ch.is_master is True
        assert len(ch.eq_bands) == 10

    def test_default_bands_count(self) -> None:
        bands = _default_bands()
        assert len(bands) == 10
        for i, band in enumerate(bands):
            assert band.freq_hz == DEFAULT_BAND_FREQUENCIES[i]
            assert band.filter_type == DEFAULT_BAND_TYPES[i]
            assert band.gain_db == 0.0

    def test_channel_to_dict(self) -> None:
        ch = Channel(
            id="test.app.123",
            name="Test App",
            volume=0.75,
            is_muted=True,
            app_binary="test_app",
        )
        d = ch.to_dict()
        assert d["id"] == "test.app.123"
        assert d["name"] == "Test App"
        assert d["volume"] == 0.75
        assert d["is_muted"] is True
        assert d["is_master"] is False
        assert d["app_binary"] == "test_app"
        assert len(d["eq_bands"]) == 10

    def test_channel_from_dict(self) -> None:
        d = {
            "id": "test.app.456",
            "name": "Restored App",
            "volume": 0.5,
            "is_muted": False,
            "is_master": False,
            "app_binary": "restored",
            "eq_bands": [
                {"freq_hz": 31, "gain_db": 1.0, "q": 0.5, "filter_type": "lowshelf"},
                {"freq_hz": 63, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"},
            ],
        }
        ch = Channel.from_dict(d)
        assert ch.id == "test.app.456"
        assert ch.name == "Restored App"
        assert ch.volume == 0.5
        assert ch.is_muted is False
        assert len(ch.eq_bands) == 2  # Explicit bands override default
        assert ch.eq_bands[0].gain_db == 1.0

    def test_channel_from_dict_no_bands(self) -> None:
        """Channels without stored bands fall back to 10-band defaults."""
        ch = Channel.from_dict({"id": "minimal", "name": "Min"})
        assert len(ch.eq_bands) == 10

    def test_channel_round_trip(self) -> None:
        original = Channel(
            id="round.trip.789",
            name="Round Trip",
            volume=0.33,
            is_muted=True,
            app_binary="roundtrip",
        )
        original.eq_bands[3].gain_db = 5.0
        restored = Channel.from_dict(original.to_dict())
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.volume == original.volume
        assert restored.is_muted == original.is_muted
        assert restored.app_binary == original.app_binary
        assert restored.eq_bands[3].gain_db == 5.0

    def test_is_eq_active(self) -> None:
        ch = Channel(id="test", name="Test")
        assert ch.is_eq_active is False
        ch.filter_pid = 12345
        ch.filter_node_id = 678
        assert ch.is_eq_active is True

    def test_band_params_for_engine(self) -> None:
        ch = Channel(id="test", name="Test")
        params = ch.band_params_for_engine()
        assert len(params) == 10
        for p in params:
            assert "freq_hz" in p
            assert "gain_db" in p
            assert "q" in p
            assert "filter_type" in p

    def test_user_volume_not_persisted(self) -> None:
        """user_volume is intentionally excluded from to_dict."""
        ch = Channel(id="test", name="Test", user_volume=0.5)
        d = ch.to_dict()
        assert "user_volume" not in d


class TestEQPreset:
    """EQPreset model and built-in presets."""

    def test_preset_creation(self) -> None:
        p = EQPreset(
            name="Test",
            bands=[{"freq_hz": 1000, "gain_db": 0.0, "q": 0.707, "filter_type": "peaking"}],
        )
        assert p.name == "Test"
        assert len(p.bands) == 1

    def test_preset_to_dict(self) -> None:
        p = EQPreset(
            name="Test",
            bands=[{"freq_hz": 500, "gain_db": 3.0, "q": 0.5, "filter_type": "peaking"}],
        )
        d = p.to_dict()
        assert d["name"] == "Test"
        assert len(d["bands"]) == 1

    def test_preset_from_dict(self) -> None:
        d = {
            "name": "Loaded",
            "bands": [{"freq_hz": 2000, "gain_db": -1.0, "q": 0.8, "filter_type": "peaking"}],
        }
        p = EQPreset.from_dict(d)
        assert p.name == "Loaded"
        assert p.bands[0]["gain_db"] == -1.0

    def test_preset_round_trip(self) -> None:
        original = EQPreset(
            name="Round",
            bands=[{"freq_hz": 100, "gain_db": 2.0, "q": 0.3, "filter_type": "peaking"}],
        )
        restored = EQPreset.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.bands == original.bands

    def test_builtin_presets_count(self) -> None:
        """We expect exactly 8 built-in presets."""
        assert len(BUILTIN_PRESETS) == 8

    def test_builtin_presets_unique_names(self) -> None:
        names = [p.name for p in BUILTIN_PRESETS]
        assert len(names) == len(set(names))

    def test_builtin_presets_each_has_10_bands(self) -> None:
        for preset in BUILTIN_PRESETS:
            assert len(preset.bands) == 10, f"Preset '{preset.name}' has {len(preset.bands)} bands"

    def test_flat_preset_all_zero(self) -> None:
        flat = [p for p in BUILTIN_PRESETS if p.name == "Flat"][0]
        for band in flat.bands:
            assert band["gain_db"] == 0.0, f"Flat preset has non-zero gain at {band['freq_hz']} Hz"
