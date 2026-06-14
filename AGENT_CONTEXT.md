# Agent Context — Telegram Forward Bot

> Read this first. It will save you hours of archaeology.

## What this project is

A Telegram bot deployed on **Railway** that forwards and copies messages between Telegram channels. Two operating modes:

- **Bot-forwarding** — uses the PTB bot token to forward messages (adds "Forwarded from" tag)
- **Userbot copy** — uses Telethon with a real Telegram account to copy messages silently (no tag)

The main feature recently added is **dual-bot parallel copy**: two Telethon accounts work simultaneously on split halves of a channel, giving ~2× copy speed.

---

## Repo layout

```
telegram-bot/           ← all bot code lives here
├── main.py             ← entry point; reads BOT_TOKEN, calls bot.build_app()
├── bot.py              ← PTB Application builder; registers ALL handlers + convs
├── states.py           ← ALL ConversationHandler state constants (0–26, unique)
├── config.py           ← reads env vars (BOT_TOKEN, ALLOWED_USER_ID, etc.)
├── forwarder.py        ← live message forwarding via bot token
├── database.py         ← aiosqlite DB (forwarding rules, ignore list)
├── log_buffer.py       ← in-memory ring buffer for /logs command
├── userbot_bridge.py   ← manages BOTH Telethon clients (Bot 1 + Bot 2)
├── handlers/
│   ├── menu.py         ← main menu keyboard + start/help/uptime/unknown handlers
│   ├── copybot.py      ← /copy, /dryrun, /sync, /status, /stopjob, /resume
│   ├── login.py        ← /login wizard (OTP + string-session, Bot 1)
│   ├── login2.py       ← /login2 wizard (OTP + string-session, Bot 2)
│   ├── dualcopy.py     ← /dualcopy wizard, /stopdual, /status2
│   ├── rules.py        ← add/list/delete forwarding rules
│   ├── history.py      ← /history, /clearhistory
│   ├── ignore.py       ← ignore list management
│   ├── preview.py      ← /previewcaption wizard
│   └── autoresume.py   ← auto-resume copy job after restart
└── userbot/
    ├── forwarder.py    ← single-bot copy engine
    ├── dual_forwarder.py ← dual-bot parallel copy engine
    ├── sync.py         ← live sync (new messages forwarded in real-time)
    ├── sender.py       ← _do_send() / send_album() — actual Telegram sends
    ├── filter_utils.py ← file extension filtering
    ├── checkpoint.py   ← saves/loads copy progress to disk
    └── notifier.py     ← progress callback helpers
```

---

## How to push code changes from Replit

**`git push` is blocked in the Replit sandbox.** Use the GitHub Contents API instead.

```bash
TOKEN=$(printenv GITHUB_PERSONAL_ACCESS_TOKEN)
REPO="azizthdk/Telegram-forward-bot-34"

# 1. Fetch a file (get current SHA — required for PUT)
curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/$REPO/contents/telegram-bot/PATH/TO/FILE.py" | \
  python3 -c "import sys,json,base64; d=json.load(sys.stdin); print('SHA:', d['sha']); print(base64.b64decode(d['content']).decode())"

# 2. Push updated file (replace FILE_SHA with the sha from step 1)
CONTENT=$(base64 -w0 /tmp/updated_file.py)
curl -s -X PUT "https://api.github.com/repos/$REPO/contents/telegram-bot/PATH/TO/FILE.py" \
  -H "Authorization: token $TOKEN" -H "Content-Type: application/json" \
  -d "{\"message\":\"your commit message\",\"content\":\"$CONTENT\",\"sha\":\"FILE_SHA\"}"
```

Railway auto-deploys on every push to main.

---

## Critical facts you must know

### `main_menu_keyboard` signature
```python
# handlers/menu.py
def main_menu_keyboard(userbot_ready: bool = False, userbot2_ready: bool = False):
```
- **Never** pass unknown kwargs — causes TypeError crash on every menu render
- Internal callers: `main_menu_keyboard(_ready(context), _ready2(context))`
- Login success callers pass explicit booleans

### `_do_send()` return values
`"ok"` | `"skip"` | `"skip_unsupported"` | `"skip_deleted"` | `"fail"`

`send_album()` returns only: `"ok"` | `"skip"` | `"fail"`

In `dual_forwarder.py`: use `elif result == "fail": failed += 1` then `else: skipped += 1`.
Do NOT check `elif result == "skip"` — it will miss the `_unsupported` / `_deleted` variants.

### Bot 1 vs Bot 2 bot_data keys
| Purpose | Bot 1 | Bot 2 |
|---|---|---|
| Client object | `userbot_client` | `userbot2_client` |
| Ready flag | `userbot_ready` | `userbot2_ready` |
| Locked flag | `userbot_locked` | `userbot2_locked` |
| Connect loop task | `_userbot_connect_task` | `_userbot2_connect_task` |

### ConversationHandler registration order (`bot.py`)
```
preview_conv → copy_conv → login_conv → login2_conv → dualcopy_conv → main conv
```
Order matters. Moving any of these breaks state routing.

### `userbot2_login` callback
Menu button `callback_data="userbot2_login"` falls through the main conv (intentionally not handled there) to `login2_conv`'s entry point. Do not add it to the main conv's MAIN_MENU state.

### Telethon entity resolution
`dual_forwarder.py` uses `resolve_entity_safe()` which calls `client.get_dialogs()` on `ValueError`. This fixes `Could not find input entity for PeerChannel` when Bot 2 has never cached a channel. Always use this wrapper when resolving entities.

---

## Railway environment variables

| Variable | Required | Purpose |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram bot token |
| `TELEGRAM_API_ID` | ✅ | Telethon API ID (from my.telegram.org) |
| `TELEGRAM_API_HASH` | ✅ | Telethon API hash |
| `ALLOWED_USER_ID` | ✅ | Telegram user ID that controls the bot |
| `SESSION_STRING` | optional | Bot 1 Telethon session (auto-generated by /login) |
| `SESSION_STRING_2` | optional | Bot 2 Telethon session (auto-generated by /login2) |

If `SESSION_STRING` / `SESSION_STRING_2` are not set, the userbots start with no session and the user must /login on each cold-start.

---

## Bugs fixed in this session (do not re-introduce)

| # | Bug | File | Fix |
|---|---|---|---|
| 1 | CRASH: `main_menu_keyboard()` called with unknown `userbot2_ready=True` kwarg | `handlers/login2.py` `_login2_success` | Removed unknown kwarg; added `userbot2_ready` param to function signature |
| 2 | WRONG COUNTS: `skip_unsupported`/`skip_deleted` counted as failures in dual copy | `userbot/dual_forwarder.py` `_copy_range` | Fixed to `elif result == "fail"` + `else: skipped` |
| 3 | NO BUTTON: "Connect Userbot 2" missing from main menu | `handlers/menu.py` | Added `userbot2_ready` param + new button row |
| 4 | WRONG STATUS: login success menu didn't show Bot 2 connection state | `handlers/login.py`, `handlers/login2.py` | Pass correct `userbot2_ready` bool to `main_menu_keyboard` |

---

## Known behaviour (not a bug)

**"Userbot is still initialising"** — On Railway cold-start, if a user taps "Connect Userbot 1" within ~2 seconds of boot, `bridge.get_client(bot_data)` returns None because the background `_connect_loop` task hasn't completed `client.connect()` yet. The bot tells the user to wait and try again. This resolves itself in ~3 seconds.

---

## Full dual-copy feature summary

Commands added:
- `/login2` — connects second Telegram account (OTP or string-session paste)
- `/dualcopy` — wizard: source → dest → options → launches parallel copy
- `/status2` — live side-by-side breakdown (Bot 1 first half vs Bot 2 second half)
- `/stopdual` — cancels the running dual-copy job

How it works:
1. `copy_channel_files_dual()` in `userbot/dual_forwarder.py` collects all message IDs
2. Splits them 50/50 between Bot 1 and Bot 2
3. Both coroutines run concurrently via `asyncio.gather()`
4. A shared `asyncio.Lock` + shared checkpoint prevents duplicate sends
5. Progress is reported via a single Telegram message edited periodically
