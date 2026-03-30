"""
ERP-CNC Adapter Installer — Constants, colors, stylesheet, and helpers.
"""
import sys
from pathlib import Path

from version import VERSION


def _icon_path() -> str | None:
    """Return the path to logo.ico, or None if not found."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent.parent
    ico = base / "resources" / "logo.ico"
    return str(ico) if ico.exists() else None


# ── PL Project Color Scheme ──────────────────────────────────────────────────
PRIMARY   = "#4261ee"
GOLD      = "#ffab00"
NAVY      = "#0D132F"
BG        = "#ffffff"
BG_CARD   = "#f9f9f9"
TEXT_BODY  = "#333333"
TEXT_MUTED = "rgba(13, 19, 47, 0.7)"
BORDER     = "#eeeeee"

STYLESHEET = f"""
/* ── Window ────────────────────────────────────────────────────────────── */
#InstallerWindow {{
    background: {BG};
    border-radius: 12px;
    border: 1px solid {BORDER};
}}

/* ── Custom Title Bar ─────────────────────────────────────────────────── */
#TitleBar {{
    background: {BG};
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}}
#TitleBar QLabel {{
    color: {NAVY};
    font-size: 13px;
    font-weight: 600;
}}
#CloseButton {{
    background: transparent;
    color: {TEXT_BODY};
    font-size: 18px;
    font-weight: bold;
    border: none;
    padding: 4px 12px;
    border-radius: 6px;
}}
#CloseButton:hover {{
    background: #e74c3c;
    color: white;
}}

/* ── Step Indicator ───────────────────────────────────────────────────── */
#StepDot {{
    border-radius: 6px;
    min-width: 12px; max-width: 12px;
    min-height: 12px; max-height: 12px;
}}
#StepLabel {{
    font-size: 11px;
}}

/* ── Page content ─────────────────────────────────────────────────────── */
#PageTitle {{
    color: {NAVY};
    font-size: 22px;
    font-weight: 700;
}}
#PageSubtitle {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}

/* ── Buttons ──────────────────────────────────────────────────────────── */
#PrimaryButton {{
    background: {PRIMARY};
    color: white;
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    padding: 10px 32px;
}}
#PrimaryButton:hover {{
    background: #3451d1;
}}
#PrimaryButton:disabled {{
    background: #a0b0ee;
}}

#SecondaryButton {{
    background: transparent;
    color: {TEXT_BODY};
    font-size: 14px;
    font-weight: 500;
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 32px;
}}
#SecondaryButton:hover {{
    background: {BG_CARD};
}}

#GoldButton {{
    background: {GOLD};
    color: {NAVY};
    font-size: 14px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    padding: 10px 32px;
}}
#GoldButton:hover {{
    background: #e69d00;
}}

/* ── Path Input ───────────────────────────────────────────────────────── */
#PathInput {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    color: {TEXT_BODY};
    background: {BG};
}}
#PathInput:focus {{
    border-color: {PRIMARY};
}}

#BrowseButton {{
    background: {BG_CARD};
    color: {TEXT_BODY};
    font-size: 13px;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 16px;
}}
#BrowseButton:hover {{
    background: {BORDER};
}}

/* ── Progress Bar ─────────────────────────────────────────────────────── */
QProgressBar {{
    background: {BORDER};
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: #905BA9;
    border-radius: 6px;
}}

/* ── Log Area ─────────────────────────────────────────────────────────── */
#LogArea {{
    background: {BG_CARD};
    color: {TEXT_BODY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px;
    font-family: Consolas, monospace;
    font-size: 12px;
}}

/* ── Misc ─────────────────────────────────────────────────────────────── */
#DiskLabel {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
#Checkmark {{
    color: #27ae60;
    font-size: 56px;
    font-weight: bold;
}}
#SuccessLabel {{
    color: {NAVY};
    font-size: 18px;
    font-weight: 600;
}}
#UrlLabel {{
    color: {PRIMARY};
    font-size: 14px;
}}
"""
