"""Tests for theme definitions — contrast ratios, color completeness, consistency."""

import re

from peq_app.ui_tui.app import THEME_ORDER, THEMES

# Required keys every theme must define
_REQUIRED_KEYS = {
    "name",
    "canvas",
    "surface",
    "surface_hover",
    "surface_selected",
    "border",
    "border_subtle",
    "text",
    "text_dim",
    "text_muted",
    "accent",
    "accent_dim",
    "danger",
    "danger_dim",
    "band_track",
    "band_neutral",
}


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert '#rrggbb' to (r, g, b) integers."""
    h = hex_str.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(hex_str: str) -> float:
    """WCAG 2.1 relative luminance from a hex colour."""
    r, g, b = _hex_to_rgb(hex_str)

    def _linear(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio between two hex colours."""
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestThemeDefinitions:
    """Verify theme structure and consistency."""

    def test_all_themes_in_order(self) -> None:
        assert THEME_ORDER == ["amber", "slate", "mono"]

    def test_each_theme_order_key_exists(self) -> None:
        for key in THEME_ORDER:
            assert key in THEMES, f"Theme '{key}' in THEME_ORDER but not in THEMES"

    def test_no_extra_themes(self) -> None:
        assert set(THEMES.keys()) == set(THEME_ORDER)

    def test_all_themes_have_required_keys(self) -> None:
        for theme_name, palette in THEMES.items():
            missing = _REQUIRED_KEYS - set(palette.keys())
            assert not missing, f"Theme '{theme_name}' missing keys: {missing}"

    def test_all_colors_are_valid_hex(self) -> None:
        hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
        for theme_name, palette in THEMES.items():
            for key, value in palette.items():
                if key == "name":
                    continue
                assert hex_re.match(value), (
                    f"Theme '{theme_name}' key '{key}' = '{value}' is not #rrggbb"
                )

    def test_theme_names_are_strings(self) -> None:
        for theme_name, palette in THEMES.items():
            assert isinstance(palette["name"], str)
            assert len(palette["name"]) > 0


class TestContrastRatios:
    """Verify WCAG AA 4.5:1 contrast minimums."""

    def test_text_on_canvas_meets_aa(self) -> None:
        """Main text must have ≥4.5:1 contrast on the canvas."""
        for theme_name, c in THEMES.items():
            ratio = contrast_ratio(c["text"], c["canvas"])
            assert ratio >= 4.5, (
                f"Theme '{theme_name}' text {c['text']} on canvas {c['canvas']} "
                f"has contrast {ratio:.2f}:1 (need ≥4.5:1)"
            )

    def test_text_muted_on_canvas_meets_aa(self) -> None:
        """Muted text must have ≥4.5:1 contrast on the canvas."""
        for theme_name, c in THEMES.items():
            ratio = contrast_ratio(c["text_muted"], c["canvas"])
            assert ratio >= 4.5, (
                f"Theme '{theme_name}' text_muted {c['text_muted']} on canvas {c['canvas']} "
                f"has contrast {ratio:.2f}:1 (need ≥4.5:1)"
            )

    def test_text_dim_on_canvas_meets_aa(self) -> None:
        """Dimmed text should have reasonable contrast on the canvas."""
        for theme_name, c in THEMES.items():
            ratio = contrast_ratio(c["text_dim"], c["canvas"])
            assert ratio >= 4.5, (
                f"Theme '{theme_name}' text_dim {c['text_dim']} on canvas {c['canvas']} "
                f"has contrast {ratio:.2f}:1 (need ≥4.5:1)"
            )

    def test_accent_on_canvas_has_minimum_contrast(self) -> None:
        """Accent must have ≥3:1 contrast on canvas (large-element minimum)."""
        for theme_name, c in THEMES.items():
            ratio = contrast_ratio(c["accent"], c["canvas"])
            assert ratio >= 3.0, (
                f"Theme '{theme_name}' accent {c['accent']} on canvas {c['canvas']} "
                f"has contrast {ratio:.2f}:1 (need ≥3:1)"
            )

    def test_danger_on_canvas_has_minimum_contrast(self) -> None:
        """Danger/mute red must be perceptible on canvas."""
        for theme_name, c in THEMES.items():
            ratio = contrast_ratio(c["danger"], c["canvas"])
            assert ratio >= 3.0, (
                f"Theme '{theme_name}' danger {c['danger']} on canvas {c['canvas']} "
                f"has contrast {ratio:.2f}:1 (need ≥3:1)"
            )

    def test_text_on_surface_meets_aa(self) -> None:
        """Text on surface (headers, footer) should meet AA."""
        for theme_name, c in THEMES.items():
            ratio = contrast_ratio(c["text"], c["surface"])
            assert ratio >= 4.5, (
                f"Theme '{theme_name}' text on surface has contrast {ratio:.2f}:1"
            )


class TestThemeConsistency:
    """Check internal consistency of the theme system."""

    def test_accent_dim_is_darker_than_accent(self) -> None:
        for theme_name, c in THEMES.items():
            acc_lum = _relative_luminance(c["accent"])
            dim_lum = _relative_luminance(c["accent_dim"])
            assert dim_lum < acc_lum, (
                f"Theme '{theme_name}' accent_dim {c['accent_dim']} should be darker than accent {c['accent']}"
            )

    def test_danger_dim_is_darker_than_danger(self) -> None:
        for theme_name, c in THEMES.items():
            dang_lum = _relative_luminance(c["danger"])
            dim_lum = _relative_luminance(c["danger_dim"])
            assert dim_lum < dang_lum, (
                f"Theme '{theme_name}' danger_dim should be darker than danger"
            )

    def test_surface_is_lighter_than_canvas(self) -> None:
        for theme_name, c in THEMES.items():
            surf_lum = _relative_luminance(c["surface"])
            canv_lum = _relative_luminance(c["canvas"])
            assert surf_lum > canv_lum, (
                f"Theme '{theme_name}' surface should be lighter than canvas"
            )

    def test_text_is_lightest(self) -> None:
        """Text should be the lightest key except possibly highlighted states."""
        for theme_name, c in THEMES.items():
            text_lum = _relative_luminance(c["text"])
            assert text_lum > _relative_luminance(c["text_dim"])
            assert text_lum > _relative_luminance(c["text_muted"])
