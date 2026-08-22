import logging
from datetime import datetime
from telegram import (
    Update, 
    BotCommand, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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

# Пайдаланушылардың соңғы әрекеттерін сақтау (Админге кімнің не жазғанын/басқанын көрсету үшін)
user_logs_list = []

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

# Пайдаланушының не жазғанын немесе кай команда басқанын сақтау
def save_user_action(user, action_text):
    username = f"@{user.username}" if user.username else "Жоқ"
    time_now = datetime.now().strftime("%H:%M:%S")
    log_line = (
        f"⏰ `{time_now}` | 👤 **{user.first_name}** ({username})\n"
        f"🆔 ID: `{user.id}`\n"
        f"💬 **Жазылған/Команда:** {action_text}\n"
        f"------------------------------------"
    )
    user_logs_list.append(log_line)
    if len(user_logs_list) > 30: # Тізім асып кетпеуі үшін соңғы 30-ын ұстаймыз
        user_logs_list.pop(0)

# -------------------- БАТЫРМАЛАР (KEYBOARDS) --------------------
def get_main_keyboard(user_id: int):
    buttons = [
        [KeyboardButton("Меню вкусы и цена")],
        [KeyboardButton("Отзыв канал Jester")],
    ]
    # Тек сізге (админге) ғана көрінетін кнопка
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("👁 Кім кірді / Логтар")])
        
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# Менюдің астында тұратын "Заказать товар" батырмасы
order_inline_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Заказать товар", callback_data="order_product")]
])

# -------------------- ТЕКСТТЕР --------------------
MENU_TEXT = """🚩🚩🚩🚩  🚩🚩🚩🚩


🔠🔠🟢🔠  🔠🔠🔠🔠🔠🔠 ✅

🔠🔠🔠🔠🔠🔠🅰️🔠 🔠🅰️🔠🅰️


👇👇👇👇👇👇👇👇👇👇👇👇👇👇👇👇

Waka E.T Burst 41к тяг ≈ 23000₸  12-15% 

Вкусы  ⬇️

Клубника 🍓  
Киви 🥝 
Виноград 🍇  
 

Waka BLAST 38к тяг ≈ 21500₸  12-15% 

Вкусы  ⬇️

Манго 🥭 
Арбуз  🍉  
Яблоко  🍏   
Энергетик⚡ ~ Лимон 🍋 
Манго 🥭 ~ Ваниль 🍦 
 Тройная ягода 🪐 + лёд 🧊 
Арбуз 🍉 ~ лёд 🧊 
Вишня 🍒 ~ лёд 🧊 
Клубника 🍓 ~ Киви 🥝 + лёд 🧊  
Черника 🫐 ~ Малина ⚡️ + лёд 🧊 

Waka XLAND SPIKE 35к тяг ≈ 20000₸  12-15% 

Вкусы  ⬇️ 
 
Виноград  🍇 
Кислое яблоко 🍏  
Клюква ~ Виноград 🍇 
Черника 🫐 ~ Вишня 🍒 

Waka JUPITER 30к тяг ≈ 18000₸  12-15%

Вкусы ⬇️

Арбуз 🍉 
Вишня 🍒 
Клубника 🍓 
Гавайский лимонад 🍹  
Клюква ~ Виноград 🍇 
Ежевика ~ Черника 🫐 ~ Малина 💫
 
Waka SoPro 20к тяг ≈ 15000₸ 11%  

Вкусы  ⬇️

Арбуз 🍉 
Вишня 🍒 
Лимон 🍋 
Клубника 🍓 
Яблоко 🍏 
Виноград 🍇 
Зелёный Виноград 🟢🍇 
Тройная ягода 💥
Капучино ☕
Тёмная вишня 🍒 
Энергетик ⚡
Клубника 🍓 ~ Виноград 🍇 
Арбуз 🍉 ~ Вишня 🍒  
Клубника 🍓 ~ Киви 🥝 
Арбуз 🍉 ~ Мята ⚡️
Яблоко 🍏 ~ Груша 🍐  
Клубника 🍓 ~ Арбуз 🍉 
Клубника 🍓 + лёд 🧊 
Lайм 💫 + лёд 🧊 

Waka XLAND 15к тяг ≈ 14000₸  9-11% 

Вкусы ⬇️ 

Арбуз 🍉 
Мята ❄️ 
Виноград 🍇 
Кислое яблоко 🍏 
Зеленый Виноград 🍇 
Сакура 🌸 ~ виноград 🍇 
Клубника 🍓 ~ Киви 🥝 
Черника 🫐 ~ Малина 💫



Waka SoPro PA 10к тяг ≈ 12500₸  8-9% 

Вкусы😋  ⬇️

Арбуз 🍉  
Вишня 🍒 
Киви 🥝 
Виноград 🍇  
Персик 🍑  
Гранат 💫
Мультифрукты 🍓 
Ягодный микс 💫
Ягодный тархун⚡️
Клубника 🍓 ~ Банан 🍌  
Персик 🍑 ~ Манго 🥭   
Лимон 🍋 ~ Лайм 🍋 
Манго 🥭 ~ Апельсин 🍊  
Клубника 🍓 ~ Виноград 🍇   
Черника 🫐 ~ Черная смородина 🪐 
Гуава ~ Малина ⚡️
Черника 🫐 ~ Малина  ⚡️ 

Холодные 🧊

Арбуз 🍉 + лёд 🧊     
Вишня 🍒 + лёд 🧊  
Черника 🫐 + лёд 🧊  
Клубника 🍓 ~ Киви 🥝 + лёд 🧊    
Малина 💥 ~ Черника 🫐 +лёд 🧊    
Черника 🫐 ~ Малина 💥 ~ Лимон 🍋 + лёд 🧊 

Waka SoPro DM 8к тяг ≈ 9500₸  9-11% 

Вкусы  ⬇️

Малина 🥸
Киви 🥝
Виноград 🍇  
Персик 🍑  
Клубника 🍓  
Манго 🥭  
Арбуз 🍉   
Вишня 🍒  
Дюшес 💫  
Черника 🫐 
Ягодный микс 🍓  
Виноград 🍇 ~ Яблоко 🍏  
Черника 🫐 ~ Малина 💫  
Персик 🍑 ~ Клубника 🍓  
Черника 🫐 ~ Малина 💫 ~ Гранат ⚡️ 

Waka Smash 6к тяг ≈ 7500₸  7%  

Вкусы  ⬇️ 

Арбуз 🍉  
Яблоко 🍏 
Черника 🫐 
Виноград 🍇  
Клубника 🍓  
Вишня 🍒
Вишнёвый Лайм 🌪
Дюшес 💥
Алоэ ~ Виноград 🍇 
Банан 🍌 ~ Дыня 🍈  
Банан 🍌 ~ Какос 💫
Клубника 🍓 ~ Манго 🥭 
Клубника 🍓 ~ Виноград 🍇   

Waka Solo 2  2.5к тяг ≈ 5500₸  5-7% 

Вкусы ⬇️ 

Клубника 🍓  
Черника 🫐  
Мультифрукты ⚡️
Арбуз 🍉   
Клубника 🍓 ~ Малина 💫
Черника 🫐 ~ Малина 💫   
Клубника 🍓 ~ Виноград 🍇  
Персик 🍑 ~ Манго 🥭 

Waka Slam 2.3к тяг ≈ 4000₸  5-7% 

Вкусы  ⬇️

Арбуз 🍉 
Виноград 🍇 
Вишня 🍒 
Дюшес ⚡️
Мята 💫
Яблоко 🍏 

🥤 Коктейль 6.5к тяг ≈ 8000₸ 🥤

Вкусы ⬇️ 

Апельсин 🍊  
Яблоко 🍏   
Мята 💫
Арбуз 🍉  
Дюшес ⚡️  
Виноград 🍇 
Клубника 🍓   
Вишня 🍒 
Черника 🫐  
Персик 🍑    
Киви 🥝   
Манго 🥭   
Тайский табак 🪐"""

# -------------------- КОМАНДАЛАР --------------------

# 1. Start командасы
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    save_user_action(user, "/start")
    
    await update.message.reply_text(
        "Сәлеметсіз бе ? Jester магазиніне қош келдіңіз !",
        reply_markup=get_main_keyboard(user.id)
    )

# 2. Заказать разку командасы
async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    save_user_action(user, "/order")
    
    await update.message.reply_text("Напишите этому человеку @from_aksh")

# 3. Профиль командасы
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    save_user_action(user, "/profile")

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
    
    if user.id != ADMIN_ID:
        return

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
    active_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
    blocked_users = cursor.fetchone()[0]

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

# ТЕК АДМИНГЕ: Пайдаланушылардың не жазғанын/басқанын көру командасы
async def show_user_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    if not user_logs_list:
        await update.message.reply_text("Әлі ешқандай белсенділік тіркелмеді.")
        return

    logs_text = "\n".join(user_logs_list[-15:]) # Соңғы 15 әрекет
    await update.message.reply_text(
        f"🔍 **Кімнің не жазғаны/басқаны:**\n\n{logs_text}",
        parse_mode="Markdown"
    )

# Inline кнопка басылғанда ("Заказать товар" батырмасы)
async def inline_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order_product":
        save_user_action(query.from_user, "Кнопка: Заказать товар")
        await query.message.reply_text("Напишите этому человеку @from_aksh")

# Әр хабарлама мен батырмаларды өңдеу
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if user:
        db_add_or_update_user(user.id, user.username or user.first_name)
        save_user_action(user, text)

    # Жаңа команда-батырмаларды тексереміз:
    if text == "Отзыв канал Jester":
        await update.message.reply_text("Наш отзыв канал https://t.me/+T4PUwlWmxNdhYWQ6")
    elif text == "Меню вкусы и цена":
        await update.message.reply_text(MENU_TEXT, reply_markup=order_inline_keyboard)
    elif text == "👁 Кім кірді / Логтар":
        await show_user_logs(update, context)

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

    application.add_handler(CallbackQueryHandler(inline_button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    application.post_init = set_bot_commands

    logger.info("Бот іске қосылуда...")
    application.run_polling()

if __name__ == "__main__":
    main()
