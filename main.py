import os
import logging
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN env var is missing")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ====== CONFIG (REPLACE THIS) ======
CHANNEL = "@stylefug"  # <-- put your channel username, e.g. "@studioFUG"
CHANNEL_URL = "https://t.me/stylefug"  # <-- put your channel link, e.g. "https://t.me/studioFUG"
# ===================================

TEXT = {
    "locked": (
        "studioFUG dating is private.\n"
        "Subscribe to the official channel to continue."
    ),
    "join": "Subscribe",
    "ijoined": "I subscribed",
    "welcome": (
        "Welcome.\n\n"
        "Next: profile setup."
    ),
    "cant_check": (
        "I can't verify your subscription yet.\n"
        "Admin check: the bot must be an admin of the channel."
    ),
}


def kb_locked():
    kb = InlineKeyboardBuilder()
    kb.button(text=TEXT["join"], url=CHANNEL_URL)
    kb.button(text=TEXT["ijoined"], callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()


async def is_subscribed(user_id: int) -> bool:
    """
    Works when the bot is an admin in the channel.
    """
    try:
        m = await bot.get_chat_member(CHANNEL, user_id)
        return m.status in {"member", "administrator", "creator"}
    except Exception:
        # usually means bot is not admin or channel name is wrong
        return False


@dp.message(CommandStart())
async def start(message: Message):
    ok = await is_subscribed(message.from_user.id)
    if not ok:
        await message.answer(TEXT["locked"], reply_markup=kb_locked())
        return
    await message.answer(TEXT["welcome"])


@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    ok = await is_subscribed(call.from_user.id)
    if not ok:
        await call.answer("Not subscribed yet.", show_alert=False)
        await call.message.edit_text(TEXT["locked"], reply_markup=kb_locked())
        return

    await call.answer("Access granted.", show_alert=False)
    await call.message.edit_text(TEXT["welcome"])


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
