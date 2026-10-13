"""Restore inherited subprocess pipes in a windowed Windows executable."""
import ctypes as C
import os
import sys


def restore_worker_stdio():
    if sys.platform != 'win32':
        return
    import msvcrt
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetStdHandle.argtypes, kernel.GetStdHandle.restype = [C.c_ulong], C.c_void_p
    kernel.GetCurrentProcess.argtypes, kernel.GetCurrentProcess.restype = [], C.c_void_p
    kernel.DuplicateHandle.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p,
                                      C.POINTER(C.c_void_p), C.c_ulong, C.c_int, C.c_ulong]
    kernel.DuplicateHandle.restype = C.c_int
    process = kernel.GetCurrentProcess()
    for name, number, mode, flags in [('stdin', -10, 'r', os.O_RDONLY),
                                      ('stdout', -11, 'w', os.O_WRONLY),
                                      ('stderr', -12, 'w', os.O_WRONLY)]:
        if getattr(sys, name) is not None:
            continue
        handle = kernel.GetStdHandle(number & 0xffffffff)
        duplicate = C.c_void_p()
        if handle and handle != C.c_void_p(-1).value and kernel.DuplicateHandle(process, handle, process, C.byref(duplicate), 0, False, 2):
            fd = msvcrt.open_osfhandle(duplicate.value, flags | os.O_BINARY)
            stream = os.fdopen(fd, mode, encoding='utf-8', buffering=1)
        else:
            stream = open(os.devnull, mode, encoding='utf-8')
        setattr(sys, name, stream)
