"""Keep native taskbar minimization for the fixed, frameless Windows window."""
import ctypes
from ctypes import wintypes
import os


def enable_taskbar_minimize(hwnd):
    if os.name != 'nt':
        return
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    get_style = user32.GetWindowLongW
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = wintypes.LONG
    set_style = user32.SetWindowLongW
    set_style.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    set_style.restype = wintypes.LONG
    set_position = user32.SetWindowPos
    set_position.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                            ctypes.c_int, ctypes.c_int, wintypes.UINT]
    set_position.restype = wintypes.BOOL
    # FormBorderStyle.None removes these flags; the shell needs them to minimize.
    style = get_style(hwnd, -16)
    ctypes.set_last_error(0)
    if not set_style(hwnd, -16, (style | 0x00020000 | 0x00080000) & ~0x00010000) and ctypes.get_last_error():
        raise ctypes.WinError(ctypes.get_last_error())
    # Refresh non-client state without moving, resizing, activating or adding a caption.
    if not set_position(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020):
        raise ctypes.WinError(ctypes.get_last_error())
