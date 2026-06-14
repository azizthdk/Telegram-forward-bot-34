"""
Manages a shared Telethon userbot client inside PTB's asyncio event loop.

The connection is made in a background task so the bot starts polling
immediately. The client is stored in bot_data as soon as it connects
(even before authorisation) so the in-bot login wizard can use it
straight away.

SESSION_STRING support
──────────────────────
On Railway (ephemeral filesystem) set the SESSION_STRING environment variable
to a Telethon StringSession export. The session is kept entirely in memory —
no file is written, so sessions survive redeployments without a volume mount.

To generate a SESSION_STRING, run once locally:
    from telethon.sessions import StringSession
    from telethon import TelegramClient
    import asyncio, os
    async def main():
        c = TelegramClient(StringSession(), int(os.environ["TELEGRAM_API_ID"]),
                           os.environ["TELEGRAM_API_HASH"])
        await c.start()
        print(c.session.save())
    asyncio.run(main())
"""
import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)

def _parse_api_id() -> int:
    val = (os.environ.get("TELEGRAM_API_ID", "") or "0").strip()
    try:
        return int(val)
    except ValueError:
        return 0   # invalid value — userbot will be disabled with a warning

API_ID = _parse_api_id()
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

# SESSION_STRING takes priority — required on Railway (ephemeral filesystem).
# SESSION_PATH is used as fallback when running locally or on a volume mount.
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
SESSION_PATH   = os.environ.get(
    "SESSION_PATH",
    os.path.join(os.path.dirname(__file__), "sessions", "userbot"),
)

_FAST_RETRIES = 12
_FAST_DELAY   = 5
_SLOW_DELAY   = 30


async def _connect_loop(bot_data: dict) -> None:
    """
    Background task — connects the Telethon client and keeps it available.

    Key guarantee: bot_data["userbot_client"] is set to the connected client
    immediately after connect() succeeds, BEFORE the authorisation check.
    This means the in-bot /login wizard can always call send_code_request()
    even if the session file has no saved credentials yet.
    """
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        logger.warning("telethon not installed — userbot commands disabled")
        return

    os.makedirs(os.path.join(os.path.dirname(__file__), "sessions"), exist_ok=True)

    attempt = 0
    while True:
        attempt += 1
        client = None
        try:
            if SESSION_STRING:
                client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
                logger.info("Userbot using SESSION_STRING (survives redeployments)")
            else:
                client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
                logger.info("Userbot using file session at %s", SESSION_PATH)

            await client.connect()

            # ── Set the client IMMEDIATELY after connect, before auth check ──
            bot_data["userbot_client"] = client
            bot_data.pop("userbot_locked", None)

            if not await client.is_user_authorized():
                logger.warning(
                    "Userbot session not authorised — use /login in the bot to sign in."
                )
                bot_data["userbot_ready"] = False

                authorised = False
                while True:
                    await asyncio.sleep(10)
                    try:
                        if await client.is_user_authorized():
                            authorised = True
                            break
                    except Exception:
                        logger.warning("Userbot auth-poll error — reconnecting")
                        break

                if not authorised:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                    bot_data["userbot_ready"] = False
                    await asyncio.sleep(_FAST_DELAY)
                    continue

            me = await client.get_me()
            bot_data["userbot_client"] = client
            bot_data["userbot_ready"]  = True
            # Record connect time only on first successful auth so /uptime shows
            # time since first login, not time since last reconnect.
            if "userbot_connected_at" not in bot_data:
                bot_data["userbot_connected_at"] = time.time()
            logger.info("Userbot bridge connected as %s (@%s)", me.first_name, me.username)

            while True:
                await asyncio.sleep(30)
                try:
                    if not client.is_connected():
                        logger.warning("Userbot connection lost — reconnecting…")
                        break
                    if not await client.is_user_authorized():
                        logger.warning("Userbot session deauthorised — reconnecting…")
                        break
                except Exception as e:
                    logger.warning("Userbot health-check failed: %s — reconnecting…", e)
                    break

            bot_data["userbot_ready"] = False
            try:
                await client.disconnect()
            except Exception:
                pass
            await asyncio.sleep(_FAST_DELAY)
            continue

        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

            if "database is locked" in str(e).lower():
                if attempt == 1:
                    logger.warning(
                        "Userbot session locked — retrying every 5 s for 1 min, then every 30 s."
                    )
                    bot_data["userbot_locked"] = True
                elif attempt == _FAST_RETRIES + 1:
                    logger.warning("Session still locked — switching to slow retries (30 s).")
                delay = _FAST_DELAY if attempt <= _FAST_RETRIES else _SLOW_DELAY
                await asyncio.sleep(delay)
            else:
                logger.error("Userbot connect failed: %s", e)
                await asyncio.sleep(_SLOW_DELAY)


async def init_userbot(application) -> None:
    """PTB post_init hook — starts the connection task and returns immediately."""
    bot_data = application.bot_data
    bot_data.setdefault("active_copy_task",    None)
    bot_data.setdefault("active_sync_task",    None)
    bot_data.setdefault("active_sync_handler", None)
    bot_data.setdefault("active_copy_stats",   {})
    bot_data.setdefault("userbot_ready",       False)

    if not API_ID or not API_HASH:
        logger.warning("TELEGRAM_API_ID/HASH not set — userbot commands disabled")
        return

    task = asyncio.create_task(_connect_loop(bot_data))
    bot_data["_userbot_connect_task"] = task
    logger.info("Userbot bridge task started in background")


def get_client(bot_data: dict):
    return bot_data.get("userbot_client")


def is_ready(bot_data: dict) -> bool:
    return bot_data.get("userbot_ready", False)


def is_locked(bot_data: dict) -> bool:
    return bot_data.get("userbot_locked", False)
