import logging
import sqlite3
import html
import os
from datetime import datetime, timezone, timedelta
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Уақыт белдеуін орнату (Нұр-Сұлтан / Астана уақыты)
# Егер сіздің уақыт белдеуіңіз басқа болса, мынаны өзгертіңіз:
# datetime.timezone(datetime.timedelta(hours=5))
KZ_TZ = timezone(timedelta(hours=5))

# Логгерді орнату
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Мәліметтер базасының аты
DB_NAME = "bot_database.db"

# Render Environment Variables-дан алу үшін "BOT_TOKEN" атымен токенді қосуды ұмытпаңыз!
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") # ADMIN_ID-ны да Render Environment Variables-да қосу ұсынылады

if not BOT_TOKEN:
    logger.error("BOT_TOKEN табылмады! Render Environment Variables-да 'BOT_TOKEN' атымен қосыңыз.")
    exit()
if not ADMIN_ID:
    logger.warning("ADMIN_ID табылмады. Кейбір админ функциялары жұмыс істемеуі мүмкін.")
    ADMIN_ID = None
else:
    try:
        ADMIN_ID = int(ADMIN_ID)
    except ValueError:
        logger.error(f"ADMIN_ID қате форматта: {ADMIN_ID}. Сан болуы керек.")
        ADMIN_ID = None

# -------------------- Мәліметтер базасын басқару --------------------

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # Пайдаланушылар кестесі
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            language_code TEXT,
            is_bot INTEGER,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            blocked INTEGER DEFAULT 0,
            referred_by INTEGER,
            saved_text TEXT
        )
        """)
        # Егер referred_by және saved_text кейінірек қосылса, оларды жаңарту
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
            logger.info("users кестесіне 'referred_by' колонкасы қосылды.")
        except sqlite3.OperationalError:
            pass # Колонка бар болса, ештеңе істемеу

        try:
            cursor.execute("ALTER TABLE users ADD COLUMN saved_text TEXT")
            logger.info("users кестесіне 'saved_text' колонкасы қосылды.")
        except sqlite3.OperationalError:
            pass # Колонка бар болса, ештеңе істемеу

        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Мәліметтер базасын инициализациялауда қате: {e}")
    finally:
        conn.close()

def get_now_iso():
    return datetime.now(KZ_TZ).isoformat(timespec="seconds")

def format_datetime(dt_text: str | None) -> str:
    if not dt_text:
        return "белгісіз"
    try:
        # ISO форматына түрлендіру (мысалы, '2023-10-27T10:30:00+05:00')
        dt_object = datetime.fromisoformat(dt_text)
        return dt_object.strftime("%Y-%m-%d %H:%M:%S (%Z%z)")
    except (ValueError, TypeError):
        return dt_text # Егер формат бұрыс болса, түпнұсқа мәтінді қайтару

def safe_text(value: str | None, default="жоқ") -> str:
    if value is None:
        return default
    return html.escape(str(value))

def save_user_activity(update: Update, increase_message_count=True):
    user = update.effective_user
    if not user:
        return

    now = get_now_iso()
    message_add = 1 if increase_message_count else 0

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
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
            message_count,
            blocked,
            saved_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            username = excluded.username,
            language_code = excluded.language_code,
            is_bot = excluded.is_bot,
            last_seen = excluded.last_seen,
            message_count = users.message_count + ?,
            saved_text = COALESCE(users.saved_text, excluded.saved_text)
        """, (
            user.id,
            user.first_name,
            user.last_name,
            user.username,
            user.language_code,
            1 if user.is_bot else 0,
            now, # first_seen тек бірінші рет кіргенде орнатылады
            now,
            message_add, # message_count тек осы жазба жаңартылса ғана қосылады
            0, # blocked
            None # saved_text жаңа пайдаланушы болса, тек null болады
        ))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Пайдаланушы әрекетін сақтауда қате ({user.id}): {e}")
        conn.rollback()
    finally:
        conn.close()

def get_user_data(user_id: int) -> dict | None:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row # Деректерді тікбұрышты форматта алу
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        data = cursor.fetchone()
        return dict(data) if data else None
    except sqlite3.Error as e:
        logger.error(f"Пайдаланушы деректерін алуда қате ({user_id}): {e}")
        return None
    finally:
        conn.close()

def set_saved_text(user_id: int, saved_text: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET saved_text = ? WHERE user_id = ?", (saved_text, user_id))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Пайдаланушы мәтінін сақтауда қате ({user_id}): {e}")
        conn.rollback()
    finally:
        conn.close()

def get_saved_text(user_id: int) -> str | None:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT saved_text FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"Пайдаланушы мәтінін алуда қате ({user_id}): {e}")
        return None
    finally:
        conn.close()

def save_referral(user_id: int, referred_by: int):
    if user_id == referred_by:
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO users (user_id, referred_by, first_seen, last_seen)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            referred_by = COALESCE(users.referred_by, excluded.referred_by)
        """, (user_id, referred_by, get_now_iso(), get_now_iso()))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Рефералды сақтауда қате ({user_id}, referred_by={referred_by}): {e}")
        conn.rollback()
    finally:
        conn.close()

def mark_user_blocked(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET blocked = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Пайдаланушыны бұғатталды деп белгілеуде қате ({user_id}): {e}")
        conn.rollback()
    finally:
        conn.close()

def get_bot_stats():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    stats = {}
    try:
        # Жалпы пайдаланушылар саны
        cursor.execute("SELECT COUNT(*) FROM users")
        stats["total_users"] = cursor.fetchone()[0]

        # Бұғаттаған пайдаланушылар саны
        cursor.execute("SELECT COUNT(*) FROM users WHERE blocked = 1")
        stats["blocked_users"] = cursor.fetchone()[0]

        # Жаңа пайдаланушылар (соңғы 24 сағатта)
        cutoff_date = datetime.now(KZ_TZ) - timedelta(days=1)
        cursor.execute("SELECT COUNT(*) FROM users WHERE first_seen >= ?", (cutoff_date.isoformat(timespec="seconds"),))
        stats["new_users_last_24h"] = cursor.fetchone()[0]

        # Жалпы хабарламалар саны
        cursor.execute("SELECT SUM(message_count) FROM users")
        total_messages = cursor.fetchone()[0]
        stats["total_messages"] = total_messages if total_messages is not None else 0

        return stats
    except sqlite3.Error as e:
        logger.error(f"Бот статистикасын алуда қате: {e}")
        return None
    finally:
        conn.close()

# -------------------- Командалар --------------------

async def admin_stats_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Бұл команда тек админге арналған!")
        return
    await update.message.reply_text("📊 Бот статистикасы: ...")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # Пайдаланушыны тіркеу/жаңарту
    save_user_activity(update, increase_message_count=False) # start командасы хабарлама санағын арттырмайды

    start_parameter = context.args[0] if context.args else None
    reply_text = f"Сәлеметсіз бе, {safe_text(user.first_name)}!\n\n"

    if start_parameter and start_parameter.startswith("ref_"):
        try:
            referred_by_id = int(start_parameter.split("_")[1])
            if referred_by_id != user.id:
                save_referral(user.id, referred_by_id)
                reply_text += f"Сіз {referred_by_id} пайдаланушысы арқылы келдіңіз.\n\n"
            else:
                reply_text += "Өзіңізге сілтеме жасай алмайсыз.\n\n"
        except (ValueError, IndexError):
            logger.warning(f"invalid referral link from user {user.id}: {start_parameter}")
            reply_text += "Сіз дұрыс емес сілтеме арқылы келдіңіз.\n\n"

    reply_text += "Мен сізге көмекші ботпын. Қызметтерді көру үшін /help командасын пайдаланыңыз."
    await update.message.reply_text(reply_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Менің негізгі командаларым:\n"
        "/start - Ботты бастау\n"
        "/help - Осы көмек мәзірін көрсету\n"
        "/profile - Сіздің профиліңізді көрсету\n"
        "/save_my_text [мәтін] - Сіздің мәтініңізді сақтау\n"
        "/my_text - Сақталған мәтінді көру\n"
    )

    if ADMIN_ID and update.effective_user.id == ADMIN_ID:
        help_text += "\n<b>Админ командалары:</b>\n"
        help_text += "/stats - Бот статистикасын көрсету\n"
        await update.message.reply_html(help_text) # Админ болса, барлық ақпаратты HTML форматында жібереміз
    else:
        # Админ болмаса, тек жалпы көмек және "табылмады" хабарын жіберу
        # Егер сіздің ойыңызда "табылмады" деген хабарды тек админ командалары болмағанда жіберу болса,
        # онда бұл жерде орналасуы керек.
        # Егер сіздің мақсатыңыз админ болса да, профиль табылмаса "табылмады" деп жазу болса,
        # логиканы өзгерту керек.
        await update.message.reply_html(help_text) # Жалпы көмек мәзірін жібереміз
        # Сіздің кодыңыздағы "Сіз туралы ақпарат табылмады." сөзінің қайда қолданылатынын нақтылаңыз.
        # Егер оны профиль туралы ақпарат жоқ болғанда көрсеткіңіз келсе, онда /profile командасының логикасын тексеру керек.
        # қазіргі кезде бұл код сол жерде не істейтіні белгісіз.
        # Егер тек админ емес адамдарға "табылмады" деп жазу керек болса, онда мынаны істеуге болады:
        # await update.message.reply_text("Сіз туралы ақпарат табылмады.") # Бұл жерде жақша, тырнақша және нүкте дұрыс болуы керек.

    # Бұл жолдарды delete етіңіз, себебі олар қате орналасқан және екі рет хабар жібереді.
    # await update.message.reply_text("Сіз туралы ақпарат табылмады.")
    # profile_info = f"<b>{safe_text(user.first_name)} {{safe_text(user.last_name or '')}} туралы ақпарат:</b>\n"
    # profile_info += f"👤 ID: `{user_data['user_id']}`\n"

    return # return соңында болуы керек


    profile_info = f"<b>{safe_text(user.first_name)} {safe_text(user.last_name or '')} туралы ақпарат:</b>\n\n"
    profile_info += f"👤 ID: `{user_data['user_id']}`\n"
    profile_info += f"📝 Username: @{safe_text(user_data['username'], 'жоқ')}\n"
    profile_info += f"💬 Тіл: `{user_data['language_code'] or 'белгісіз'}`\n"
    profile_info += f"🤖 Бұл бот па?: {'Иә' if user_data['is_bot'] else 'Жоқ'}\n"
    profile_info += f"⏳ Бірінші кіру: {format_datetime(user_data['first_seen'])}\n"
    profile_info += f"⏰ Соңғы кіру: {format_datetime(user_data['last_seen'])}\n"
    profile_info += f"✉️ Хаттар саны: `{user_data['message_count']}`\n"
    profile_info += f"🚫 Бұғатталған ба?: {'Иә' if user_data['blocked'] else 'Жоқ'}\n"
    if user_data.get('referred_by'):
        profile_info += f"🔗 Шақырған: `{user_data['referred_by']}`\n"
    if user_data.get('saved_text'):
        profile_info += f"💾 Сақталған мәтін: `{safe_text(user_data['saved_text'], 'жоқ')}`\n"

    await update.message.reply_html(profile_info)

async def save_my_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Сақтайтын мәтінді көрсетіңіз. Мысалы: `/save_my_text Менің мәтінім`")
        return

    text_to_save = " ".join(context.args)
    set_saved_text(user.id, text_to_save)
    await update.message.reply_text(f"✅ Мәтініңіз сақталды: `{safe_text(text_to_save)}`")

async def my_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    saved_text = get_saved_text(user.id)

    if saved_text:
        await update.message.reply_text(f"💾 Сіздің сақталған мәтініңіз:\n`{safe_text(saved_text)}`")
    else:
        await update.message.reply_text("Сіз әлі ешқандай мәтін сақтамадыңыз. `/save_my_text` командасын қолданыңыз.")

async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not ADMIN_ID or user.id != ADMIN_ID:
        await update.message.reply_text("Сізге бұл команданы қолдануға рұқсат етілмеген.")
        return

    if update.effective_chat.type != "private":
        await update.message.reply_text("Бұл команда тек жеке чатта қолданылады.")
        return

    stats = get_bot_stats()
    if stats:
        stats_text = "📊 <b>Бот статистикасы:</b>\n\n"
        stats_text += f"🔹 Жалпы пайдаланушылар: `{stats['total_users']}`\n"
        stats_text += f"🔹 Бұғатталған пайдаланушылар: `{stats['blocked_users']}`\n"
        stats_text += f"🔹 Жаңа пайдаланушылар (соңғы 24 сағат): `{stats['new_users_last_24h']}`\n"
        stats_text += f"🔹 Жалпы жіберілген хабарламалар: `{stats['total_messages']}`\n"
        await update.message.reply_html(stats_text)
    else:
        await update.message.reply_text("Статистиканы алу мүмкін болмады.")

# -------------------- Хабарламаларды өңдеу --------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Пайдаланушының әрекетін тіркеу
    save_user_activity(update, increase_message_count=True)

    message_text = update.message.text.lower()
    user = update.effective_user

    # Мәтіннің ешқандай командаға сәйкес келмеуін тексеру
    if message_text == "/start":
        await start_command(update, context)
    elif message_text == "/help":
        await help_command(update, context)
    elif message_text == "/profile":
        await profile_command(update, context)
    elif message_text.startswith("/save_my_text"):
        await save_my_text(update, context)
    elif message_text == "/my_text":
        await my_text(update, context)
    elif ADMIN_ID and user.id == ADMIN_ID and message_text == "/stats":
        await admin_stats_command(update, context)
    else:
        # Егер сәйкес келмесе, кәдімгі мәтін ретінде өңдеу
        await update.message.reply_text(f"Мен сіздің '{safe_text(update.message.text)}' сөзіңізді түсінбедім. Немесе `/help` командасын қолданыңыз.")

# -------------------- Қателерді өңдеу --------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update: {update}", exc_info=context.error)

    # Пайдаланушы бұғаттаған жағдайды өңдеу
    if isinstance(context.error, telegram.error.Forbidden):
        user_id = update.effective_message.chat_id # Update объектынде user_id болуы мүмкін емес, сондықтан chat_id қолданамыз
        mark_user_blocked(user_id)
        logger.warning(f"Пайдаланушы {user_id} ботты бұғаттады.")
    elif isinstance(context.error, telegram.error.BadRequest):
        logger.warning(f"Telegram BadRequest: {context.error}")
    else:
        # Басқа қателерді тіркеу
        logger.error(f"Төмендегі update қате тудырды: {update}", exc_info=context.error)


async def profile_command(update, context):
    await update.message.reply_text("Бұл сіздің профиліңіз.")


# -------------------- Ботты іске қосу --------------------

async def set_bot_commands(application: Application):
    commands = [
        BotCommand("start", "Ботты бастау"),
        BotCommand("help", "Көмек"),
        BotCommand("profile", "Профильді көру"),
        BotCommand("save_my_text", "Мәтінді сақтау"),
        BotCommand("my_text", "Сақталған мәтінді көру")
    ]
    if ADMIN_ID: # Тек админ болса, админ командасын қосу
        commands.append(BotCommand("stats", "Статистика"))

    await application.bot.set_my_commands(commands)


def main():
    # Application құру
    application = Application.builder().token(BOT_TOKEN).build()

    # Командаларды тіркеу
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("save_my_text", save_my_text))
    application.add_handler(CommandHandler("my_text", my_text))

    if ADMIN_ID:
        application.add_handler(
            CommandHandler("stats", admin_stats_command)
        )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    application.add_error_handler(error_handler)

    # Командаларды іске қосу кезінде жүктеу (post_init арқылы)
    application.post_init = set_bot_commands

    logger.info("Бот іске қосылуда...")
    application.run_polling()


if __name__ == "__main__":
    main()
