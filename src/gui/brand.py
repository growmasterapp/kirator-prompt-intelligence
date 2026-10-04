"""
Optional Kirator brand kit.

On Graham's PC the shared kit lives at C:\\KIRATOR\\KIRATOR_GUI-BRAND.
That folder is not part of this repo, and this app must run without it.

If the folder is there (or KIRATOR_BRAND_KIT points at a copy), we use its
logo and an extra stylesheet. If it is missing, the built-in forest theme
in src/gui/static/css/design-tokens.css and the built-in mark.svg are used.

This module never inserts that folder onto sys.path and never imports it.
A missing kit is normal.
"""

from __future__ import annotations

import os
from pathlib import Path

# Checked only when the folder actually exists. Not required to run.
_DEFAULT_KIT = Path(r"C:\KIRATOR\KIRATOR_GUI-BRAND")

_LOGO_NAMES = ("logo.png", "logo.svg", "mark.svg", "brand.png")
_THEME_NAMES = ("theme.css", "design-tokens.css", "kirator.css")


def brand_kit_dir() -> Path | None:
    """Return the kit directory when one is installed, else None."""
    candidates: list[Path] = []
    override = os.environ.get("KIRATOR_BRAND_KIT", "").strip()
    if override:
        candidates.append(Path(override))
    candidates.append(_DEFAULT_KIT)
    for path in candidates:
        try:
            if path.is_dir():
                return path
        except OSError:
            continue
    return None


def brand_logo_file() -> Path | None:
    kit = brand_kit_dir()
    if kit is None:
        return None
    for name in _LOGO_NAMES:
        candidate = kit / name
        if candidate.is_file():
            return candidate
    return None


def brand_theme_file() -> Path | None:
    kit = brand_kit_dir()
    if kit is None:
        return None
    for name in _THEME_NAMES:
        candidate = kit / name
        if candidate.is_file():
            return candidate
    return None


def logo_url(static_dir: Path) -> str:
    """
    URL for the header mark.

    Order: brand-kit logo, then a logo.png shipped beside the GUI,
    then the built-in SVG. The SVG is always in the repo, so tests and
    fresh machines do not need a PNG.
    """
    if brand_logo_file() is not None:
        return "/brand/logo"
    png = Path(static_dir) / "logo.png"
    if png.is_file():
        return "/static/logo.png"
    return "/static/mark.svg"


def theme_url() -> str | None:
    """Extra stylesheet from the kit, or None to keep the built-in theme."""
    if brand_theme_file() is None:
        return None
    return "/brand/theme.css"
