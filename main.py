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

# ====== CHANNEL GATE ======
CHANNEL = "@stylefug"
CHANNEL_URL = "https://t.me/stylefug"
# ==========================

TEXT = {
    "ru": {
        "locked": "studioFUG dating — закрытое комьюнити.\nПодпишись на официальный канал, чтобы продолжить.",
        "join": "Подписаться",
        "ijoined": "Я подписался",
        "welcome": "Добро пожаловать.\n\nДальше — создание профиля.",
        "not_sub": "Пока не вижу подписку."
    },
    "en": {
        "locked": "studioFUG dating is private.\nSubscribe to the official channel to continue.",
        "join": "Subscribe",
        "ijoined": "I subscribed",
        "welcome": "Welcome.\n\nNext: profile setup.",
        "not_sub": "Not subscribed yet."
    }
}

def get_lang(user_lang: str | None) -> str:
    return "ru" if (user_lang or "").startswith("ru") else "en"

def kb_locked(t: dict):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["join"], url=CHANNEL_URL)
    kb.button(text=t["ijoined"], callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()

async def is_subscribed(user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL, user_id)
        return m.status in {"member", "administrator", "creator"}
    except Exception:
        return False

@dp.message(CommandStart())
async def start(message: Message):
    lang = get_lang(getattr(message.from_user, "language_code", None))
    t = TEXT[lang]

    if not await is_subscribed(message.from_user.id):
        await message.answer(t["locked"], reply_markup=kb_locked(t))
        return

    await message.answer(t["welcome"])

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    lang = get_lang(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]

    if not await is_subscribed(call.from_user.id):
        await call.answer(t["not_sub"], show_alert=False)
        await call.message.edit_text(t["locked"], reply_markup=kb_locked(t))
        return

    await call.answer("OK", show_alert=False)
    await call.message.edit_text(t["welcome"])

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
