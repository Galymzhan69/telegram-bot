import logging
import datetime
import sqlite3
import html
import time
import os

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# ================== TOKEN ==================
# Бот токенін осы жерге жазыңыз немесе Render-дің Environment Variable бөліміне BOT_TOKEN болып қосыңыз
BOT_TOKEN = os.getenv("8178654145:AAE7214atC4dbeACowg5sMbUAXlo039LGhY", "8178654145:AAE7214atC4dbeACowg5sMbUAXlo039LGhY")

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ================== DATABASE ==================
DB_NAME = "bot_users.db"
KZ_TZ = datetime.timezone(datetime.timedelta(hours=5))


def get_now_iso():
    return datetime.datetime.now(KZ_TZ).isoformat(timespec="seconds")


def format_datetime(dt_text):
    if not dt_text:
        return "Белгісіз"

    try:
        dt = datetime.datetime.fromisoformat(dt_text)
        return dt.astimezone(KZ_TZ).strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return dt_text


def safe_text(value, default="жоқ"):
    if value is None or value == "":
        return default
    return html.escape(str(value))


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            language_code TEXT,
            is_bot INTEGER,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            saved_text TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_user_activity(update: Update, increase_message_count=True):
    user = update.effective_user

    if not user:
        return

    now = get_now_iso()
    message_add = 1 if increase_message_count else 0

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users (
            user_id,
            first_name,
            last_name,
            username,
            language_code,
            is_bot,
            first_seen,
            last_seen,
            message_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(user_id) DO UPDATE SET
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            username = excluded.username,
            language_code = excluded.language_code,
            is_bot = excluded.is_bot,
            last_seen = excluded.last_seen,
            message_count = users.message_count + ?
    """, (
        user.id,
        user.first_name,
        user.last_name,
        user.username,
        user.language_code,
        1 if user.is_bot else 0,
        now,
        now,
        message_add,
        message_add
    ))

    conn.commit()
    conn.close()


def get_user_data(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)

    return None


def set_saved_text(user_id: int, saved_text: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET saved_text = ? WHERE user_id = ?",
        (saved_text, user_id)
    )

    conn.commit()
    conn.close()


# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_activity(update)
    user = update.effective_user

    await update.message.reply_html(
        f"Сәлеметсіз бе, {user.mention_html()}! 👋\n\n"
        "Мен сіздің көмекші ботыңызбын.\n"
        "Командаларды көру үшін /help жіберіңіз."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_activity(update)

    help_text = (
        "<b>📌 Негізгі командалар:</b>\n\n"
        "🚀 /start - Ботты бастау\n"
        "ℹ️ /help - Көмек көрсету\n"
        "👤 /profile - Профильді көру\n"
        "💾 /save_my_text [мәтін] - Мәтінді сақтау\n"
        "📜 /my_text - Сақталған мәтінді көру\n\n"
        "<b>Мысал:</b>\n"
        "<code>/save_my_text Менің сүйікті кітабым - Абай жолы</code>"
    )

    await update.message.reply_html(help_text)


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_activity(update)

    user = update.effective_user
    chat = update.effective_chat

    user_data = get_user_data(user.id)

    if not user_data:
        await update.message.reply_text(
            "Профиль табылмады. /start командасын басып көріңіз."
        )
        return

    first_name = safe_text(user_data.get("first_name"))
    last_name = safe_text(user_data.get("last_name"))
    username = user_data.get("username")
    language_code = safe_text(user_data.get("language_code"))

    is_bot = "Иә" if user_data.get("is_bot") == 1 else "Жоқ"

    if username:
        username_text = f"@{safe_text(username)}"
    else:
        username_text = "жоқ"

    full_name_parts = []
    if user_data.get("first_name"):
        full_name_parts.append(user_data.get("first_name"))
    if user_data.get("last_name"):
        full_name_parts.append(user_data.get("last_name"))

    full_name = (
        safe_text(" ".join(full_name_parts))
        if full_name_parts
        else "жоқ"
    )

    first_seen = format_datetime(user_data.get("first_seen"))
    last_seen = format_datetime(user_data.get("last_seen"))
    message_count = user_data.get("message_count", 0)

    saved_text_status = (
        "Бар ✅" if user_data.get("saved_text") else "Жоқ ❌"
    )

    current_time = datetime.datetime.now(
        KZ_TZ
    ).strftime("%d.%m.%Y %H:%M:%S")

    profile_info = (
        "<b>👤 Сіздің профиліңіз</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"💬 <b>Chat ID:</b> <code>{chat.id}</code>\n"
        f"📌 <b>Chat түрі:</b> <code>{safe_text(chat.type)}</code>\n\n"
        f"👤 <b>Аты:</b> {first_name}\n"
        f"👥 <b>Тегі:</b> {last_name}\n"
        f"📝 <b>Толық аты:</b> {full_name}\n"
        f"🔗 <b>Username:</b> {username_text}\n"
        f"🌐 <b>Тілі:</b> {language_code}\n"
        f"🤖 <b>Бот па:</b> {is_bot}\n\n"
        f"📅 <b>Ботқа бірінші кірген уақыты:</b>\n"
        f"<code>{first_seen}</code>\n\n"
        f"`<code>{first_seen}</code>\n\n"
        f"🕘 <b>Соңғы актив:</b>\n"
        f"<code>{last_seen}</code>\n\n"
        f"💬 <b>Жалпы хабар саны:</b> "
        f"<code>{message_count}</code>\n"
        f"💾 <b>Сақталған мәтін:</b> {saved_text_status}\n\n"
        f"⏰ <b>Қазіргі уақыт:</b>\n"
        f"<code>{current_time}</code>\n\n"
        f'🔎 <a href="tg://user?id={user.id}">'
        "Telegram профиліне өту</a>"
    )

    await update.message.reply_html(
        profile_info,
        disable_web_page_preview=True
    )


async def save_my_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_activity(update)
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Мәтінді сақтау үшін командадан кейін мәтін жазыңыз.\n\n"
            "Мысал:\n"
            "/save_my_text Менің сүйікті кітабым - Абай жолы"
        )
        return

    saved_text = " ".join(context.args).strip()

    if not saved_text:
        await update.message.reply_text(
            "Сақтайтын мәтін бос болмауы керек."
        )
        return

    set_saved_text(user.id, saved_text)

    await update.message.reply_text(
        f"✅ Мәтініңіз сәтті сақталды:\n\n{saved_text}"
    )


async def show_my_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_activity(update)
    user = update.effective_user
    user_data = get_user_data(user.id)

    if user_data and user_data.get("saved_text"):
        saved_text = user_data.get("saved_text")
        await update.message.reply_text(
            f"📜 Сіздің сақталған мәтініңіз:\n\n{saved_text}"
        )
    else:
        await update.message.reply_text(
            "🤷 Сізде әлі сақталған мәтін жоқ.\n\n"
            "Сақтау үшін:\n"
            "/save_my_text [мәтін]"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user_activity(update)
    user = update.effective_user

    if not update.message or not update.message.text:
        return

    message_text = update.message.text
    lower_message_text = message_text.lower()

    if "сәлем" in lower_message_text:
        await update.message.reply_text(
            f"Сәлем, {user.first_name}!"
        )

    elif "рахмет" in lower_message_text or "алғыс" in lower_message_text:
        await update.message.reply_text(
            "Қош келдіңіз! 😊"
        )

    elif "қалайсың" in lower_message_text:
        await update.message.reply_text(
            "Мен жақсымын, рахмет! Сізге қалай көмектесе аламын?"
        )

    else:
        await update.message.reply_text(
            "Мен бұл хабарламаны түсінбедім.\n"
            "Командаларды көру үшін /help жіберіңіз."
        )


# ================== MENU ==================
async def set_bot_commands(application: Application):
    commands = [
        BotCommand("start", "Ботты бастау"),
        BotCommand("help", "Көмек"),
        BotCommand("profile", "Профильді көру"),
        BotCommand("save_my_text", "Мәтін сақтау"),
        BotCommand("my_text", "Сақталған мәтінді көру"),
    ]

    await application.bot.set_my_commands(commands)


# ================== BOT BUILDER ==================
def build_application():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(set_bot_commands)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("save_my_text", save_my_text))
    application.add_handler(CommandHandler("my_text", show_my_text))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    return application


# ================== MAIN RUNNER ==================
def main():
    init_db()

    print("================================")
    print("🤖 TELEGRAM BOT")
    print("🔄 24/7 режимі іске қосылуда...")
    print("================================")

    while True:
        try:
            application = build_application()
            print("✅ Бот сәтті іске қосылды!")

            application.run_polling(
                poll_interval=3.0,
                drop_pending_updates=False,
                allowed_updates=Update.ALL_TYPES
            )
        except KeyboardInterrupt:
            print("🛑 Бот қолмен тоқтатылды.")
            break
        except Exception as error:
            logger.exception("Ботта қате пайда болды.")
            print(f"❌ Қате: {error}")
            print("🔄 10 секундтан кейін қайта қосылады...")
            time.sleep(10)


if __name__ == "__main__":
    main()