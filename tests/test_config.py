"""Tests for configuration constants."""

from pathlib import Path

from peq_app import config


class TestEQDefaults:
    """EQ band configuration constants are sensible."""

    def test_band_frequencies_count(self) -> None:
        assert len(config.DEFAULT_BAND_FREQUENCIES) == 10

    def test_band_types_count_matches_frequencies(self) -> None:
        assert len(config.DEFAULT_BAND_TYPES) == len(config.DEFAULT_BAND_FREQUENCIES)

    def test_frequencies_increasing(self) -> None:
        freqs = config.DEFAULT_BAND_FREQUENCIES
        for i in range(len(freqs) - 1):
            assert freqs[i] < freqs[i + 1], f"{freqs[i]} should be < {freqs[i + 1]}"

    def test_frequencies_are_positive(self) -> None:
        for f in config.DEFAULT_BAND_FREQUENCIES:
            assert f > 0

    def test_band_types_are_valid(self) -> None:
        valid = {"peaking", "lowshelf", "highshelf"}
        for t in config.DEFAULT_BAND_TYPES:
            assert t in valid, f"'{t}' is not a valid filter type"

    def test_first_band_is_lowshelf(self) -> None:
        assert config.DEFAULT_BAND_TYPES[0] == "lowshelf"

    def test_last_band_is_highshelf(self) -> None:
        assert config.DEFAULT_BAND_TYPES[-1] == "highshelf"

    def test_default_q_is_valid(self) -> None:
        assert config.DEFAULT_Q > 0
        assert config.DEFAULT_Q <= config.Q_MAX
        assert config.DEFAULT_Q >= config.Q_MIN

    def test_gain_limits_symmetric(self) -> None:
        assert config.GAIN_MIN_DB == -config.GAIN_MAX_DB

    def test_q_limits_positive(self) -> None:
        assert config.Q_MIN > 0
        assert config.Q_MAX > config.Q_MIN

    def test_scan_interval_positive(self) -> None:
        assert config.SCAN_INTERVAL > 0


class TestAppConstants:
    """Application name, paths, and binaries."""

    def test_app_name(self) -> None:
        assert config.APP_NAME == "peq"

    def test_config_dir_is_path(self) -> None:
        assert isinstance(config.CONFIG_DIR, Path)
        assert config.APP_NAME in str(config.CONFIG_DIR)

    def test_state_dir_is_under_config(self) -> None:
        assert str(config.STATE_DIR).startswith(str(config.CONFIG_DIR))

    def test_filter_chain_dir_is_under_config(self) -> None:
        assert str(config.FILTER_CHAIN_DIR).startswith(str(config.CONFIG_DIR))

    def test_pw_cli_is_present(self) -> None:
        assert isinstance(config.PW_CLI, str)
        assert len(config.PW_CLI) > 0

    def test_ignored_binaries_contains_sd_dummy(self) -> None:
        assert "sd_dummy" in config.IGNORED_BINARIES


class TestEnsureDirs:
    """ensure_dirs creates required directories."""

    def test_ensure_dirs_creates_directories(self, tmp_path: Path) -> None:
        import peq_app.config as cfg

        orig_config = cfg.XDG_CONFIG_HOME
        try:
            cfg.XDG_CONFIG_HOME = tmp_path
            cfg.CONFIG_DIR = tmp_path / cfg.APP_NAME
            cfg.FILTER_CHAIN_DIR = cfg.CONFIG_DIR / "filter-chains"
            cfg.STATE_DIR = cfg.CONFIG_DIR / "state"
            cfg.PIPEWIRE_CONFIG_DIR = tmp_path / "pipewire" / "filter-chain.conf.d"

            cfg.ensure_dirs()
            assert cfg.FILTER_CHAIN_DIR.exists()
            assert cfg.STATE_DIR.exists()
            assert cfg.PIPEWIRE_CONFIG_DIR.exists()
        finally:
            cfg.XDG_CONFIG_HOME = orig_config
