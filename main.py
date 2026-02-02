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

# --- i18n: RU if Telegram is ru*, else EN ---
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
        "delete": "Удалить профиль",
        "back": "Назад",
        "not_sub": "Пока не вижу подписку.",
        "need_profile": "Сначала создай профиль.",
        "creating": "Создаём профиль.",
        "ask_name": "Имя / никнейм?",
        "ask_age": "Возраст (числом)?",
        "ask_city": "Город?",
        "ask_gender": "Ты кто?",
        "g_m": "Мужчина",
        "g_f": "Женщина",
        "ask_looking": "Кто интересен?",
        "l_m": "Мужчины",
        "l_f": "Женщины",
        "l_all": "Все",
        "ask_photo": "Пришли 1 фото (как фото, не файл).",
        "ask_bio": "Коротко о себе (1–2 строки, без ссылок).",
        "saved": "Профиль сохранён. Можно смотреть анкеты.",
        "bad_age": "Нужна цифра (например 26).",
        "no_photo": "Пришли фото именно как фото (не документ).",
        "no_more": "Пока анкет больше нет. Попробуй позже.",
        "card_like": "❤️ Лайк",
        "card_skip": "❌ Пропуск",
        "matched": "Это взаимно. Матч!",
        "you_got_like": "Тебя лайкнули.",
        "mutual": "У вас матч. Можно написать друг другу:",
        "no_username": "У пользователя скрыт username. Напиши ему через Telegram из профиля (если доступно).",
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
        "delete": "Delete profile",
        "back": "Back",
        "not_sub": "Not subscribed yet.",
        "need_profile": "Create a profile first.",
        "creating": "Creating your profile.",
        "ask_name": "Name / nickname?",
        "ask_age": "Age (number)?",
        "ask_city": "City?",
        "ask_gender": "You are?",
        "g_m": "Man",
        "g_f": "Woman",
        "ask_looking": "Looking for?",
        "l_m": "Men",
        "l_f": "Women",
        "l_all": "All",
        "ask_photo": "Send 1 photo (as a photo, not a file).",
        "ask_bio": "Short bio (1–2 lines, no links).",
        "saved": "Profile saved. You can browse now.",
        "bad_age": "Please send a number (e.g. 26).",
        "no_photo": "Send a photo as a photo (not a document).",
        "no_more": "No more profiles right now. Try later.",
        "card_like": "❤️ Like",
        "card_skip": "❌ Skip",
        "matched": "It's mutual. Match!",
        "you_got_like": "Someone liked you.",
        "mutual": "You matched. You can contact each other:",
        "no_username": "User has no public username. Contact via Telegram profile if available.",
        "deleted": "Profile deleted."
    }
}

def lang_of(user_lang: str | None) -> str:
    return "ru" if (user_lang or "").startswith("ru") else "en"

# ----- simple per-user flow state in DB -----
# states: none, name, age, city, gender, looking, photo, bio
# also store draft fields in a drafts table

async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            lang TEXT
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            city TEXT NOT NULL,
            gender TEXT NOT NULL,         -- 'm'/'f'
            looking TEXT NOT NULL,        -- 'm'/'f'/'all'
            photo_file_id TEXT NOT NULL,
            bio TEXT NOT NULL
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            from_user_id INTEGER NOT NULL,
            to_user_id INTEGER NOT NULL,
            PRIMARY KEY (from_user_id, to_user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS state (
            user_id INTEGER PRIMARY KEY,
            step TEXT NOT NULL
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

async def set_user(user_id: int, username: str | None, lang: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users(user_id, username, lang) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, lang=excluded.lang",
            (user_id, username, lang),
        )
        await db.commit()

async def set_step(user_id: int, step: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO state(user_id, step) VALUES(?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET step=excluded.step",
            (user_id, step),
        )
        await db.commit()

async def get_step(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT step FROM state WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else "none"

async def clear_step(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM state WHERE user_id=?", (user_id,))
        await db.commit()

async def draft_set(user_id: int, **kwargs):
    cols = []
    vals = []
    for k, v in kwargs.items():
        cols.append(k)
        vals.append(v)
    if not cols:
        return
    sets = ", ".join([f"{c}=?" for c in cols])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO draft(user_id) VALUES(?) ON CONFLICT(user_id) DO NOTHING",
            (user_id,),
        )
        await db.execute(f"UPDATE draft SET {sets} WHERE user_id=?", (*vals, user_id))
        await db.commit()

async def draft_get(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, age, city, gender, looking, photo_file_id, bio FROM draft WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return {}
        keys = ["name", "age", "city", "gender", "looking", "photo_file_id", "bio"]
        return dict(zip(keys, row))

async def draft_clear(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM draft WHERE user_id=?", (user_id,))
        await db.commit()

async def profile_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM profiles WHERE user_id=?", (user_id,))
        return (await cur.fetchone()) is not None

async def save_profile(user_id: int, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO profiles(user_id, name, age, city, gender, looking, photo_file_id, bio) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "name=excluded.name, age=excluded.age, city=excluded.city, gender=excluded.gender, "
            "looking=excluded.looking, photo_file_id=excluded.photo_file_id, bio=excluded.bio",
            (
                user_id, data["name"], data["age"], data["city"],
                data["gender"], data["looking"], data["photo_file_id"], data["bio"]
            )
        )
        await db.commit()

async def get_profile(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT name, age, city, gender, looking, photo_file_id, bio FROM profiles WHERE user_id=?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row:
            return None
        keys = ["name", "age", "city", "gender", "looking", "photo_file_id", "bio"]
        return dict(zip(keys, row))

async def delete_profile(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM profiles WHERE user_id=?", (user_id,))
        await db.execute("DELETE FROM likes WHERE from_user_id=? OR to_user_id=?", (user_id, user_id))
        await db.commit()

async def is_subscribed(user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL, user_id)
        return m.status in {"member", "administrator", "creator"}
    except Exception:
        return False

def kb_locked(t: dict):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["join"], url=CHANNEL_URL)
    kb.button(text=t["ijoined"], callback_data="check_sub")
    kb.adjust(1)
    return kb.as_markup()

def kb_menu(t: dict):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["create"], callback_data="menu_create")
    kb.button(text=t["browse"], callback_data="menu_browse")
    kb.button(text=t["profile"], callback_data="menu_profile")
    kb.adjust(1)
    return kb.as_markup()

def kb_gender(t: dict):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["g_m"], callback_data="g_m")
    kb.button(text=t["g_f"], callback_data="g_f")
    kb.adjust(2)
    return kb.as_markup()

def kb_looking(t: dict):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["l_m"], callback_data="l_m")
    kb.button(text=t["l_f"], callback_data="l_f")
    kb.button(text=t["l_all"], callback_data="l_all")
    kb.adjust(1)
    return kb.as_markup()

def kb_profile_actions(t: dict):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["delete"], callback_data="profile_delete")
    kb.button(text=t["back"], callback_data="menu_back")
    kb.adjust(1)
    return kb.as_markup()

def kb_card(t: dict, target_user_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["card_like"], callback_data=f"like:{target_user_id}")
    kb.button(text=t["card_skip"], callback_data=f"skip:{target_user_id}")
    kb.adjust(2)
    return kb.as_markup()

async def pick_next_profile(viewer_id: int):
    me = await get_profile(viewer_id)
    if not me:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        # Exclude self and already liked/skipped target by checking likes table (only likes stored; skips not stored)
        # We'll still avoid showing someone you already liked.
        cur = await db.execute("""
            SELECT p.user_id
            FROM profiles p
            WHERE p.user_id != ?
              AND p.user_id NOT IN (SELECT to_user_id FROM likes WHERE from_user_id = ?)
        """, (viewer_id, viewer_id))
        ids = [r[0] for r in await cur.fetchall()]
        if not ids:
            return None

        # Apply basic "looking" filter from viewer:
        # if viewer looking == 'm' show only men; 'f' show only women; 'all' show all
        looking = me["looking"]
        if looking in ("m", "f"):
            cur2 = await db.execute("""
                SELECT user_id FROM profiles
                WHERE user_id IN (%s) AND gender = ?
            """ % (",".join(["?"] * len(ids))), (*ids, looking))
            ids2 = [r[0] for r in await cur2.fetchall()]
            ids = ids2

        if not ids:
            return None

    target_id = random.choice(ids)
    return target_id

def gender_label(lang: str, g: str) -> str:
    if lang == "ru":
        return "М" if g == "m" else "Ж"
    return "M" if g == "m" else "F"

def looking_label(lang: str, l: str) -> str:
    if lang == "ru":
        return {"m": "мужчины", "f": "женщины", "all": "все"}[l]
    return {"m": "men", "f": "women", "all": "all"}[l]

async def send_card(viewer_msg_or_call, viewer_lang: str, target_user_id: int):
    t = TEXT[viewer_lang]
    p = await get_profile(target_user_id)
    if not p:
        return

    caption = (
        f"{p['name']}, {p['age']}\n"
        f"{p['city']}\n\n"
        f"{p['bio']}"
    )
    await bot.send_photo(
        chat_id=viewer_msg_or_call.chat.id if isinstance(viewer_msg_or_call, Message) else viewer_msg_or_call.message.chat.id,
        photo=p["photo_file_id"],
        caption=caption,
        reply_markup=kb_card(t, target_user_id),
    )

# ---------------- HANDLERS ----------------

@dp.message(CommandStart())
async def start(message: Message):
    lang = lang_of(getattr(message.from_user, "language_code", None))
    await set_user(message.from_user.id, message.from_user.username, lang)
    t = TEXT[lang]

    if not await is_subscribed(message.from_user.id):
        await message.answer(t["locked"], reply_markup=kb_locked(t))
        return

    await message.answer(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]

    if not await is_subscribed(call.from_user.id):
        await call.answer(t["not_sub"], show_alert=False)
        await call.message.edit_text(t["locked"], reply_markup=kb_locked(t))
        return

    await call.answer("OK", show_alert=False)
    await call.message.edit_text(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

@dp.callback_query(F.data == "menu_back")
async def menu_back(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    await call.answer()
    await call.message.edit_text(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

@dp.callback_query(F.data == "menu_create")
async def menu_create(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    await call.answer()
    await draft_clear(call.from_user.id)
    await set_step(call.from_user.id, "name")
    await call.message.answer(f"{t['creating']}\n\n{t['ask_name']}")

@dp.callback_query(F.data == "menu_profile")
async def menu_profile(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    await call.answer()

    p = await get_profile(call.from_user.id)
    if not p:
        await call.message.answer(t["need_profile"])
        return

    text = (
        f"{p['name']}, {p['age']}\n"
        f"{p['city']}\n"
        f"{gender_label(lang, p['gender'])} • {looking_label(lang, p['looking'])}\n\n"
        f"{p['bio']}"
    )
    await call.message.answer(text, reply_markup=kb_profile_actions(t))

@dp.callback_query(F.data == "profile_delete")
async def profile_delete(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    await call.answer()
    await delete_profile(call.from_user.id)
    await call.message.answer(t["deleted"])

@dp.callback_query(F.data == "menu_browse")
async def menu_browse(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    await call.answer()

    if not await profile_exists(call.from_user.id):
        await call.message.answer(t["need_profile"])
        return

    target_id = await pick_next_profile(call.from_user.id)
    if not target_id:
        await call.message.answer(t["no_more"])
        return

    await send_card(call, lang, target_id)

# --- profile creation flow ---
@dp.message()
async def profile_flow(message: Message):
    lang = lang_of(getattr(message.from_user, "language_code", None))
    t = TEXT[lang]
    step = await get_step(message.from_user.id)

    if step == "none":
        return  # ignore regular messages

    if step == "name":
        name = (message.text or "").strip()
        if not name:
            await message.answer(t["ask_name"])
            return
        await draft_set(message.from_user.id, name=name)
        await set_step(message.from_user.id, "age")
        await message.answer(t["ask_age"])
        return

    if step == "age":
        txt = (message.text or "").strip()
        if not txt.isdigit():
            await message.answer(t["bad_age"])
            return
        age = int(txt)
        if age < 18 or age > 99:
            await message.answer(t["bad_age"])
            return
        await draft_set(message.from_user.id, age=age)
        await set_step(message.from_user.id, "city")
        await message.answer(t["ask_city"])
        return

    if step == "city":
        city = (message.text or "").strip()
        if not city:
            await message.answer(t["ask_city"])
            return
        await draft_set(message.from_user.id, city=city)
        await set_step(message.from_user.id, "gender")
        await message.answer(t["ask_gender"], reply_markup=kb_gender(t))
        return

    if step == "photo":
        if not message.photo:
            await message.answer(t["no_photo"])
            return
        file_id = message.photo[-1].file_id
        await draft_set(message.from_user.id, photo_file_id=file_id)
        await set_step(message.from_user.id, "bio")
        await message.answer(t["ask_bio"])
        return

    if step == "bio":
        bio = (message.text or "").strip()
        if not bio:
            await message.answer(t["ask_bio"])
            return
        await draft_set(message.from_user.id, bio=bio)
        data = await draft_get(message.from_user.id)

        # save
        await save_profile(message.from_user.id, data)
        await draft_clear(message.from_user.id)
        await clear_step(message.from_user.id)

        await message.answer(t["saved"])
        await message.answer(f"{t['menu']}", reply_markup=kb_menu(t))
        return

@dp.callback_query(F.data.in_({"g_m", "g_f"}))
async def pick_gender(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    step = await get_step(call.from_user.id)
    if step != "gender":
        await call.answer()
        return

    gender = "m" if call.data == "g_m" else "f"
    await draft_set(call.from_user.id, gender=gender)
    await set_step(call.from_user.id, "looking")
    await call.answer()
    await call.message.answer(t["ask_looking"], reply_markup=kb_looking(t))

@dp.callback_query(F.data.in_({"l_m", "l_f", "l_all"}))
async def pick_looking(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    step = await get_step(call.from_user.id)
    if step != "looking":
        await call.answer()
        return

    looking = {"l_m": "m", "l_f": "f", "l_all": "all"}[call.data]
    await draft_set(call.from_user.id, looking=looking)
    await set_step(call.from_user.id, "photo")
    await call.answer()
    await call.message.answer(t["ask_photo"])

# --- like/skip flow ---
@dp.callback_query(F.data.startswith("skip:"))
async def skip_profile(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    await call.answer()

    if not await profile_exists(call.from_user.id):
        await call.message.answer(t["need_profile"])
        return

    target_id = await pick_next_profile(call.from_user.id)
    if not target_id:
        await call.message.answer(t["no_more"])
        return
    await send_card(call, lang, target_id)

@dp.callback_query(F.data.startswith("like:"))
async def like_profile(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    t = TEXT[lang]
    await call.answer()

    if not await profile_exists(call.from_user.id):
        await call.message.answer(t["need_profile"])
        return

    try:
        target_id = int(call.data.split(":", 1)[1])
    except Exception:
        return

    # store like
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO likes(from_user_id, to_user_id) VALUES(?,?)",
            (call.from_user.id, target_id)
        )
        await db.commit()

        # check mutual
        cur = await db.execute(
            "SELECT 1 FROM likes WHERE from_user_id=? AND to_user_id=?",
            (target_id, call.from_user.id)
        )
        mutual = (await cur.fetchone()) is not None

    if mutual:
        await call.message.answer(t["matched"])

        # notify both with usernames if possible
        u1 = call.from_user.username
        u2_profile = await get_profile(target_id)  # just to ensure exists
        # fetch stored usernames
        async with aiosqlite.connect(DB_PATH) as db:
            cur1 = await db.execute("SELECT username FROM users WHERE user_id=?", (call.from_user.id,))
            r1 = await cur1.fetchone()
            cur2 = await db.execute("SELECT username FROM users WHERE user_id=?", (target_id,))
            r2 = await cur2.fetchone()
        u1 = (r1[0] if r1 else None) or call.from_user.username
        u2 = (r2[0] if r2 else None)

        # message viewer
        if u2:
            await call.message.answer(f"{t['mutual']}\n@{u2}")
        else:
            await call.message.answer(t["no_username"])

        # message other side
        # determine other side lang (fallback to EN)
        other_lang = "en"
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT lang FROM users WHERE user_id=?", (target_id,))
            r = await cur.fetchone()
            if r and r[0] in ("ru", "en"):
                other_lang = r[0]
        ot = TEXT[other_lang]

        try:
            await bot.send_message(target_id, ot["matched"])
            if u1:
                await bot.send_message(target_id, f"{ot['mutual']}\n@{u1}")
            else:
                await bot.send_message(target_id, ot["no_username"])
        except Exception:
            pass
    else:
        # optional: notify "you got like" (can be noisy; keep minimal)
        pass

    # next card
    next_id = await pick_next_profile(call.from_user.id)
    if not next_id:
        await call.message.answer(t["no_more"])
        return
    await send_card(call, lang, next_id)

@dp.message(Command("help"))
async def help_cmd(message: Message):
    lang = lang_of(getattr(message.from_user, "language_code", None))
    t = TEXT[lang]
    await message.answer(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

async def main():
    await db_init()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
