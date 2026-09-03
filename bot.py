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
ADMIN_ID = 8129855972  # Сіздің Telegram ID-іңіз
REFERRAL_REWARD = 120  # 1 адам шақырғаны үшін берілетін сумма (тенге)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

user_logs_list = []

# -------------------- ДЕРЕКҚОР (DATABASE) --------------------
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    # Тұрақты бағандармен кесте жасау
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_seen TEXT,
            last_active TEXT,
            is_blocked INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            balance INTEGER DEFAULT 0,
            referrals_count INTEGER DEFAULT 0
        )
    """)
    
    # Ескі дерекқор болса, жаңа бағандарды қосу (миграция)
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "referred_by" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL")
    if "balance" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN balance INTEGER DEFAULT 0")
    if "referrals_count" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN referrals_count INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

def db_add_or_update_user(user_id: int, username: str, referrer_id: int = None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT first_seen, referred_by FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row is None:
        # Жаңа пайдаланушыны сақтау
        cursor.execute("""
            INSERT INTO users (user_id, username, first_seen, last_active, is_blocked, referred_by, balance, referrals_count)
            VALUES (?, ?, ?, ?, 0, ?, 0, 0)
        """, (user_id, username, now_str, now_str, referrer_id))
        
        # Егер оны біреу шақырған болса, шақырған адамға 120тг және +1 реферал қосу
        if referrer_id and referrer_id != user_id:
            cursor.execute("""
                UPDATE users 
                SET balance = balance + ?, referrals_count = referrals_count + 1 
                WHERE user_id = ?
            """, (REFERRAL_REWARD, referrer_id))
    else:
        # Бар пайдаланушы мәліметін жаңарту
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

# Пайдаланушы әрекетін сақтау және АДМИНГЕ СРАЗУ ХАБАРЛАМА ЖІБЕРУ
async def track_and_notify_admin(context: ContextTypes.DEFAULT_TYPE, user, action_text: str):
    username = f"@{user.username}" if user.username else "Жоқ"
    time_now = datetime.now().strftime("%H:%M:%S")
    
    log_line = (
        f"⏰ `{time_now}` | 👤 **{user.first_name}** ({username})\n"
        f"🆔 ID: `{user.id}`\n"
        f"💬 **Әрекет:** {action_text}\n"
        f"------------------------------------"
    )
    user_logs_list.append(log_line)
    if len(user_logs_list) > 50:
        user_logs_list.pop(0)

    if user.id != ADMIN_ID:
        try:
            admin_msg = (
                f"🚨 **Ботта жаңа белсенділік!**\n\n"
                f"👤 Пайдаланушы: **{user.first_name}** ({username})\n"
                f"🆔 ID: `{user.id}`\n"
                f"💬 Басты/жазды: **{action_text}**"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Админге хабарлама жіберуде қате: {e}")

# -------------------- БАТЫРМАЛАР (KEYBOARDS) --------------------
def get_main_keyboard(user_id: int):
    buttons = [
        [KeyboardButton("🛒 Заказать товар"), KeyboardButton("Меню вкусы и цена")],
        [KeyboardButton("🔗 Рефералка"), KeyboardButton("💰 Баланс")],
        [KeyboardButton("Отзыв канал Jester"), KeyboardButton("👤 Профиль")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton("👁 Кіргендер тарихы"), KeyboardButton("📊 Статистика")])
        buttons.append([KeyboardButton("👥 Рефералдар тізімі")])
        
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

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
Лайм 💫 + лёд 🧊 

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

# Start командасы (Реферал сілтемені тексеру қосылған)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referrer_id = None
    
    # Егер рефералдық сілтеме арқылы кірсе (/start 12345678)
    if context.args and context.args[0].isdigit():
        possible_referrer = int(context.args[0])
        if possible_referrer != user.id:
            referrer_id = possible_referrer

    db_add_or_update_user(user.id, user.username or user.first_name, referrer_id)
    await track_and_notify_admin(context, user, "/start")
    
    await update.message.reply_text(
        "Сәлеметсіз бе ? Jester магазиніне қош келдіңіз !",
        reply_markup=get_main_keyboard(user.id)
    )

# Order командасы
async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    await track_and_notify_admin(context, user, "Заказать товар")
    
    await update.message.reply_text("Напишите этому человеку @from_aksh")

# Profile командасы
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    await track_and_notify_admin(context, user, "Профиль тексерелді")

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT first_seen, last_active, balance, referrals_count FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        first_seen, last_active, balance, referrals = row
        text = (
            f"👤 **Сіздің профиліңіз:**\n\n"
            f"🆔 **ID:** `{user.id}`\n"
            f"👤 **Атыңыз:** {user.first_name}\n"
            f"💰 **Баланс:** {balance} ₸\n"
            f"👥 **Шақырған адамдарыңыз:** {referrals}\n"
            f"📅 **Ботқа бірінші рет кірген күніңіз:** {first_seen}\n"
            f"⚡ **Соңғы белсенділік:** {last_active}"
        )
    else:
        text = "Профиль мәліметтері табылмады."

    await update.message.reply_text(text, parse_mode="Markdown")

# 2. Рефералка командасы
async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    await track_and_notify_admin(context, user, "Рефералка батырмасын басты")

    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.id}"

    text = (
        f"🎁 **Рефералдық бағдарлама!**\n\n"
        f"Достарыңызды ботқа шақырып, **әрбір адам үшін {REFERRAL_REWARD} ₸** заңды түрде табыңыз!\n\n"
        f"🔗 **Сіздің жеке сілтемеңіз:**\n`{ref_link}`\n\n"
        f"📌 Сілтемеңізді достарыңызға жіберіңіз. Олар ботқа өтіп `/start` батырмасын басқанда сіздің балансыңызға бірден 120 ₸ қосылады!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# 3. Баланс командасы
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_add_or_update_user(user.id, user.username or user.first_name)
    await track_and_notify_admin(context, user, "Баланс тексерді")

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance, referrals_count FROM users WHERE user_id = ?", (user.id,))
    row = cursor.fetchone()
    conn.close()

    balance = row[0] if row else 0
    referrals = row[1] if row else 0

    text = (
        f"💰 **Сіздің балансыңыз:**\n\n"
        f"💵 **Сумма:** {balance} ₸\n"
        f"👥 **Шақырылған адамдар:** {referrals} адам\n\n"
        f"💡 Балансты арттыру үшін достарыңызды шақырыңыз!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# 1. АДМИН: Барлық пайдаланушыларға рассылка жіберу (/send)
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    # Тексеру: Текст жазылған ба? (Мысалы: /send Бүгін скидка!)
    if not context.args:
        await update.message.reply_text(
            "⚠️ **Қолдану тәсілі:**\n`/send Сіздің хабарламаңыз`\n\nМысалы:\n`/send Бүгін барлық тауарларға 20% скидка!`",
            parse_mode="Markdown"
        )
        return

    broadcast_text = " ".join(context.args)

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_blocked = 0")
    users = cursor.fetchall()
    conn.close()

    await update.message.reply_text(f"📢 Хабарлама {len(users)} пайдаланушыға жіберілуде...")

    success_count = 0
    blocked_count = 0

    for user_row in users:
        target_id = user_row[0]
        try:
            await context.bot.send_message(chat_id=target_id, text=broadcast_text)
            success_count += 1
        except Exception:
            mark_user_blocked(target_id)
            blocked_count += 1

    await update.message.reply_text(
        f"✅ **Жіберу аяқталды!**\n\n"
        f"📥 Сәтті жеткізілді: **{success_count}**\n"
        f"🚫 Ботты бұғаттағандар: **{blocked_count}**",
        parse_mode="Markdown"
    )

# 4. АДМИН: Кім қанша адам қосқанын көру (/referrals)
async def admin_referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    # Ең көп реферал жинаған 20 адамды шығару
    cursor.execute("""
        SELECT user_id, username, referrals_count, balance 
        FROM users 
        WHERE referrals_count > 0 
        ORDER BY referrals_count DESC 
        LIMIT 20
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Әлі ешкім адам шақырмады.")
        return

    text = "👥 **Ең көп реферал қосқан пайдаланушылар тізімі:**\n\n"
    for idx, row in enumerate(rows, start=1):
        u_id, username, ref_count, balance = row
        uname = f"@{username}" if username and not username.isdigit() else "Жоқ"
        text += f"{idx}. 👤 ID: `{u_id}` ({uname}) — **{ref_count} адам** | 💰 {balance} ₸\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# Stats командасы
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

# Логтарды көрсету (Админге)
async def show_user_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    if not user_logs_list:
        await update.message.reply_text("Әлі ешқандай белсенділік тіркелмеді.")
        return

    logs_text = "\n".join(user_logs_list[-20:])
    await update.message.reply_text(
        f"🔍 **Кімнің не жазғаны/басқаны (Тарих):**\n\n{logs_text}",
        parse_mode="Markdown"
    )

# Inline кнопка өңдеу
async def inline_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "order_product":
        await track_and_notify_admin(context, query.from_user, "Inline Кнопка: Заказать товар")
        await query.message.reply_text("Напишите этому человеку @from_aksh")

# Текстік хабарламаларды өңдеу
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if user:
        db_add_or_update_user(user.id, user.username or user.first_name)
        await track_and_notify_admin(context, user, text)

    if text == "Отзыв канал Jester":
        await update.message.reply_text("Наш отзыв канал https://t.me/+T4PUwlWmxNdhYWQ6")
    elif text == "Меню вкусы и цена":
        await update.message.reply_text(MENU_TEXT, reply_markup=order_inline_keyboard)
    elif text == "🛒 Заказать товар":
        await order_command(update, context)
    elif text == "👤 Профиль":
        await profile_command(update, context)
    elif text == "🔗 Рефералка":
        await referral_command(update, context)
    elif text == "💰 Баланс":
        await balance_command(update, context)
    elif text == "👁 Кіргендер тарихы":
        await show_user_logs(update, context)
    elif text == "📊 Статистика":
        await stats_command(update, context)
    elif text == "👥 Рефералдар тізімі":
        await admin_referrals_command(update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Exception):
        if "bot was blocked by the user" in str(context.error).lower():
            if isinstance(update, Update) and update.effective_user:
                mark_user_blocked(update.effective_user.id)

async def set_bot_commands(application: Application):
    commands = [
        BotCommand("start", "Ботты бастау"),
        BotCommand("order", "Заказать товар"),
        BotCommand("profile", "Профильді көру"),
        BotCommand("referral", "Рефералка"),
        BotCommand("balance", "Баланс көру"),
    ]
    
    admin_commands = commands + [
        BotCommand("stats", "Статистика (Админ)"),
        BotCommand("send", "Барлығына хабарлама (Админ)"),
        BotCommand("referrals", "Рефералдар тізімі (Админ)")
    ]

    if ADMIN_ID:
        await application.bot.set_my_commands(
            admin_commands,
            scope={"type": "chat", "chat_id": ADMIN_ID}
        )
    
    await application.bot.set_my_commands(commands)

# -------------------- ІСКЕ ҚОСУ --------------------
def main():
    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    # Базалық командалар
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("order", order_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("balance", balance_command))
    
    # Админ командалары
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("send", broadcast_command))
    application.add_handler(CommandHandler("referrals", admin_referrals_command))

    application.add_handler(CallbackQueryHandler(inline_button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    application.post_init = set_bot_commands

    logger.info("Бот іске қосылуда...")
    application.run_polling()

if __name__ == "__main__":
    main()
