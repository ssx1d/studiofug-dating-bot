import os
import logging
import asyncio
import random
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
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

DB_PATH = "db.sqlite3"

# ---------- TEXTS ----------
TEXT = {
    "ru": {
        "locked": "studioFUG dating — закрытое комьюнити.\nПодпишись на официальный канал, чтобы продолжить.",
        "join": "Подписаться",
        "ijoined": "Я подписался",
        "welcome": "Добро пожаловать.",
        "menu": "Выбери действие:",
        "create": "Создать профиль",
        "browse": "Смотреть анкеты",
        "profile": "Мой профиль",
        "not_sub": "Пока не вижу подписку.",
        "need_profile": "Сначала создай профиль.",
        "ask_name": "Имя / никнейм?",
        "ask_age": "Возраст (числом)?",
        "ask_city": "Город?",
        "ask_gender": "Гендер:",
        "g_m": "Мужчина",
        "g_f": "Женщина",
        "g_n": "Не хочу говорить",
        "ask_looking": "Кто интересен?",
        "l_m": "Мужчины",
        "l_f": "Женщины",
        "l_all": "Все",
        "ask_photo": "Пришли 1 фото (именно как фото, не файл).",
        "ask_bio": "Коротко о себе (1–2 строки).",
        "saved": "Профиль сохранён. Можно смотреть анкеты.",
        "bad_age": "Нужна цифра (например 26).",
        "no_photo": "Пришли фото как фото (не документ).",
        "no_more": "Пока анкет больше нет.",
        "card_like": "❤️ Лайк",
        "card_skip": "❌ Пропуск",
        "matched": "Это взаимно. Матч!",
        "deleted": "Профиль удалён."
    },
    "en": {
        "locked": "studioFUG dating is private.\nSubscribe to the official channel to continue.",
        "join": "Subscribe",
        "ijoined": "I subscribed",
        "welcome": "Welcome.",
        "menu": "Choose an action:",
        "create": "Create profile",
        "browse": "Browse",
        "profile": "My profile",
        "not_sub": "Not subscribed yet.",
        "need_profile": "Create a profile first.",
        "ask_name": "Name / nickname?",
        "ask_age": "Age (number)?",
        "ask_city": "City?",
        "ask_gender": "Gender:",
        "g_m": "Man",
        "g_f": "Woman",
        "g_n": "Prefer not to say",
        "ask_looking": "Looking for?",
        "l_m": "Men",
        "l_f": "Women",
        "l_all": "All",
        "ask_photo": "Send 1 photo (as photo, not file).",
        "ask_bio": "Short bio (1–2 lines).",
        "saved": "Profile saved. You can browse.",
        "bad_age": "Send a number (e.g. 26).",
        "no_photo": "Send photo as photo (not document).",
        "no_more": "No more profiles.",
        "card_like": "❤️ Like",
        "card_skip": "❌ Skip",
        "matched": "It's a match!",
        "deleted": "Profile deleted."
    }
}

def lang_of(code: str | None) -> str:
    return "ru" if (code or "").startswith("ru") else "en"

# ---------- DB ----------
async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            city TEXT,
            gender TEXT,      -- m/f/n
            looking TEXT,     -- m/f/all (preference)
            photo_file_id TEXT,
            bio TEXT
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user_id INTEGER,
            to_user_id INTEGER,
            PRIMARY KEY (from_user_id, to_user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS state (
            user_id INTEGER PRIMARY KEY,
            step TEXT
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS draft (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            age INTEGER,
            city TEXT,
            gender TEXT,
            looking TEXT,
            photo_file_id TEXT,
            bio TEXT
        )""")
        await db.commit()

# ---------- HELPERS ----------
async def is_subscribed(user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL, user_id)
        return m.status in {"member", "administrator", "creator"}
    except Exception:
        return False

def kb_locked(t):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["join"], url=CHANNEL_URL)
    kb.button(text=t["ijoined"], callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()

def kb_menu(t):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["create"], callback_data="menu_create")
    kb.button(text=t["browse"], callback_data="menu_browse")
    kb.button(text=t["profile"], callback_data="menu_profile")
    kb.adjust(1)
    return kb.as_markup()

def kb_gender(t):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["g_m"], callback_data="g_m")
    kb.button(text=t["g_f"], callback_data="g_f")
    kb.button(text=t["g_n"], callback_data="g_n")
    kb.adjust(2, 1)
    return kb.as_markup()

def kb_looking(t):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["l_m"], callback_data="l_m")
    kb.button(text=t["l_f"], callback_data="l_f")
    kb.button(text=t["l_all"], callback_data="l_all")
    kb.adjust(1)
    return kb.as_markup()

def kb_card(t, uid):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["card_like"], callback_data=f"like:{uid}")
    kb.button(text=t["card_skip"], callback_data=f"skip:{uid}")
    kb.adjust(2)
    return kb.as_markup()

def allowed_genders_by_looking(looking: str) -> tuple[str, ...]:
    # required behavior:
    # men -> m + n
    # women -> f + n
    # all -> m + f + n
    if looking == "m":
        return ("m", "n")
    if looking == "f":
        return ("f", "n")
    return ("m", "f", "n")

async def pick_next_profile(viewer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # viewer profile
        cur = await db.execute("SELECT looking FROM profiles WHERE user_id=?", (viewer_id,))
        row = await cur.fetchone()
        if not row:
            return None
        looking = row[0]
        genders = allowed_genders_by_looking(looking)

        # candidates:
        # - not self
        # - not already liked by viewer
        # - gender in allowed set
        placeholders = ",".join(["?"] * len(genders))
        query = f"""
            SELECT p.user_id
            FROM profiles p
            WHERE p.user_id != ?
              AND p.gender IN ({placeholders})
              AND p.user_id NOT IN (
                    SELECT to_user_id FROM likes WHERE from_user_id = ?
              )
        """
        cur = await db.execute(query, (viewer_id, *genders, viewer_id))
        ids = [r[0] for r in await cur.fetchall()]
        if not ids:
            return None
        return random.choice(ids)

async def get_profile(uid: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            SELECT name, age, city, gender, looking, photo_file_id, bio
            FROM profiles WHERE user_id=?
        """, (uid,))
        row = await cur.fetchone()
        if not row:
            return None
        keys = ["name", "age", "city", "gender", "looking", "photo_file_id", "bio"]
        return dict(zip(keys, row))

def gender_badge(lang: str, g: str) -> str:
    # minimal, clean
    if g == "n":
        return "—"
    if lang == "ru":
        return "М" if g == "m" else "Ж"
    return "M" if g == "m" else "F"

async def send_card(chat_id: int, lang: str, uid: int):
    t = TEXT[lang]
    p = await get_profile(uid)
    if not p:
        return
    caption = f"{p['name']}, {p['age']}\n{p['city']}\n\n{p['bio']}"
    await bot.send_photo(
        chat_id=chat_id,
        photo=p["photo_file_id"],
        caption=caption,
        reply_markup=kb_card(t, uid),
    )

# ---------- START ----------
@dp.message(CommandStart())
async def start(message: Message):
    lang = lang_of(message.from_user.language_code)
    t = TEXT[lang]

    if not await is_subscribed(message.from_user.id):
        await message.answer(t["locked"], reply_markup=kb_locked(t))
        return

    await message.answer(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    lang = lang_of(call.from_user.language_code)
    t = TEXT[lang]
    if not await is_subscribed(call.from_user.id):
        await call.message.edit_text(t["locked"], reply_markup=kb_locked(t))
        return
    await call.message.edit_text(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

# ---------- CREATE PROFILE ----------
@dp.callback_query(F.data == "menu_create")
async def menu_create(call: CallbackQuery):
    lang = lang_of(call.from_user.language_code)
    t = TEXT[lang]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM draft WHERE user_id=?", (call.from_user.id,))
        await db.execute("INSERT OR REPLACE INTO state VALUES(?,?)", (call.from_user.id, "name"))
        await db.commit()
    await call.answer()
    await call.message.answer(t["ask_name"])

@dp.message()
async def flow(message: Message):
    lang = lang_of(message.from_user.language_code)
    t = TEXT[lang]

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT step FROM state WHERE user_id=?", (message.from_user.id,))
        row = await cur.fetchone()
        if not row:
            return
        step = row[0]

        if step == "name":
            name = (message.text or "").strip()
            if not name:
                await message.answer(t["ask_name"]); return
            await db.execute("INSERT OR REPLACE INTO draft(user_id,name) VALUES(?,?)",
                             (message.from_user.id, name))
            await db.execute("UPDATE state SET step='age' WHERE user_id=?", (message.from_user.id,))
            await db.commit()
            await message.answer(t["ask_age"])
            return

        if step == "age":
            txt = (message.text or "").strip()
            if not txt.isdigit():
                await message.answer(t["bad_age"]); return
            age = int(txt)
            if age < 18 or age > 99:
                await message.answer(t["bad_age"]); return
            await db.execute("UPDATE draft SET age=? WHERE user_id=?", (age, message.from_user.id))
            await db.execute("UPDATE state SET step='city' WHERE user_id=?", (message.from_user.id,))
            await db.commit()
            await message.answer(t["ask_city"])
            return

        if step == "city":
            city = (message.text or "").strip()
            if not city:
                await message.answer(t["ask_city"]); return
            await db.execute("UPDATE draft SET city=? WHERE user_id=?", (city, message.from_user.id))
            await db.execute("UPDATE state SET step='gender' WHERE user_id=?", (message.from_user.id,))
            await db.commit()
            await message.answer(t["ask_gender"], reply_markup=kb_gender(t))
            return

        if step == "photo":
            if not message.photo:
                await message.answer(t["no_photo"]); return
            file_id = message.photo[-1].file_id
            await db.execute("UPDATE draft SET photo_file_id=? WHERE user_id=?",
                             (file_id, message.from_user.id))
            await db.execute("UPDATE state SET step='bio' WHERE user_id=?", (message.from_user.id,))
            await db.commit()
            await message.answer(t["ask_bio"])
            return

        if step == "bio":
            bio = (message.text or "").strip()
            if not bio:
                await message.answer(t["ask_bio"]); return
            await db.execute("UPDATE draft SET bio=? WHERE user_id=?", (bio, message.from_user.id))

            # Save profile
            await db.execute("""
                INSERT OR REPLACE INTO profiles
                SELECT user_id, name, age, city, gender, looking, photo_file_id, bio
                FROM draft WHERE user_id=?
            """, (message.from_user.id,))

            await db.execute("DELETE FROM state WHERE user_id=?", (message.from_user.id,))
            await db.execute("DELETE FROM draft WHERE user_id=?", (message.from_user.id,))
            await db.commit()

            await message.answer(t["saved"], reply_markup=kb_menu(t))
            return

@dp.callback_query(F.data.in_({"g_m", "g_f", "g_n"}))
async def pick_gender(call: CallbackQuery):
    lang = lang_of(call.from_user.language_code)
    t = TEXT[lang]
    g = {"g_m": "m", "g_f": "f", "g_n": "n"}[call.data]

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT step FROM state WHERE user_id=?", (call.from_user.id,))
        row = await cur.fetchone()
        if not row or row[0] != "gender":
            await call.answer()
            return

        await db.execute("UPDATE draft SET gender=? WHERE user_id=?", (g, call.from_user.id))
        await db.execute("UPDATE state SET step='looking' WHERE user_id=?", (call.from_user.id,))
        await db.commit()

    await call.answer()
    await call.message.answer(t["ask_looking"], reply_markup=kb_looking(t))

@dp.callback_query(F.data.in_({"l_m", "l_f", "l_all"}))
async def pick_looking(call: CallbackQuery):
    lang = lang_of(call.from_user.language_code)
    t = TEXT[lang]
    l = {"l_m": "m", "l_f": "f", "l_all": "all"}[call.data]

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT step FROM state WHERE user_id=?", (call.from_user.id,))
        row = await cur.fetchone()
        if not row or row[0] != "looking":
            await call.answer()
            return

        await db.execute("UPDATE draft SET looking=? WHERE user_id=?", (l, call.from_user.id))
        await db.execute("UPDATE state SET step='photo' WHERE user_id=?", (call.from_user.id,))
        await db.commit()

    await call.answer()
    await call.message.answer(t["ask_photo"])

# ---------- BROWSE ----------
@dp.callback_query(F.data == "menu_browse")
async def browse(call: CallbackQuery):
    lang = lang_of(call.from_user.language_code)
    t = TEXT[lang]

    # Ensure viewer has profile
    viewer_profile = await get_profile(call.from_user.id)
    if not viewer_profile:
        await call.answer()
        await call.message.answer(t["need_profile"])
        return

    uid = await pick_next_profile(call.from_user.id)
    await call.answer()
    if not uid:
        await call.message.answer(t["no_more"])
        return

    await send_card(call.message.chat.id, lang, uid)

# ---------- LIKE / SKIP ----------
@dp.callback_query(F.data.startswith("skip:"))
async def skip(call: CallbackQuery):
    lang = lang_of(call.from_user.language_code)
    t = TEXT[lang]

    viewer_profile = await get_profile(call.from_user.id)
    if not viewer_profile:
        await call.answer()
        await call.message.answer(t["need_profile"])
        return

    uid = await pick_next_profile(call.from_user.id)
    await call.answer()
    if not uid:
        await call.message.answer(t["no_more"])
        return
    await send_card(call.message.chat.id, lang, uid)

@dp.callback_query(F.data.startswith("like:"))
async def like(call: CallbackQuery):
    lang = lang_of(call.from_user.language_code)
    t = TEXT[lang]

    viewer_profile = await get_profile(call.from_user.id)
    if not viewer_profile:
        await call.answer()
        await call.message.answer(t["need_profile"])
        return

    try:
        target_id = int(call.data.split(":", 1)[1])
    except Exception:
        await call.answer()
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO likes(from_user_id, to_user_id) VALUES(?,?)",
                         (call.from_user.id, target_id))
        await db.commit()

        # mutual?
        cur = await db.execute("SELECT 1 FROM likes WHERE from_user_id=? AND to_user_id=?",
                               (target_id, call.from_user.id))
        mutual = (await cur.fetchone()) is not None

    await call.answer()
    if mutual:
        await call.message.answer(t["matched"])

    # Next
    uid = await pick_next_profile(call.from_user.id)
    if not uid:
        await call.message.answer(t["no_more"])
        return
    await send_card(call.message.chat.id, lang, uid)

# ---------- PROFILE ----------
@dp.callback_query(F.data == "menu_profile")
async def my_profile(call: CallbackQuery):
    lang = lang_of(call.from_user.language_code)
    t = TEXT[lang]

    p = await get_profile(call.from_user.id)
    await call.answer()
    if not p:
        await call.message.answer(t["need_profile"])
        return

    caption = f"{p['name']}, {p['age']}\n{p['city']}\n{gender_badge(lang, p['gender'])}\n\n{p['bio']}"
    await bot.send_photo(call.message.chat.id, p["photo_file_id"], caption=caption)

@dp.message(Command("help"))
async def help_cmd(message: Message):
    lang = lang_of(message.from_user.language_code)
    t = TEXT[lang]
    await message.answer(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

# ---------- MAIN ----------
async def main():
    await db_init()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
