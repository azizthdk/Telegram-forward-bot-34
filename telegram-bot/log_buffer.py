"""
In-memory circular log buffer — captures recent log lines so /logs can
show them inside Telegram without needing Railway's console.

Usage:
    import log_buffer
    log_buffer.setup()          # once at process start
    lines = log_buffer.get_lines(25)
"""
import logging
from collections import deque

_MAX = 500   # keep at most 500 lines in memory


class _BufferHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self._buf: deque[str] = deque(maxlen=_MAX)
        self.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._buf.append(self.format(record))
        except Exception:
            self.handleError(record)

    def get_lines(self, n: int = 25) -> list[str]:
        lines = list(self._buf)
        return lines[-n:]


_handler: "_BufferHandler | None" = None


def setup() -> None:
    """Register the buffer handler on the root logger. Call once at startup."""
    global _handler
    if _handler is not None:
        return  # already set up — idempotent
    _handler = _BufferHandler()
    _handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(_handler)


def get_lines(n: int = 25) -> list[str]:
    """Return the last *n* captured log lines (most recent last)."""
    if _handler is None:
        return ["(log buffer not initialised — log_buffer.setup() was not called)"]
    return _handler.get_lines(n)
