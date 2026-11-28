import pytest

from dashboard import theme


def _relative_luminance(hex_color):
    channels = [
        int(hex_color[index : index + 2], 16) / 255
        for index in (1, 3, 5)
    ]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(foreground, background):
    luminances = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return (luminances[0] + 0.05) / (luminances[1] + 0.05)


def test_spacing_tokens_use_the_requested_scale_and_multiples_of_four():
    assert theme.SPACING_PX == (4, 8, 12, 16, 20, 24, 32, 40, 48, 64)
    assert all(value % 4 == 0 for value in theme.SPACING_PX)


@pytest.mark.parametrize(
    "foreground",
    [
        theme.TEXT_PRIMARY,
        theme.TEXT_SECONDARY,
        theme.TEXT_MUTED,
        theme.LINK_TEXT,
    ],
)
@pytest.mark.parametrize("background", [theme.SURFACE_PAGE, theme.SURFACE_CARD])
def test_text_tokens_meet_wcag_contrast_on_page_and_card(foreground, background):
    assert _contrast_ratio(foreground, background) >= 4.5


def test_dashboard_css_avoids_depth_and_all_property_transitions():
    css = theme.dashboard_css().casefold()

    for forbidden in ("gradient", "box-shadow", "animation", "transition: all"):
        assert forbidden not in css
