# Lazy-import UserBot so that importing userbot.forwarder (used by the server)
# does NOT drag in the full CLI codebase (colorama, interactive menu, etc.).
# Use: from userbot.bot import UserBot
def __getattr__(name):
    if name == "UserBot":
        from .bot import UserBot as _UB
        return _UB
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
