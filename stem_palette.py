"""Validated per-stem colors shared by settings and the container writer."""
import re

DEFAULT_COLORS = ['#009E73', '#D55E00', '#CC79A7', '#56B4E9']


def validate_colors(colors):
    if not isinstance(colors, (list, tuple)) or len(colors) != 4:
        raise ValueError('Choose four stem colors.')
    if any(not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color) for color in colors):
        raise ValueError('Stem colors must use #RRGGBB.')
    return [color.upper() for color in colors]
