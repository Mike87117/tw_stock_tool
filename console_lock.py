"""Shared console IO lock for thread-safe terminal output."""

from contextlib import contextmanager
from collections.abc import Iterator
import threading

_CONSOLE_IO_LOCK = threading.RLock()


@contextmanager
def console_io_lock() -> Iterator[None]:
    """Serialize process-global stdout/stderr changes and console prints."""
    with _CONSOLE_IO_LOCK:
        yield
