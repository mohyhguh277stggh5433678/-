import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler,
    MessageHandler,
    Filters
)
from functools import wraps
import sqlite3
from sqlite3 import Error
import os

# إعدادات المطور
DEVELOPER_ID = 7828957324
BOT_TOKEN = "7636147475:AAGdViEYL9ckAYiWblDP8nrzkVKRrYMLrKw"

# إعدادات قاعدة البيانات
DB_NAME = "bot_db.sqlite"

# حالات المحادثة
SECTION_NAME, SECTION_CONTENT, WELCOME_MSG, SUPPORT_MSG = range(4)

def create_connection():
    conn = None
    try:
        conn = sqlite3.connect(DB_NAME)
        
        # إنشاء الجداول
        conn.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY)''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS settings
                     (key TEXT PRIMARY KEY, value TEXT)''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS sections
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     name TEXT UNIQUE,
                     content_type TEXT,
                     content TEXT)''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                     username TEXT)''')
        
        # إضافة المطور
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (DEVELOPER_ID,))
        conn.commit()
        
    except Error as e:
        print(f"خطأ في قاعدة البيانات: {e}")
    return conn

# إعادة تهيئة قاعدة البيانات
if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
create_connection()

# ديكوراتور التحقق من الأدمن
def is_admin(func):
    @wraps(func)
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        conn = create_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,))
        if cur.fetchone():
            return func(update, context)
        else:
            update.message.reply_text("❌ صلاحية مطلوبة: أدمن فقط!")
        conn.close()
    return wrapper

### ---------- أوامر المستخدمين ---------- ###
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    conn = create_connection()
    
    # تسجيل المستخدم
    conn.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                 (user.id, user.username or ""))
    conn.commit()
    
    # رسالة الترحيب
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='welcome_msg'")
    welcome_msg = cur.fetchone()
    
    # بناء الواجهة
    keyboard = []
    cur.execute("SELECT name FROM sections")
    sections = cur.fetchall()
    
    for section in sections:
        keyboard.append([InlineKeyboardButton(section[0], callback_data=f'section_{section[0]}')])
    
    keyboard.append([InlineKeyboardButton("📮 تواصل مع الدعم", callback_data='contact_support')])
    
    update.message.reply_text(
        welcome_msg[0] if welcome_msg else f"مرحبًا {user.first_name}!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    conn.close()

### ---------- أوامر الأدمن ---------- ###
@is_admin
def admin_panel(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("🎉 تعيين رسالة ترحيب", callback_data='set_welcome')],
        [InlineKeyboardButton("➕ إضافة قسم", callback_data='add_section')],
        [InlineKeyboardButton("📩 بث عام", callback_data='broadcast')]
    ]
    update.message.reply_text(
        "👮♂️ لوحة التحكم الإدارية:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

### ---------- معالجة الأزرار ---------- ###
def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    query.answer()
    
    if data == 'set_welcome':
        query.message.reply_text("أرسل رسالة الترحيب الجديدة:")
        return WELCOME_MSG
    
    elif data == 'add_section':
        query.message.reply_text("أرسل اسم القسم الجديد:")
        return SECTION_NAME
    
    elif data == 'contact_support':
        query.message.reply_text("✉️ أرسل رسالتك وسيتم الرد في أقرب وقت:")
        return SUPPORT_MSG
    
    return ConversationHandler.END

### ---------- إدارة الأقسام ---------- ###
def section_name(update: Update, context: CallbackContext):
    context.user_data['section_name'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("نص", callback_data='text'),
         InlineKeyboardButton("تحويل رسالة", callback_data='forward')]
    ]
    update.message.reply_text(
        "اختر نوع المحتوى:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SECTION_CONTENT

def section_content(update: Update, context: CallbackContext):
    conn = create_connection()
    try:
        conn.execute("INSERT INTO sections (name, content_type, content) VALUES (?, ?, ?)",
                    (context.user_data['section_name'], update.message.text, "محتوى مؤقت"))
        conn.commit()
        update.message.reply_text("✅ تم إضافة القسم بنجاح!")
    except Error as e:
        update.message.reply_text(f"❌ خطأ في إضافة القسم: {e}")
    finally:
        conn.close()
    return ConversationHandler.END

### ---------- معالجة المحادثات ---------- ###
def set_welcome_msg(update: Update, context: CallbackContext):
    conn = create_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ('welcome_msg', update.message.text))
        conn.commit()
        update.message.reply_text("✅ تم تحديث رسالة الترحيب!")
    except Error as e:
        update.message.reply_text(f"❌ خطأ في تحديث الرسالة: {e}")
    finally:
        conn.close()
    return ConversationHandler.END

def handle_support_msg(update: Update, context: CallbackContext):
    user = update.effective_user
    msg = (
        f"📬 رسالة دعم جديدة من:\n"
        f"المستخدم: [{user.full_name}](tg://user?id={user.id})\n"
        f"الرسالة: {update.message.text}"
    )
    
    context.bot.send_message(
        chat_id=DEVELOPER_ID,
        text=msg,
        parse_mode="Markdown"
    )
    update.message.reply_text("✅ تم إرسال رسالتك إلى فريق الدعم!")
    return ConversationHandler.END

### ---------- الإعداد الرئيسي ---------- ###
def main():
    # تهيئة الأبديتر مع الإصدار الصحيح
    updater = Updater(BOT_TOKEN, use_context=True)
    
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("admin", admin_panel))

    dp.add_handler(CallbackQueryHandler(button_handler))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={
            WELCOME_MSG: [MessageHandler(Filters.text, set_welcome_msg)],
            SECTION_NAME: [MessageHandler(Filters.text, section_name)],
            SUPPORT_MSG: [MessageHandler(Filters.text, handle_support_msg)],
            SECTION_CONTENT: [MessageHandler(Filters.text, section_content)]
        },
        fallbacks=[]
    )
    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
