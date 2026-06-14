import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from states import MAIN_MENU

MAIN_MENU_TEXT = (
    "🤖 *Telegram Forwarder Bot*\n\n"
    "Choose an option below:"
)


def main_menu_keyboard(userbot_ready: bool = False):
    connect_label = (
        "✅ Userbot Connected"
        if userbot_ready
        else "🔑 Connect Userbot"
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Forward Rule",   callback_data="add_rule")],
        [InlineKeyboardButton("📋 List Forward Rules", callback_data="list_rules")],
        [InlineKeyboardButton("🗑 Delete Forward Rule", callback_data="delete_rule")],
        [InlineKeyboardButton("📜 Forward History",    callback_data="fwd_history")],
        [InlineKeyboardButton("🚫 Ignore List",        callback_data="ignore_list")],
        [InlineKeyboardButton(connect_label,           callback_data="userbot_login"),
         InlineKeyboardButton("📊 Status",             callback_data="status_menu")],
        [InlineKeyboardButton("📡 List My Chats",      callback_data="listchats_menu")],
        [InlineKeyboardButton("ℹ️ Help",               callback_data="help")],
    ])


def _ready(context) -> bool:
    import userbot_bridge as bridge
    return bridge.is_ready(context.bot_data)


def _fmt_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string."""
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        MAIN_MENU_TEXT,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(_ready(context)),
    )
    return MAIN_MENU


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        MAIN_MENU_TEXT,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(_ready(context)),
    )
    return MAIN_MENU


async def uptime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show how long the bot and userbots have been running."""
    now = time.time()
    bd  = context.bot_data

    # ── Bot process uptime ────────────────────────────────────────────────────
    bot_start = bd.get("bot_start_time")
    if bot_start:
        bot_uptime = f"`{_fmt_duration(now - bot_start)}`"
    else:
        bot_uptime = "_unknown_"

    # ── Userbot 1 uptime ──────────────────────────────────────────────────────
    ub1_at = bd.get("userbot_connected_at")
    if ub1_at:
        ub1_uptime = f"`{_fmt_duration(now - ub1_at)}`"
    elif bd.get("userbot_ready"):
        ub1_uptime = "`connected (time unknown)`"
    else:
        ub1_uptime = "_not connected_"

    # ── Active job info ───────────────────────────────────────────────────────
    copy_task = bd.get("active_copy_task")
    sync_task = bd.get("active_sync_task")
    if copy_task and not copy_task.done():
        job_line = "📋 Copy job: `running`"
    elif sync_task and not sync_task.done():
        job_line = "🔄 Sync job: `running`"
    else:
        job_line = "💤 No active job"

    text = (
        "⏱ *Bot Uptime*\n\n"
        f"🤖 Bot process : {bot_uptime}\n"
        f"👤 Userbot     : {ub1_uptime}\n\n"
        f"{job_line}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Help — Telegram Forwarder Bot*\n\n"
        "*How to use:*\n"
        "1. Add this bot as an *admin* to the destination chat/channel.\n"
        "2. Use *Add Forward Rule* to set up auto-forwarding.\n"
        "3. Tap *🔑 Connect Userbot* (or send /login) to enable copy/sync.\n\n"
        "*Bot forwarding (with 'Forwarded from' tag):*\n"
        "• ➕ *Add Forward Rule* — Auto-forward messages from one chat to another\n"
        "• 📋 *List Rules* — See all active forwarding rules\n"
        "• 🗑 *Delete Rule* — Remove a forwarding rule\n"
        "• 📜 *Forward History* — Forward past messages from a channel\n"
        "• 🚫 *Ignore List* — Chats to skip during bulk operations\n\n"
        "*Userbot copy (NO 'Forwarded from' tag):*\n"
        "• /login — Connect your Telegram account (required first)\n"
        "• /copy — Bulk-copy files from any channel you're a member of\n"
        "• /dryrun — Preview what would be copied (nothing is sent)\n"
        "• /sync — Start live auto-sync (new messages forwarded instantly)\n"
        "• /stopsync — Stop the running auto-sync\n"
        "• /status — Check current copy job progress\n"
        "• /stopjob — Cancel the running copy job\n"
        "• /resume — Resume a copy job after a bot restart\n\n"
        "*Inspection & diagnostics:*\n"
        "• /listchats — List all your Telegram chats with IDs\n"
        "• /synctest — Test that auto-sync is live and measure latency\n"
        "• /previewcaption — Preview how a caption will look after cleaning\n"
        "• /history — Show copy job statistics for each channel pair\n"
        "• /clearhistory — Delete checkpoint files so a pair can be re-copied\n"
        "• /config — Show current bot configuration\n"
        "• /uptime — Show how long the bot and userbot have been running\n"
        "• /logs [N] — Show the last N log lines for crash diagnostics\n\n"
        "*Important:*\n"
        "• The bot must be an *admin* in destination chats for forwarding.\n"
        "• For /copy and /sync you only need to be a *member* of the source channel.\n"
        "• After /login, copy your SESSION_STRING and add it to Railway Variables\n"
        "  so the userbot reconnects automatically after each redeploy."
    )
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]
            ),
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(_ready(context)),
        )
    return MAIN_MENU


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fires when the user sends an unrecognised /command."""
    cmd = update.message.text.split()[0] if update.message.text else "that"
    await update.message.reply_text(
        f"❓ `{cmd}` is not a valid command.\n\n"
        "Here's what I can do — tap a button or send a command:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(_ready(context)),
    )


async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fires when the user sends a plain text message outside any conversation."""
    text = (update.message.text or "").strip().lower()

    greetings = {"hi", "hello", "hey", "hii", "helo", "hiiii", "yo", "sup"}
    thanks    = {"thanks", "thank you", "ty", "thx", "ok", "okay", "k", "done", "cool", "nice"}
    bye       = {"bye", "goodbye", "cya", "see you", "gn", "good night"}

    if text in greetings:
        reply = "👋 Hey! I'm your Telegram Forwarder Bot. Use /menu to see all options."
    elif text in thanks:
        reply = "✅ You're welcome! Let me know if you need anything else — /menu"
    elif text in bye:
        reply = "👋 Goodbye! The bot keeps running in the background."
    else:
        reply = (
            "🤖 I didn't understand that.\n\n"
            "I only respond to commands. Try one of these:"
        )

    await update.message.reply_text(
        reply,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(_ready(context)),
    )
