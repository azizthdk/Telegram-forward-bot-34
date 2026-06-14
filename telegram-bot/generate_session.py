"""
Run this ONCE to generate your SESSION_STRING.

In Railway Console:
    cd telegram-bot
    python generate_session.py

It will ask for your phone number and OTP, then print the SESSION_STRING.
Copy the printed string and add it as a Railway environment variable:
    Key:   SESSION_STRING
    Value: <the long string printed below>
"""
import asyncio
import os

async def main():
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        print("Installing telethon...")
        import subprocess
        subprocess.run(["pip", "install", "telethon"], check=True)
        from telethon import TelegramClient
        from telethon.sessions import StringSession

    api_id   = int(os.environ.get("TELEGRAM_API_ID", "0"))
    api_hash = os.environ.get("TELEGRAM_API_HASH", "")

    if not api_id or not api_hash:
        print("❌  TELEGRAM_API_ID and TELEGRAM_API_HASH env vars are not set.")
        print("    Make sure you have added them in Railway → Variables.")
        return

    print(f"\n📱  Logging in with API_ID={api_id}")
    print("    You will receive an OTP in your Telegram Saved Messages.\n")

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()

    session_string = client.session.save()
    await client.disconnect()

    print("\n" + "="*60)
    print("✅  SESSION_STRING generated successfully!")
    print("="*60)
    print("\nCopy EVERYTHING between the lines below:\n")
    print("---SESSION_STRING-START---")
    print(session_string)
    print("---SESSION_STRING-END---")
    print("\nAdd it to Railway → your service → Variables:")
    print("  Key:   SESSION_STRING")
    print("  Value: (paste the string above)\n")

asyncio.run(main())
