"""
Tray Icon
==========

Renders the system tray icon.  Font loading and theme detection live in
:mod:`usage_monitor_for_claude.platforms`; this module stays purely
about drawing.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .platforms import load_font
from .settings import ICON_DARK, ICON_LIGHT, ICON_STYLE

__all__ = ['ZERO_STATE_GLYPH', 'create_icon_image', 'create_status_image']

ZERO_STATE_GLYPH = '>_'

TRANSPARENT = (0, 0, 0, 0)

# Icon canvas and bar geometry (pixels)
ICON_SIZE = 64
BAR_HEIGHT = 9
BAR_GAP = 3
MARKER_WIDTH = 4

# Row height for the 'numbers' icon style - two rows split the canvas evenly.
NUMBER_ROW_HEIGHT = 32


def create_icon_image(
    pct_top: float | None, pct_bottom: float | None, light_taskbar: bool = False,
    *, mode_top: str = 'utilization', mode_bottom: str = 'utilization',
    time_pct_top: float | None = None, time_pct_bottom: float | None = None,
    extra_usage_available: bool = False, bar_count: int = 2,
) -> Image.Image:
    """Create a Codex prompt/usage glyph with the available quota bars.

    With ``ICON_STYLE`` set to ``'numbers'`` the icon instead shows the two
    utilization percentages as stacked rows without bars; the mode and
    elapsed-time parameters have no effect in that style.

    Parameters
    ----------
    pct_top : float or None
        Utilization percentage (0-100) for the upper bar, or None if absent.
    pct_bottom : float or None
        Utilization percentage (0-100) for the lower bar, or None if absent.
    light_taskbar : bool
        Use dark-on-light colors for a light taskbar.
    mode_top : str
        Display mode for the upper bar: ``'utilization'`` (linear fill)
        or ``'overage'`` (fills as usage exceeds the time marker).
    mode_bottom : str
        Display mode for the lower bar.  Same semantics as *mode_top*.
    time_pct_top : float or None
        Elapsed-time percentage for the upper bar.  Draws the reset-time
        marker in ``utilization`` mode; required for ``overage`` mode.
    time_pct_bottom : float or None
        Elapsed-time percentage for the lower bar.  Same semantics as
        *time_pct_top*.
    extra_usage_available : bool
        True if the account has paid extra-usage credits still available.
        When a quota is fully exhausted, this decides whether to show ``$``
        (continuing costs money) or ``✕`` (fully blocked).
    bar_count : int
        Number of available quotas to draw, clamped from zero to two.
        A single quota is centered in the normal two-bar area.
    """
    colors = ICON_DARK if light_taskbar else ICON_LIGHT
    fg, fg_half, fg_warn = colors['fg'], colors['fg_half'], colors['fg_warn']

    S = ICON_SIZE
    img = Image.new('RGBA', (S, S), TRANSPARENT)
    draw = ImageDraw.Draw(img)

    available = []
    if pct_top is not None:
        available.append((pct_top, mode_top, time_pct_top))
    if pct_bottom is not None:
        available.append((pct_bottom, mode_bottom, time_pct_bottom))
    available = available[:max(0, min(2, bar_count))]
    primary_pct = available[0][0] if available else 0.0
    all_exhausted = bool(available) and all(entry[0] >= 100 for entry in available)
    all_zero = not available or all(entry[0] <= 0 for entry in available)

    if ICON_STYLE == 'numbers':
        # Two states collapse both rows into one full-size glyph: idle shows
        # the single Codex prompt, and both quotas exhausted shows one large '✕'/'$' -
        # extra_usage_available applies account-wide, so the two rows would
        # only repeat the same symbol twice at half size.
        if all_exhausted and not extra_usage_available:
            _draw_centered_text(draw, '\u2715', load_font(36, symbol=True), 2, fg)
        elif all_exhausted:
            _draw_centered_text(draw, '$', load_font(42), 2, fg)
        elif all_zero:
            _draw_centered_text(draw, ZERO_STATE_GLYPH, load_font(36), 0, fg)
        elif len(available) == 1:
            _draw_centered_text(draw, f'{min(primary_pct, 99):.0f}', load_font(40), 0, fg)
        else:
            _draw_number_row(draw, 0, pct_top, extra_usage_available, fg)
            _draw_number_row(draw, NUMBER_ROW_HEIGHT, pct_bottom, extra_usage_available, fg)
        return img

    # Top glyph: "✕" when any quota exhausted and no extra credits left,
    # "$" when exhausted but paid extra-usage still available,
    # Codex prompt while usage is still zero, otherwise the percentage.
    stroke_width = 0
    any_exhausted = any(entry[0] >= 100 for entry in available)
    if any_exhausted and not extra_usage_available:
        text, font = '\u2715', load_font(36, symbol=True)
        stroke_width = 2
    elif any_exhausted:
        text, font = '$', load_font(42)
        stroke_width = 2
    elif primary_pct > 0:
        # Clamp to 99: values in [99.5, 100) would round to a three-digit
        # '100' that overflows the canvas and reads as exhausted.
        text, font = f'{min(primary_pct, 99):.0f}', load_font(40)
    else:
        text, font = ZERO_STATE_GLYPH, load_font(36)

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw = bbox[2] - bbox[0]
    draw.text(((S - tw) / 2 - bbox[0], -bbox[1]), text, fill=fg, font=font, stroke_width=stroke_width, stroke_fill=fg)

    # Progress bars - full width, flush to bottom
    bar2_y = S - BAR_HEIGHT
    bar1_y = bar2_y - BAR_GAP - BAR_HEIGHT

    if len(available) == 1:
        pct, mode, time_pct = available[0]
        y = bar2_y - (BAR_HEIGHT + BAR_GAP) // 2
        _draw_usage_bar(draw, y, pct, mode, time_pct, fg, fg_half, fg_warn)
    elif len(available) == 2:
        _draw_usage_bar(draw, bar1_y, pct_top, mode_top, time_pct_top, fg, fg_half, fg_warn)
        _draw_usage_bar(draw, bar2_y, pct_bottom, mode_bottom, time_pct_bottom, fg, fg_half, fg_warn)

    return img


def _draw_centered_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, stroke_width: int, fg: tuple,
        box_top: int = 0, box_height: int = ICON_SIZE) -> None:
    """Draw *text* horizontally centered, vertically centered within the given box."""
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (ICON_SIZE - tw) / 2 - bbox[0]
    y = box_top + (box_height - th) / 2 - bbox[1]
    draw.text((x, y), text, fill=fg, font=font, stroke_width=stroke_width, stroke_fill=fg)


def _draw_number_row(draw: ImageDraw.ImageDraw, row_top: int, pct: float, extra_usage_available: bool, fg: tuple) -> None:
    """Draw one row of the ``'numbers'`` icon style at vertical offset *row_top*.

    The row shows the percentage clamped to 99, or ``✕``/``$`` when the
    quota is exhausted (following the same extra-usage rule as the classic
    top glyph).  Everything is drawn in *fg*, matching the classic glyph.
    """
    stroke_width = 0
    if pct >= 100 and not extra_usage_available:
        text, font = '\u2715', load_font(34, symbol=True)
        stroke_width = 2
    elif pct >= 100:
        # 32 is the ceiling for '$': its ascender and descender already span
        # 30 of the 32 row pixels, larger sizes would touch the next row.
        text, font = '$', load_font(32)
        stroke_width = 1
    else:
        # Clamp to 99: values in [99.5, 100) would round to a three-digit
        # '100' that overflows the canvas and reads as exhausted.
        text, font = f'{min(pct, 99):.0f}', load_font(40)

    _draw_centered_text(draw, text, font, stroke_width, fg, row_top, NUMBER_ROW_HEIGHT)


def _draw_usage_bar(draw: ImageDraw.ImageDraw, y: int, pct: float, mode: str, time_pct: float | None, fg: tuple, fg_half: tuple, fg_warn: tuple) -> None:
    """Draw one full-width usage bar at vertical offset *y*.

    In ``utilization`` mode the bar fills linearly with *pct* and shows a
    reset-time marker in *fg* at the *time_pct* position; the fill switches
    to *fg_warn* when usage is ahead of the elapsed time or fully exhausted,
    mirroring the popup's warning fill.  In ``overage`` mode the bar fills
    as *pct* exceeds *time_pct* and no marker is drawn - elapsed time is
    already encoded in the fill.
    """
    draw.rectangle([0, y, ICON_SIZE - 1, y + BAR_HEIGHT - 1], fill=fg_half)

    if mode == 'overage' and time_pct is not None:
        if time_pct >= 100:
            # End state for a stale window (elapsed time clamped to 100%,
            # e.g. between a reset and the confirming poll): usage below the
            # limit stayed within budget (empty bar), an exhausted quota
            # keeps the bar full - never the linear utilization fill.
            if pct >= 100:
                draw.rectangle([0, y, ICON_SIZE - 1, y + BAR_HEIGHT - 1], fill=fg)
            return

        overage = max(0.0, pct - time_pct)
        fill_ratio = min(1.0, overage / (100 - time_pct))
        fill_w = max(0, int(ICON_SIZE * fill_ratio))
        if fill_w > 0:
            draw.rectangle([0, y, fill_w - 1, y + BAR_HEIGHT - 1], fill=fg)
        return

    fill_w = max(0, min(ICON_SIZE, int(ICON_SIZE * pct / 100)))
    if fill_w > 0:
        warn = mode == 'utilization' and (pct >= 100 or (time_pct is not None and pct > time_pct))
        draw.rectangle([0, y, fill_w - 1, y + BAR_HEIGHT - 1], fill=fg_warn if warn else fg)

    if mode != 'utilization' or time_pct is None:
        return

    marker_x = min(ICON_SIZE - MARKER_WIDTH, max(0, int(ICON_SIZE * time_pct / 100) - MARKER_WIDTH // 2))
    marker_end = marker_x + MARKER_WIDTH - 1
    draw.rectangle([marker_x, y, marker_end, y + BAR_HEIGHT - 1], fill=fg)


def create_status_image(text: str, light_taskbar: bool = False) -> Image.Image:
    """Create monochrome centered-text icon for error/status states."""
    fg_dim = (ICON_DARK if light_taskbar else ICON_LIGHT)['fg_dim']

    S = 64
    img = Image.new('RGBA', (S, S), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    font = load_font(46)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((S - tw) / 2 - bbox[0], (S - th) / 2 - bbox[1]), text, fill=fg_dim, font=font)

    return img
