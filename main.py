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

# ====== ADMIN ======
ADMIN_ID = 161015743  # <-- PUT YOUR TELEGRAM USER ID HERE (use /id in bot private chat)
# ===================

DB_PATH = "db.sqlite3"

TEXT = {
    "ru": {
        "locked": "studioFUG dating — закрытое комьюнити.\nПодпишись на @stylefug, чтобы продолжить.",
        "join": "Подписаться",
        "ijoined": "Я подписался",
        "welcome": "Добро пожаловать.",
        "menu": "Выбери действие:",
        "create": "Создать профиль",
        "browse": "Смотреть анкеты",
        "profile": "Мой профиль",
        "not_sub": "Пока не вижу подписку.",
        "need_profile": "Сначала создай профиль.",
        "banned": "Доступ закрыт.",
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
        "saved": "Профиль сохранён.",
        "bad_age": "Нужна цифра (например 26).",
        "no_photo": "Пришли фото как фото (не документ).",
        "no_more": "Пока анкет больше нет.",
        "like_sent": "💋 отправлен.",
        "you_got_like": "Тебя лайкнули. Посмотри профиль:",
        "pass": "❌ Не взаимно",
        "like_back": "💋 Лайкнуть в ответ",
        "match": "Матч.",
        "contact": "Контакт:",
        "no_username": "Нет username — смотри профиль в Telegram.",
        "report_sent": "Жалоба отправлена.",
        "comment_prompt": "Напиши короткий комментарий (до 300 символов).",
        "comment_sent": "Комментарий отправлен.",
        "comment_too_long": "Слишком длинно. До 300 символов.",
        "incoming_comment": "Тебе комментарий:",
        "admin_new_profile": "Новый профиль",
        "admin_report": "Жалоба",
        "admin_from": "От",
        "admin_on": "На",
        "admin_reason": "Причина: Пожаловаться",
        "admin_user_id": "user_id",
        "admin_banned_ok": "Забанен.",
        "admin_unbanned_ok": "Разбанен.",
        "admin_usage": "Используй: /ban <user_id> или /unban <user_id>"
    },
    "en": {
        "locked": "studioFUG dating is private.\nSubscribe to @stylefug to continue.",
        "join": "Subscribe",
        "ijoined": "I subscribed",
        "welcome": "Welcome.",
        "menu": "Choose an action:",
        "create": "Create profile",
        "browse": "Browse",
        "profile": "My profile",
        "not_sub": "Not subscribed yet.",
        "need_profile": "Create a profile first.",
        "banned": "Access denied.",
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
        "saved": "Profile saved.",
        "bad_age": "Send a number (e.g. 26).",
        "no_photo": "Send photo as photo (not document).",
        "no_more": "No more profiles.",
        "like_sent": "💋 sent.",
        "you_got_like": "Someone liked you. View profile:",
        "pass": "❌ Pass",
        "like_back": "💋 Like back",
        "match": "Match.",
        "contact": "Contact:",
        "no_username": "No username — check Telegram profile.",
        "report_sent": "Report sent.",
        "comment_prompt": "Write a short comment (up to 300 chars).",
        "comment_sent": "Comment sent.",
        "comment_too_long": "Too long. Up to 300 chars.",
        "incoming_comment": "You got a comment:",
        "admin_new_profile": "New profile",
        "admin_report": "Report",
        "admin_from": "From",
        "admin_on": "On",
        "admin_reason": "Reason: Report",
        "admin_user_id": "user_id",
        "admin_banned_ok": "Banned.",
        "admin_unbanned_ok": "Unbanned.",
        "admin_usage": "Use: /ban <user_id> or /unban <user_id>"
    }
}

def lang_of(code: str | None) -> str:
    return "ru" if (code or "").startswith("ru") else "en"

def allowed_genders_by_looking(looking: str) -> tuple[str, ...]:
    # men -> m + n
    # women -> f + n
    # all -> m + f + n
    if looking == "m":
        return ("m", "n")
    if looking == "f":
        return ("f", "n")
    return ("m", "f", "n")

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
    kb.button(text=t["g_n"], callback_data="g_n")
    kb.adjust(2, 1)
    return kb.as_markup()

def kb_looking(t: dict):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["l_m"], callback_data="l_m")
    kb.button(text=t["l_f"], callback_data="l_f")
    kb.button(text=t["l_all"], callback_data="l_all")
    kb.adjust(1)
    return kb.as_markup()

def kb_card(t: dict, uid: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="💋", callback_data=f"like:{uid}")
    kb.button(text="❌", callback_data="skip")
    kb.button(text="Пожаловаться" if t is TEXT["ru"] else "Report", callback_data=f"report:{uid}")
    kb.button(text="Прокомментировать" if t is TEXT["ru"] else "Comment", callback_data=f"comment:{uid}")
    kb.adjust(2, 2)
    return kb.as_markup()

def kb_incoming_like(t: dict, liker_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text=t["like_back"], callback_data=f"like:{liker_id}")
    kb.button(text=t["pass"], callback_data=f"pass:{liker_id}")
    kb.button(text="Пожаловаться" if t is TEXT["ru"] else "Report", callback_data=f"report:{liker_id}")
    kb.button(text="Прокомментировать" if t is TEXT["ru"] else "Comment", callback_data=f"comment:{liker_id}")
    kb.adjust(1, 1, 2)
    return kb.as_markup()

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
            name TEXT,
            age INTEGER,
            city TEXT,
            gender TEXT,
            looking TEXT,
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
        await db.execute("""
        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS pending_comment (
            user_id INTEGER PRIMARY KEY,
            target_id INTEGER NOT NULL
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

async def get_user_lang(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] in ("ru", "en") else "en"

async def get_username(user_id: int) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else None

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM bans WHERE user_id=?", (user_id,))
        return (await cur.fetchone()) is not None

async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO bans(user_id) VALUES(?)", (user_id,))
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM bans WHERE user_id=?", (user_id,))
        await db.commit()

async def profile_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM profiles WHERE user_id=?", (user_id,))
        return (await cur.fetchone()) is not None

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

async def is_subscribed(user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL, user_id)
        return m.status in {"member", "administrator", "creator"}
    except Exception:
        return False

async def pick_next_profile(viewer_id: int) -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT looking FROM profiles WHERE user_id=?", (viewer_id,))
        row = await cur.fetchone()
        if not row:
            return None
        genders = allowed_genders_by_looking(row[0])
        placeholders = ",".join(["?"] * len(genders))
        query = f"""
            SELECT p.user_id
            FROM profiles p
            WHERE p.user_id != ?
              AND p.gender IN ({placeholders})
              AND p.user_id NOT IN (SELECT to_user_id FROM likes WHERE from_user_id = ?)
        """
        cur = await db.execute(query, (viewer_id, *genders, viewer_id))
        ids = [r[0] for r in await cur.fetchall()]
        if not ids:
            return None
        return random.choice(ids)

async def send_profile_card(chat_id: int, lang: str, uid: int, markup):
    p = await get_profile(uid)
    if not p:
        return
    caption = f"{p['name']}, {p['age']}\n{p['city']}\n\n{p['bio']}"
    await bot.send_photo(chat_id=chat_id, photo=p["photo_file_id"], caption=caption, reply_markup=markup)

async def admin_new_profile(uid: int):
    if not ADMIN_ID:
        return
    p = await get_profile(uid)
    if not p:
        return
    lang = "ru"
    t = TEXT[lang]
    username = await get_username(uid)
    header = f"{t['admin_new_profile']} • {t['admin_user_id']}: {uid}"
    if username:
        header += f" • @{username}"
    try:
        await bot.send_message(ADMIN_ID, header)
        await bot.send_photo(
            ADMIN_ID,
            p["photo_file_id"],
            caption=f"{p['name']}, {p['age']}\n{p['city']}\n\n{p['bio']}"
        )
    except Exception:
        pass

async def admin_report(reporter_id: int, target_id: int):
    if not ADMIN_ID:
        return
    t = TEXT["ru"]
    rep_user = await get_username(reporter_id)
    tar_user = await get_username(target_id)
    p = await get_profile(target_id)
    header = f"{t['admin_report']} • {t['admin_from']}: {reporter_id}"
    if rep_user:
        header += f" (@{rep_user})"
    header += f"\n{t['admin_on']}: {target_id}"
    if tar_user:
        header += f" (@{tar_user})"
    header += f"\n{t['admin_reason']}"
    try:
        await bot.send_message(ADMIN_ID, header)
        if p:
            await bot.send_photo(
                ADMIN_ID,
                p["photo_file_id"],
                caption=f"{p['name']}, {p['age']}\n{p['city']}\n\n{p['bio']}"
            )
    except Exception:
        pass

async def notify_like(to_user_id: int, liker_id: int):
    if not await profile_exists(to_user_id):
        return
    lang = await get_user_lang(to_user_id)
    t = TEXT[lang]
    try:
        await bot.send_message(to_user_id, t["you_got_like"])
        await send_profile_card(to_user_id, lang, liker_id, kb_incoming_like(t, liker_id))
    except Exception:
        pass

async def notify_match(a_id: int, b_id: int):
    a_lang = await get_user_lang(a_id)
    b_lang = await get_user_lang(b_id)
    ta = TEXT[a_lang]
    tb = TEXT[b_lang]
    a_user = await get_username(a_id)
    b_user = await get_username(b_id)

    try:
        await bot.send_message(a_id, ta["match"])
        if b_user:
            await bot.send_message(a_id, f"{ta['contact']} @{b_user}")
        else:
            await bot.send_message(a_id, ta["no_username"])
    except Exception:
        pass

    try:
        await bot.send_message(b_id, tb["match"])
        if a_user:
            await bot.send_message(b_id, f"{tb['contact']} @{a_user}")
        else:
            await bot.send_message(b_id, tb["no_username"])
    except Exception:
        pass

# ---------- commands ----------
@dp.message(Command("id"))
async def get_id(message: Message):
    await message.answer(f"chat_id: {message.chat.id}")

@dp.message(Command("ban"))
async def ban_cmd(message: Message):
    lang = lang_of(getattr(message.from_user, "language_code", None))
    t = TEXT[lang]
    if message.from_user.id != ADMIN_ID:
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(t["admin_usage"])
        return
    await ban_user(int(parts[1]))
    await message.answer(t["admin_banned_ok"])

@dp.message(Command("unban"))
async def unban_cmd(message: Message):
    lang = lang_of(getattr(message.from_user, "language_code", None))
    t = TEXT[lang]
    if message.from_user.id != ADMIN_ID:
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(t["admin_usage"])
        return
    await unban_user(int(parts[1]))
    await message.answer(t["admin_unbanned_ok"])

# ---------- gate ----------
@dp.message(CommandStart())
async def start(message: Message):
    lang = lang_of(getattr(message.from_user, "language_code", None))
    await set_user(message.from_user.id, message.from_user.username, lang)
    t = TEXT[lang]

    if await is_banned(message.from_user.id):
        await message.answer(t["banned"])
        return

    if not await is_subscribed(message.from_user.id):
        await message.answer(t["locked"], reply_markup=kb_locked(t))
        return

    await message.answer(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

@dp.callback_query(F.data == "check_sub")
async def check_sub(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]

    if await is_banned(call.from_user.id):
        await call.answer()
        await call.message.edit_text(t["banned"])
        return

    if not await is_subscribed(call.from_user.id):
        await call.answer(t["not_sub"], show_alert=False)
        await call.message.edit_text(t["locked"], reply_markup=kb_locked(t))
        return

    await call.answer("OK", show_alert=False)
    await call.message.edit_text(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

# ---------- menu ----------
@dp.callback_query(F.data == "menu_create")
async def menu_create(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]
    await call.answer()

    if await is_banned(call.from_user.id):
        await call.message.answer(t["banned"])
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM draft WHERE user_id=?", (call.from_user.id,))
        await db.execute("INSERT OR REPLACE INTO state VALUES(?,?)", (call.from_user.id, "name"))
        await db.commit()
    await call.message.answer(t["ask_name"])

@dp.callback_query(F.data == "menu_profile")
async def my_profile(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]
    await call.answer()

    if await is_banned(call.from_user.id):
        await call.message.answer(t["banned"])
        return

    p = await get_profile(call.from_user.id)
    if not p:
        await call.message.answer(t["need_profile"])
        return

    caption = f"{p['name']}, {p['age']}\n{p['city']}\n\n{p['bio']}"
    await bot.send_photo(call.message.chat.id, p["photo_file_id"], caption=caption)

@dp.callback_query(F.data == "menu_browse")
async def browse(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]
    await call.answer()

    if await is_banned(call.from_user.id):
        await call.message.answer(t["banned"])
        return

    if not await profile_exists(call.from_user.id):
        await call.message.answer(t["need_profile"])
        return

    uid = await pick_next_profile(call.from_user.id)
    if not uid:
        await call.message.answer(t["no_more"])
        return

    await send_profile_card(call.message.chat.id, lang, uid, kb_card(t, uid))

# ---------- create profile flow ----------
@dp.message()
async def flow(message: Message):
    lang = lang_of(getattr(message.from_user, "language_code", None))
    await set_user(message.from_user.id, message.from_user.username, lang)
    t = TEXT[lang]

    if await is_banned(message.from_user.id):
        return

    # pending comment?
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT target_id FROM pending_comment WHERE user_id=?", (message.from_user.id,))
        pending = await cur.fetchone()
        if pending:
            target_id = pending[0]
            text = (message.text or "").strip()
            if not text:
                return
            if len(text) > 300:
                await message.answer(t["comment_too_long"])
                return

            p = await get_profile(message.from_user.id)
            if not p:
                await message.answer(t["need_profile"])
                await db.execute("DELETE FROM pending_comment WHERE user_id=?", (message.from_user.id,))
                await db.commit()
                return

            # send to target
            target_lang = await get_user_lang(target_id)
            tt = TEXT[target_lang]
            try:
                await bot.send_message(target_id, tt["incoming_comment"])
                await bot.send_photo(
                    target_id,
                    p["photo_file_id"],
                    caption=f"{p['name']}, {p['age']}\n{p['city']}\n\n{text}",
                    reply_markup=kb_incoming_like(tt, message.from_user.id)
                )
            except Exception:
                pass

            await db.execute("DELETE FROM pending_comment WHERE user_id=?", (message.from_user.id,))
            await db.commit()
            await message.answer(t["comment_sent"])
            return

    # normal profile creation steps
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
            await db.execute("INSERT OR REPLACE INTO draft(user_id,name) VALUES(?,?)", (message.from_user.id, name))
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
            await db.execute("UPDATE draft SET photo_file_id=? WHERE user_id=?", (file_id, message.from_user.id))
            await db.execute("UPDATE state SET step='bio' WHERE user_id=?", (message.from_user.id,))
            await db.commit()
            await message.answer(t["ask_bio"])
            return

        if step == "bio":
            bio = (message.text or "").strip()
            if not bio:
                await message.answer(t["ask_bio"]); return
            await db.execute("UPDATE draft SET bio=? WHERE user_id=?", (bio, message.from_user.id))

            await db.execute("""
                INSERT OR REPLACE INTO profiles
                SELECT user_id, name, age, city, gender, looking, photo_file_id, bio
                FROM draft WHERE user_id=?
            """, (message.from_user.id,))

            await db.execute("DELETE FROM state WHERE user_id=?", (message.from_user.id,))
            await db.execute("DELETE FROM draft WHERE user_id=?", (message.from_user.id,))
            await db.commit()

            await message.answer(t["saved"])
            await message.answer(t["menu"], reply_markup=kb_menu(t))

            # notify admin
            await admin_new_profile(message.from_user.id)
            return

@dp.callback_query(F.data.in_({"g_m", "g_f", "g_n"}))
async def pick_gender(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]
    await call.answer()

    if await is_banned(call.from_user.id):
        await call.message.answer(t["banned"])
        return

    g = {"g_m": "m", "g_f": "f", "g_n": "n"}[call.data]
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT step FROM state WHERE user_id=?", (call.from_user.id,))
        row = await cur.fetchone()
        if not row or row[0] != "gender":
            return
        await db.execute("UPDATE draft SET gender=? WHERE user_id=?", (g, call.from_user.id))
        await db.execute("UPDATE state SET step='looking' WHERE user_id=?", (call.from_user.id,))
        await db.commit()

    await call.message.answer(t["ask_looking"], reply_markup=kb_looking(t))

@dp.callback_query(F.data.in_({"l_m", "l_f", "l_all"}))
async def pick_looking(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]
    await call.answer()

    if await is_banned(call.from_user.id):
        await call.message.answer(t["banned"])
        return

    l = {"l_m": "m", "l_f": "f", "l_all": "all"}[call.data]
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT step FROM state WHERE user_id=?", (call.from_user.id,))
        row = await cur.fetchone()
        if not row or row[0] != "looking":
            return
        await db.execute("UPDATE draft SET looking=? WHERE user_id=?", (l, call.from_user.id))
        await db.execute("UPDATE state SET step='photo' WHERE user_id=?", (call.from_user.id,))
        await db.commit()

    await call.message.answer(t["ask_photo"])

# ---------- browse actions ----------
@dp.callback_query(F.data == "skip")
async def skip(call: CallbackQuery):
    await browse(call)

@dp.callback_query(F.data.startswith("like:"))
async def like(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]
    await call.answer()

    if await is_banned(call.from_user.id):
        await call.message.answer(t["banned"])
        return

    if not await profile_exists(call.from_user.id):
        await call.message.answer(t["need_profile"])
        return

    try:
        target_id = int(call.data.split(":", 1)[1])
    except Exception:
        return

    inserted = False
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT OR IGNORE INTO likes(from_user_id, to_user_id) VALUES(?,?)",
            (call.from_user.id, target_id)
        )
        inserted = (cur.rowcount == 1)
        await db.commit()

    if inserted:
        await notify_like(to_user_id=target_id, liker_id=call.from_user.id)

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM likes WHERE from_user_id=? AND to_user_id=?",
            (target_id, call.from_user.id)
        )
        mutual = (await cur.fetchone()) is not None

    if mutual:
        await notify_match(a_id=call.from_user.id, b_id=target_id)
    else:
        await call.message.answer(t["like_sent"])

    # next card
    uid = await pick_next_profile(call.from_user.id)
    if uid:
        await send_profile_card(call.message.chat.id, lang, uid, kb_card(t, uid))
    else:
        await call.message.answer(t["no_more"])

@dp.callback_query(F.data.startswith("pass:"))
async def pass_like(call: CallbackQuery):
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass

@dp.callback_query(F.data.startswith("report:"))
async def report(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]
    await call.answer()

    if await is_banned(call.from_user.id):
        await call.message.answer(t["banned"])
        return

    try:
        target_id = int(call.data.split(":", 1)[1])
    except Exception:
        return

    await admin_report(reporter_id=call.from_user.id, target_id=target_id)
    await call.message.answer(t["report_sent"])

@dp.callback_query(F.data.startswith("comment:"))
async def comment(call: CallbackQuery):
    lang = lang_of(getattr(call.from_user, "language_code", None))
    await set_user(call.from_user.id, call.from_user.username, lang)
    t = TEXT[lang]
    await call.answer()

    if await is_banned(call.from_user.id):
        await call.message.answer(t["banned"])
        return

    if not await profile_exists(call.from_user.id):
        await call.message.answer(t["need_profile"])
        return

    try:
        target_id = int(call.data.split(":", 1)[1])
    except Exception:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO pending_comment(user_id, target_id) VALUES(?,?)",
            (call.from_user.id, target_id)
        )
        await db.commit()

    await call.message.answer(t["comment_prompt"])

@dp.message(Command("help"))
async def help_cmd(message: Message):
    lang = lang_of(getattr(message.from_user, "language_code", None))
    await set_user(message.from_user.id, message.from_user.username, lang)
    t = TEXT[lang]
    await message.answer(f"{t['welcome']}\n{t['menu']}", reply_markup=kb_menu(t))

async def main():
    await db_init()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
