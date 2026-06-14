import logging
import os
import sys
import threading
import warnings

warnings.filterwarnings("ignore", message="If 'per_message=False'", category=UserWarning)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class _HealthHandler:
    """Minimal HTTP/1.1 health-check handler."""

    def __init__(self, conn, addr):
        try:
            conn.recv(4096)
            conn.sendall(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain\r\n"
                b"Content-Length: 2\r\n"
                b"Connection: close\r\n"
                b"\r\nOK"
            )
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


def _start_health_server() -> bool:
    """
    Bind the health-check TCP socket and start a background thread.
    Returns True on success, False if the port is already in use.

    IMPORTANT: the socket is bound here (before thread.start) so that
    Railway's probe gets a valid response the instant the process starts —
    not after a thread-scheduling delay.
    """
    import socket

    port = int(os.environ.get("PORT", 8080))
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(16)
        logger.info("Health server bound on 0.0.0.0:%d", port)
    except OSError as exc:
        logger.error("Health server could not bind to port %d: %s", port, exc)
        return False

    def _serve():
        while True:
            try:
                conn, addr = srv.accept()
                _HealthHandler(conn, addr)
            except Exception:
                pass

    # daemon=True: health thread must NOT keep the process alive after a crash —
    # Railway needs the process to exit so it can restart it automatically.
    t = threading.Thread(target=_serve, daemon=True, name="health-server")
    t.start()
    return True


def main():
    # ── 1. Bind health server FIRST ──────────────────────────────────────────
    # Do this before ANY other import so Railway's probe never gets
    # "connection refused", even if the bot fails to start.
    if not _start_health_server():
        logger.critical("Cannot bind health server — exiting with code 1")
        sys.exit(1)

    # ── 2. NOW import bot code ────────────────────────────────────────────────
    # Moving imports here means a missing dependency or bad env var never
    # prevents the health server from binding.
    try:
        from bot import build_app
        from telegram import Update
    except Exception as exc:
        logger.critical("Import error — bot will NOT start: %s", exc, exc_info=True)
        # Exit non-zero so Railway restarts and the error stays visible in logs.
        sys.exit(1)

    # ── 3. Check required env vars ────────────────────────────────────────────
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.critical(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Add it as an environment variable in Railway and redeploy."
        )
        sys.exit(1)

    api_id   = os.environ.get("TELEGRAM_API_ID", "0")
    api_hash = os.environ.get("TELEGRAM_API_HASH", "")
    if api_id == "0" or not api_hash:
        logger.warning(
            "TELEGRAM_API_ID / TELEGRAM_API_HASH not set — "
            "userbot features (/copy, /sync, /dualcopy) will be disabled."
        )

    # ── 4. Build and run ──────────────────────────────────────────────────────
    try:
        app = build_app(token)
        logger.info("Starting Telegram Forwarder Bot…")
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
    except Exception as exc:
        logger.critical("Bot crashed: %s", exc, exc_info=True)
        # Exit non-zero → Railway restarts the process automatically.
        sys.exit(1)


if __name__ == "__main__":
    main()
