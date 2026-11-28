"""Fixed design tokens and shared Streamlit styling for the dashboard."""

from __future__ import annotations

import streamlit as st


SPACE_4_PX = 4
SPACE_8_PX = 8
SPACE_12_PX = 12
SPACE_16_PX = 16
SPACE_20_PX = 20
SPACE_24_PX = 24
SPACE_32_PX = 32
SPACE_40_PX = 40
SPACE_48_PX = 48
SPACE_64_PX = 64
SPACING_PX = (
    SPACE_4_PX,
    SPACE_8_PX,
    SPACE_12_PX,
    SPACE_16_PX,
    SPACE_20_PX,
    SPACE_24_PX,
    SPACE_32_PX,
    SPACE_40_PX,
    SPACE_48_PX,
    SPACE_64_PX,
)

SURFACE_SIDEBAR = "#0f0f10"
SURFACE_PAGE = "#141415"
SURFACE_CARD = "#19191b"
SURFACE_RAISED = "#232325"
HAIRLINE_COLOR = "rgba(237,237,237,0.08)"

TEXT_PRIMARY = "#ededed"
TEXT_SECONDARY = "#a1a1a6"
TEXT_MUTED = "#85858b"
ACCENT_FILL = "#2563EB"
LINK_TEXT = "#60A5FA"
CHART_NEUTRAL_COLOR = "#66666d"
POSITIVE_COLOR = "#4cc38a"
NEGATIVE_COLOR = "#e5484d"
CHART_ACCENT_COLOR = ACCENT_FILL
CHART_COLORS = (CHART_ACCENT_COLOR, CHART_NEUTRAL_COLOR)

CONTROL_RADIUS_RANGE_PX = (8, 10)
CARD_RADIUS_RANGE_PX = (12, 16)
CONTROL_RADIUS_PX = CONTROL_RADIUS_RANGE_PX[0]
CARD_RADIUS_PX = CARD_RADIUS_RANGE_PX[0]

TYPE_SIZES_PX = (12, 14, 16, 20, 28)
FONT_WEIGHTS = (400, 500)
TYPE_SIZE_CAPTION_PX = TYPE_SIZES_PX[0]
TYPE_SIZE_BODY_PX = TYPE_SIZES_PX[1]
TYPE_SIZE_HEADING_3_PX = TYPE_SIZES_PX[2]
TYPE_SIZE_HEADING_2_PX = TYPE_SIZES_PX[3]
TYPE_SIZE_DISPLAY_PX = TYPE_SIZES_PX[4]
FONT_WEIGHT_REGULAR = FONT_WEIGHTS[0]
FONT_WEIGHT_MEDIUM = FONT_WEIGHTS[1]
SMALL_TEXT_LETTER_SPACING_PX = 0
FONT_STACK = "sans-serif"

MOTION_EASING = "cubic-bezier(0.22, 1, 0.36, 1)"
HOVER_TRANSITION_MS = 150

PAGE_SIDE_PADDING_PX = SPACE_32_PX
PAGE_MAX_WIDTH_PX = 1440
SECTION_GAP_PX = SPACE_32_PX
INNER_SECTION_GAP_PX = SPACE_16_PX
CARD_PADDING_PX = (SPACE_20_PX, SPACE_24_PX)
SIDEBAR_ROW_HEIGHT_PX = (32, 36)
SIDEBAR_ROW_GAP_PX = (2, 4)
SIDEBAR_CONTROL_HEIGHT_PX = sum(SIDEBAR_ROW_HEIGHT_PX) // 2
SIDEBAR_GAP_PX = sum(SIDEBAR_ROW_GAP_PX) // 2
HAIRLINE_WIDTH_PX = 1
FOCUS_RING_WIDTH_PX = 2


def dashboard_css() -> str:
    """Return the shared, restrained dashboard CSS."""
    return f"""<style>
:root {{
  --surface-sidebar: {SURFACE_SIDEBAR};
  --surface-page: {SURFACE_PAGE};
  --surface-card: {SURFACE_CARD};
  --surface-raised: {SURFACE_RAISED};
  --hairline: {HAIRLINE_COLOR};
  --text-primary: {TEXT_PRIMARY};
  --text-secondary: {TEXT_SECONDARY};
  --text-muted: {TEXT_MUTED};
  --accent-fill: {ACCENT_FILL};
  --link-text: {LINK_TEXT};
  --chart-neutral: {CHART_NEUTRAL_COLOR};
  --positive: {POSITIVE_COLOR};
  --negative: {NEGATIVE_COLOR};
}}

body, [data-testid="stAppViewContainer"] {{
  background-color: var(--surface-page);
  color: var(--text-primary);
  font-family: {FONT_STACK};
  font-size: {TYPE_SIZE_BODY_PX}px;
  font-weight: {FONT_WEIGHT_REGULAR};
  letter-spacing: {SMALL_TEXT_LETTER_SPACING_PX}px;
}}

.main .block-container {{
  max-width: {PAGE_MAX_WIDTH_PX}px;
  padding-left: {PAGE_SIDE_PADDING_PX}px;
  padding-right: {PAGE_SIDE_PADDING_PX}px;
}}

.main .block-container > div[data-testid="stVerticalBlock"] {{
  gap: {SECTION_GAP_PX}px;
}}

[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] {{
  gap: {INNER_SECTION_GAP_PX}px;
}}

h1, h2, h3, h4, [data-testid="stHeading"] {{
  font-weight: {FONT_WEIGHT_MEDIUM};
  letter-spacing: 0;
  text-transform: none;
}}

h1 {{ font-size: {TYPE_SIZE_DISPLAY_PX}px; }}
h2 {{ font-size: {TYPE_SIZE_HEADING_2_PX}px; }}
h3 {{ font-size: {TYPE_SIZE_HEADING_3_PX}px; }}
h4 {{ font-size: {TYPE_SIZE_BODY_PX}px; }}

[data-testid="stMetric"] {{
  background-color: var(--surface-card);
  border: {HAIRLINE_WIDTH_PX}px solid var(--hairline);
  border-radius: {CARD_RADIUS_PX}px;
  padding: {CARD_PADDING_PX[0]}px {CARD_PADDING_PX[1]}px;
}}

[data-testid="stMetricLabel"] p {{
  color: var(--text-secondary);
  font-size: {TYPE_SIZE_CAPTION_PX}px;
  font-weight: {FONT_WEIGHT_REGULAR};
  letter-spacing: 0;
  text-transform: none;
}}

[data-testid="stMetricValue"] {{
  color: var(--text-primary);
  font-size: {TYPE_SIZE_DISPLAY_PX}px;
  font-weight: {FONT_WEIGHT_MEDIUM};
  font-variant-numeric: tabular-nums;
}}

[data-testid="stCaptionContainer"] p {{
  color: var(--text-muted);
  font-size: {TYPE_SIZE_CAPTION_PX}px;
  font-weight: {FONT_WEIGHT_REGULAR};
  letter-spacing: 0;
}}

.sample-tag {{
  color: var(--text-muted);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: {TYPE_SIZE_CAPTION_PX}px;
  font-weight: {FONT_WEIGHT_REGULAR};
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  text-align: right;
  white-space: nowrap;
  padding-bottom: {SPACE_4_PX}px;
}}

[data-testid="stVerticalBlockBorderWrapper"] {{
  background-color: var(--surface-card);
  border-color: var(--hairline);
  border-radius: {CARD_RADIUS_PX}px;
  padding: {CARD_PADDING_PX[0]}px {CARD_PADDING_PX[1]}px;
}}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
  gap: {SIDEBAR_GAP_PX}px;
}}

[data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{
  min-height: {SIDEBAR_CONTROL_HEIGHT_PX}px;
  display: flex;
  align-items: center;
}}

[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div,
[data-testid="stSidebar"] input {{
  min-height: {SIDEBAR_CONTROL_HEIGHT_PX}px;
  background-color: var(--surface-raised);
  border-color: var(--hairline);
  border-radius: {CONTROL_RADIUS_PX}px;
}}

[data-testid="stSidebar"] div[role="radiogroup"] {{
  gap: {SIDEBAR_GAP_PX}px;
}}

[data-testid="stDataFrame"] {{
  border: {HAIRLINE_WIDTH_PX}px solid var(--hairline);
  border-radius: {CARD_RADIUS_PX}px;
}}

[data-testid="stDataFrame"] [role="gridcell"],
[data-testid="stDataFrame"] [role="columnheader"] {{
  font-variant-numeric: tabular-nums;
}}

a, a:visited {{
  color: var(--link-text);
}}

a:hover {{
  color: var(--text-primary);
}}

:focus-visible {{
  outline: {FOCUS_RING_WIDTH_PX}px solid var(--link-text);
  outline-offset: {SPACE_4_PX // 2}px;
}}

label, button, input, textarea, [role="option"] {{
  text-transform: none;
}}

a, button, input, textarea, [role="combobox"], [role="radio"], [role="option"] {{
  transition:
    color {HOVER_TRANSITION_MS}ms {MOTION_EASING},
    background-color {HOVER_TRANSITION_MS}ms {MOTION_EASING},
    border-color {HOVER_TRANSITION_MS}ms {MOTION_EASING},
    opacity {HOVER_TRANSITION_MS}ms {MOTION_EASING},
    transform {HOVER_TRANSITION_MS}ms {MOTION_EASING};
}}
</style>"""


def render_chart_heading(title: str, sample_size: int) -> None:
    """Render a chart title with a right-aligned sample-size tag."""
    title_column, sample_column = st.columns([6, 1], vertical_alignment="bottom")
    title_column.subheader(title)
    sample_column.markdown(
        f'<div class="sample-tag">n = {int(sample_size):,}</div>',
        unsafe_allow_html=True,
    )
