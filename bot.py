import logging
from datetime import datetime
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import sqlite3

# -------------------- БАПТАУЛАР --------------------
BOT_TOKEN = "8178654145:AAEqpzmHarA89arEsT7Ih2gqhQo49Y5NvQA"
ADMIN_ID = 8129855972  # ОСЫ_ЖЕРГЕ_ӨЗ_TELEGRAM_ID_ЖАЗЫҢЫЗ (мысалы: 123456789)

# Логтарды баптау
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- ДЕРЕКҚОР (DATABASE) --------------------
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_seen TEXT,
            last_active TEXT,
            is_blocked INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def db_add_or_update_user(user_id: int, username: str):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT first_seen FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row is None:
        # Жаңа пайдаланушы
        cursor.execute("""
            INSERT INTO users (user_id, username, first_seen, last_active, is_blocked)
            VALUES (?, ?, ?, ?, 0)
        """, (user_id, username, now_str, now_str))
    else:
        # Бар пайдаланушы — соңғы белсенділігін жаңарту
        cursor.execute("""
            UPDATE users 
            SET username = ?, last_active = ?, is_blocked = 0 
            WHERE user_id = ?
        """, (username, now_str, user_id))

    conn.commit()
    conn.close()

def mark_user_blocked(user_id: int):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# -------------------- КОМАНДАЛАР --------------------

# 1. Start командасы
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    
    await update.message.reply_text("Сәлеметсіз бе ? Jester магазиніне қош келдіңіз !")

# 2. Заказать разку командасы
async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    
    await update.message.reply_text("Напишите этому человеку @from_aksh")

# 3. Профиль командасы
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT first_seen, last_active FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        first_seen, last_active = row
        text = (
            f"👤 **Сіздің профиліңіз:**\n\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"👤 **Атыңыз:** {user.first_name}\n"
            f"📅 **Ботқа бірінші рет кірген күніңіз:** {first_seen}\n"
            f"⚡ **Соңғы белсенділік:** {last_active}"
        )
    else:
        text = "Профиль мәліметтері табылмады."

    await update.message.reply_text(text, parse_mode="Markdown")

# 4. Статистика командасы (Тек админге арналған)
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Тек админ тексере алады
    if user.id != ADMIN_ID:
        return

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    # Жалпы пайдаланушылар
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # Белсенділер (блоктамағандар)
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
    active_users = cursor.fetchone()[0]

    # Блоктағандар
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
    blocked_users = cursor.fetchone()[0]

    # Бүгін қосылғандар
    today_str = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) FROM users WHERE first_seen LIKE ?", (f"{today_str}%",))
    today_users = cursor.fetchone()[0]

    conn.close()

    text = (
        f"📊 **Бот статистикасы:**\n\n"
        f"👥 Жалпы пайдаланушылар: **{total_users}**\n"
        f"🟢 Белсенді пайдаланушылар: **{active_users}**\n"
        f"🆕 Бүгін жаңадан қосылғандар: **{today_users}**\n"
        f"🚫 Ботты блокқа тыққандар: **{blocked_users}**"
    )

    await update.message.reply_text(text, parse_mode="Markdown")

# Әр хабарлама келгенде белсенділікті жаңарту
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user:
        db_add_or_update_user(update.effective_user.id, update.effective_user.username or update.effective_user.first_name)

# Қателерді ұстау (пайдаланушы ботты блокқа тықса анықтау)
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Exception):
        if "bot was blocked by the user" in str(context.error).lower():
            if isinstance(update, Update) and update.effective_user:
                mark_user_blocked(update.effective_user.id)

# Меню баптау
async def set_bot_commands(application: Application):
    commands = [
        BotCommand("start", "Ботты бастау"),
        BotCommand("order", "Заказать разку"),
        BotCommand("profile", "Профильді көру"),
    ]
    
    # Статистика командасы ТЕК Админнің Telegram-ында ғана менюде көрінеді
    if ADMIN_ID:
        await application.bot.set_my_commands(
            commands + [BotCommand("stats", "Статистика (Админ)")],
            scope={"type": "chat", "chat_id": ADMIN_ID}
        )
    
    # Қарапайым пайдаланушыларға арналған меню
    await application.bot.set_my_commands(commands)

# -------------------- ІСКЕ ҚОСУ --------------------
def main():
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("order", order_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("stats", stats_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    application.post_init = set_bot_commands

    logger.info("Бот іске қосылуда...")
    application.run_polling()

if __name__ == "__main__":
    main()
