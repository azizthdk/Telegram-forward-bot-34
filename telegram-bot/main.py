import os
import logging
import warnings
from bot import build_app
from telegram import Update

warnings.filterwarnings("ignore", message="If 'per_message=False'", category=UserWarning)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = build_app(token)
    logger.info("Starting Telegram Forwarder Bot...")
    # run_polling manages its own event loop — do NOT wrap in asyncio.run()
    # drop_pending_updates=False so commands sent during a restart are NOT lost.
    # Old channel messages are filtered by handle_forward's startup_time guard instead.
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)


if __name__ == "__main__":
    main()
