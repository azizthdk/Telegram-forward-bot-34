"""
Bot configuration — values are read from environment variables first,
falling back to the hardcoded defaults below.

On Railway: set these as environment variables in your service settings.
Locally:    create a .env file and load it with `python-dotenv`, or just
            edit the defaults directly.
"""
import os


def _int_env(key: str, default: int) -> int:
    val = os.environ.get(key, "").strip()
    try:
        return int(val) if val else default
    except ValueError:
        return default


# ── Source channel (where files are copied FROM) ─────────────────────────────
# Set SOURCE_CHANNEL env var on Railway, e.g. -1001811670072
SOURCE_CHANNEL: int = _int_env("SOURCE_CHANNEL", 0)

# ── Destination channel (where files are copied TO) ──────────────────────────
# Set DEST_CHANNEL env var on Railway, e.g. -1003563437550
DEST_CHANNEL: int = _int_env("DEST_CHANNEL", 0)

# ── Your channel link — replaces ALL @usernames AND t.me links in captions ───
# Set CAPTION_REPLACE env var, e.g. "@BackupChannel5211"
# Set to "" (empty string) to keep original captions unchanged.
CAPTION_REPLACE: str = os.environ.get("CAPTION_REPLACE", "")

# ── Notify every N files copied (0 = off) ────────────────────────────────────
NOTIFY_EVERY: int = _int_env("NOTIFY_EVERY", 100)

# ── File filter — only copy these extensions (empty = copy everything) ───────
# Set ALLOWED_EXTS env var as comma-separated list, e.g. "mkv,mp4"
_exts_env = os.environ.get("ALLOWED_EXTS", "").strip()
ALLOWED_EXTS: set = set(e.strip().lower() for e in _exts_env.split(",") if e.strip())

# ── Skip plain text-only messages ────────────────────────────────────────────
# Set SKIP_TEXT=true to skip all text messages (only copy media files)
SKIP_TEXT: bool = os.environ.get("SKIP_TEXT", "false").lower() in ("1", "true", "yes")

# ── Promo / watermark strip patterns ─────────────────────────────────────────
# These are always applied — not currently configurable via env vars.
STRIP_PATTERNS: list = [
    r"master\s+print\s+download",
    r"movie\s+request\s+group",
    r"channel\s+link",
]
