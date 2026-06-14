import logging
import os
import sys
import threading
import time
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
    IMPORTANT: bound before thread.start so Railway's probe gets an immediate
    200 OK even before the bot finishes connecting.
    daemon=True: health thread must NOT keep the process alive after main exits.

    Returns False if binding fails (e.g. port already in use on restart).
    The bot continues running even if the health server can't bind — a brief
    gap is acceptable; Railway/Render will retry the health check shortly.
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
        logger.warning("Health server could not bind to port %d: %s — continuing without it", port, exc)
        return False

    def _serve():
        while True:
            try:
                conn, addr = srv.accept()
                _HealthHandler(conn, addr)
            except Exception:
                pass

    t = threading.Thread(target=_serve, daemon=True, name="health-server")
    t.start()
    return True


def main():
    # ── 0. Start in-memory log buffer so /logs works immediately ─────────────
    import log_buffer
    log_buffer.setup()

    # ── 1. Bind health server FIRST ──────────────────────────────────────────
    # NOTE: We do NOT exit if the server can't bind — a transient port-in-use
    # error on restart should not kill the bot. Railway/Render retries probes.
    _start_health_server()

    # ── 2. Diagnose env vars BEFORE importing bot code ────────────────────────
    # These log lines appear in Railway's console and make it obvious which
    # variable is missing when the bot fails to start.
    _tok    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    _api_id = os.environ.get("TELEGRAM_API_ID",    "")
    _api_h  = os.environ.get("TELEGRAM_API_HASH",  "")
    logger.info(
        "Env check — BOT_TOKEN:%s  API_ID:%s  API_HASH:%s",
        "SET" if _tok    else "*** MISSING ***",
        "SET" if _api_id else "not set (userbot disabled)",
        "SET" if _api_h  else "not set (userbot disabled)",
    )
    if not _tok:
        logger.critical(
            "TELEGRAM_BOT_TOKEN is not set — bot cannot start. "
            "Go to Railway → your service → Variables and add it."
        )
        sys.exit(1)

    # ── 3. Import bot code ────────────────────────────────────────────────────
    try:
        from bot import build_app
        from telegram import Update
    except Exception as exc:
        logger.critical("Import error — bot will NOT start: %s", exc, exc_info=True)
        sys.exit(1)

    if not _api_id:
        logger.warning(
            "TELEGRAM_API_ID / TELEGRAM_API_HASH not set — "
            "userbot features (/copy, /sync, /dualcopy) will be disabled."
        )

    # ── 4. Run with automatic retry on transient errors ───────────────────────
    # Retries handle: Telegram Conflict (old instance still polling),
    # network blips at startup, and other transient failures.
    # A non-transient crash (bad token, import error) exits with code 1
    # so Railway can surface it in logs and restart cleanly.
    MAX_RETRIES   = 5
    RETRY_DELAY   = 10   # seconds between retries

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            app = build_app(token)
            logger.info(
                "Starting Telegram Forwarder Bot… (attempt %d/%d)",
                attempt, MAX_RETRIES,
            )
            # drop_pending_updates=True clears the message backlog so the bot
            # doesn't try to process a flood of old /start commands on restart.
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
            # run_polling returned cleanly — exit normally
            logger.info("Bot stopped cleanly.")
            sys.exit(0)

        except Exception as exc:
            err = str(exc)
            is_conflict = "conflict" in err.lower() or "terminated by other" in err.lower()
            is_bad_token = "unauthorized" in err.lower() or "invalid token" in err.lower()

            if is_bad_token:
                logger.critical(
                    "Invalid TELEGRAM_BOT_TOKEN — check Railway Variables: %s", exc
                )
                sys.exit(1)

            if attempt < MAX_RETRIES:
                if is_conflict:
                    logger.warning(
                        "Telegram conflict (another bot instance is polling). "
                        "Waiting %ds then retrying… (%d/%d)",
                        RETRY_DELAY, attempt, MAX_RETRIES,
                    )
                else:
                    logger.error(
                        "Bot error on attempt %d/%d: %s — retrying in %ds",
                        attempt, MAX_RETRIES, exc, RETRY_DELAY, exc_info=True,
                    )
                time.sleep(RETRY_DELAY)
            else:
                logger.critical(
                    "Bot failed after %d attempts: %s", MAX_RETRIES, exc, exc_info=True
                )
                sys.exit(1)


if __name__ == "__main__":
    main()
