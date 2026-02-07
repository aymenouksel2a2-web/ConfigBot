import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import sqlite3
import time
import logging

# ==============================
# CONFIGURATION
# ==============================
TOKEN = "8579121219:AAHes3A9ELlqg9lKGXJUOM4_mVc7zQ7K5cc"   # ضع توكن البوت هنا
ADMIN_ID = 7846022798           # ضع معرف الأدمن هنا
CHANNEL_ID = -1003858414969     # ضع معرف القناة (مع العلامة السالبة)
DB_NAME = "vpn_bot.db"

bot = telebot.TeleBot(TOKEN)

# Runtime Modes
admin_upload_mode = False
broadcast_mode = False
last_status_msg_id = None

# ==============================
# DATABASE MANAGER (SQLite)
# ==============================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # جدول المستخدمين (للإذاعة والتتبع)
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 user_id INTEGER PRIMARY KEY,
                 username TEXT,
                 first_name TEXT,
                 join_date TEXT
                 )''')
    # جدول الملفات (الكونفيجات)
    c.execute('''CREATE TABLE IF NOT EXISTS configs (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 file_id TEXT,
                 upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                 )''')
    # جدول التفاعلات (لايكات القنوات)
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
                 post_message_id INTEGER,
                 user_id INTEGER,
                 username TEXT,
                 PRIMARY KEY (post_message_id, user_id)
                 )''')
    # جدول سجل الرسائل (للمسح الذكي)
    c.execute('''CREATE TABLE IF NOT EXISTS history (
                 user_id INTEGER,
                 message_id INTEGER,
                 PRIMARY KEY (user_id, message_id)
                 )''')
    conn.commit()
    conn.close()

def execute_query(query, data=(), fetch="none", commit=False):
    """دالة مساعدة للتعامل مع قاعدة البيانات بأمان"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(query, data)
        if commit: conn.commit()
        if fetch == "all": return c.fetchall()
        elif fetch == "one": return c.fetchone()
        return None
    except Exception as e:
        logging.error(f"DB Error: {e}")
        return None
    finally:
        conn.close()

# تشغيل قاعدة البيانات عند البدء
init_db()

# ==============================
# ADMIN PANEL
# ==============================
@bot.message_handler(commands=['admin', 'start'])
def admin_panel(message):
    # تسجيل المستخدم في قاعدة البيانات عند البدء
    uid = message.from_user.id
    uname = message.from_user.username or "Unknown"
    fname = message.from_user.first_name or "User"
    execute_query("INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, datetime('now'))", 
                  (uid, uname, fname), commit=True)

    if message.from_user.id != ADMIN_ID: 
        # رسالة ترحيبية للمستخدمين العاديين
        bot.reply_to(message, "أهلاً بك في بوت الكونفيجات!\nتابع قناتنا للحصول على أحدث الملفات.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btns = [
        "📤 رفع ملفات", "✅ إنهاء وحفظ",
        "📢 نشر بالقناة", "📣 إذاعة للجميع",
        "🗑️ حذف الملفات", "👥 المتفاعلين",
        "❌ إخفاء اللوحة"
    ]
    markup.add(*[types.KeyboardButton(b) for b in btns])

    # جلب عدد الملفات
    configs_count = execute_query("SELECT COUNT(*) FROM configs", fetch="one")[0]
    status_upload = "🟢 مفعل" if admin_upload_mode else "🔴 مغلق"
    status_bc = "🟢 مفعل" if broadcast_mode else "🔴 مغلق"

    msg = f"👑 **Admin Panel V12 (SQLite)**\n" \
          f"💾 Database: Secure\n" \
          f"📂 Files: `{configs_count}`\n" \
          f"📡 Upload: {status_upload}\n" \
          f"📣 Broadcast: {status_bc}"
    
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

# ==============================
# ADMIN ACTIONS & BROADCAST
# ==============================
@bot.message_handler(func=lambda m: m.text in [
    "📤 رفع ملفات", "✅ إنهاء وحفظ", "📢 نشر بالقناة", 
    "🗑️ حذف الملفات", "👥 المتفاعلين", "❌ إخفاء اللوحة", "📣 إذاعة للجميع"
])
def handle_buttons(message):
    if message.from_user.id != ADMIN_ID: return
    global admin_upload_mode, broadcast_mode, last_status_msg_id
    action = message.text
    
    if action == "📤 رفع ملفات":
        admin_upload_mode = True
        execute_query("DELETE FROM configs", commit=True) # تنظيف القديم عند رفع دفعة جديدة
        s = bot.reply_to(message, "📂 **Upload Mode ON**\nالعدد الحالي: 0", parse_mode="Markdown")
        last_status_msg_id = s.message_id
        
    elif action == "✅ إنهاء وحفظ":
        admin_upload_mode = False
        last_status_msg_id = None
        count = execute_query("SELECT COUNT(*) FROM configs", fetch="one")[0]
        bot.reply_to(message, f"✅ **تم الحفظ!**\nعدد الملفات: {count}")

    elif action == "📣 إذاعة للجميع":
        broadcast_mode = not broadcast_mode # Toggle
        status = "مفعل" if broadcast_mode else "مغلق"
        bot.reply_to(message, f"📣 وضع الإذاعة: {status}\nأرسل الرسالة الآن إذا كان مفعل.")

    elif action == "🗑️ حذف الملفات":
        execute_query("DELETE FROM configs", commit=True)
        bot.reply_to(message, "🗑️ تم حذف جميع الملفات من المخزن.")

    elif action == "👥 المتفاعلين":
        # جلب المستخدمين المميزين (من جدول likes)
        liked_users = execute_query("SELECT DISTINCT username FROM likes", fetch="all")
        liked_users = [u[0] if u[0] else "Anonymous" for u in liked_users]
        unique_users = list(set(liked_users))
        
        if not unique_users:
            bot.reply_to(message, "⚠️ لا يوجد تفاعلات حتى الآن.")
        else:
            txt = f"👥 **المتفاعلون ({len(unique_users)}):**\n" + "\n".join([f"- {u}" for u in unique_users])
            bot.reply_to(message, txt[:4090]) # حدود تيليجرام

    elif action == "📢 نشر بالقناة":
        configs = execute_query("SELECT file_id FROM configs", fetch="all")
        if not configs:
            bot.reply_to(message, "⚠️ لا توجد ملفات للنشر!")
            return
        
        bot_user = bot.get_me().username
        markup = types.InlineKeyboardMarkup()
        
        # التحقق من عدد اللايكات الحقيقي (هنا سنعرض 0 لأن المنشور جديد)
        markup.add(types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت", url=f"https://t.me/{bot_user}?start=channel"))
        
        msg_text = (
            "🔥 **تحديث جديد: كونفيجات سريعة!** 🚀\n\n"
            "⚡️ سرعة عالية\n"
            "🔓 غير محدود\n\n"
            "⚠️ **خطوات الحصول عليها:**\n1. اضغط تفعيل البوت (🤖).\n2. اضغط زر الدعم (❤️).\n3. اضغط استلام (📥)."
        )
        try:
            sent = bot.send_message(CHANNEL_ID, msg_text, parse_mode="Markdown", reply_markup=markup)
            # لا نحتاج لإضافة سجل في likes للمنشور لأن المستخدمين سيضيفونه عند التفاعل
            bot.reply_to(message, "✅ تم النشر في القناة!")
        except Exception as e:
            bot.reply_to(message, f"❌ خطأ: {e}")

    elif action == "❌ إخفاء اللوحة":
        bot.send_message(message.chat.id, "Panel Hidden.", reply_markup=types.ReplyKeyboardRemove())

# ==============================
# FILE UPLOAD & BROADCAST HANDLER
# ==============================
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice'])
def handle_content(message):
    if message.from_user.id != ADMIN_ID: return
    global admin_upload_mode, last_status_msg_id

    # 1. معالجة الإذاعة (Broadcast)
    if broadcast_mode:
        users = execute_query("SELECT user_id FROM users", fetch="all")
        success = 0
        failed = 0
        for user in users:
            try:
                if message.text:
                    bot.send_message(user[0], message.text)
                elif message.photo:
                    bot.send_photo(user[0], message.photo[-1].file_id, caption=message.caption)
                elif message.document:
                    bot.send_document(user[0], message.document.file_id, caption=message.caption)
                success += 1
                time.sleep(0.05) # تأخير بسيط لتجنب الحظر
            except:
                failed += 1
        broadcast_mode = False
        bot.reply_to(message, f"✅ **تم الإذاعة**\n✅ تم الإرسال: {success}\n❌ فشل: {failed}")
        return

    # 2. معالجة رفع الملفات
    if message.content_type == 'document' and admin_upload_mode:
        file_id = message.document.file_id
        execute_query("INSERT INTO configs (file_id) VALUES (?)", (file_id,), commit=True)
        
        # تحديث رسالة العداد
        count = execute_query("SELECT COUNT(*) FROM configs", fetch="one")[0]
        text = f"📂 **Uploading...**\nCounter: {count} ✅"
        try:
            if last_status_msg_id:
                bot.edit_message_text(text, message.chat.id, last_status_msg_id)
            else:
                s = bot.send_message(message.chat.id, text, parse_mode="Markdown")
                last_status_msg_id = s.message_id
        except:
            pass

# ==============================
# FAKE REACTION HANDLER (SQLite)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "do_like")
def user_like(call):
    try:
        uid = call.from_user.id
        mid = call.message.message_id
        uname = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        
        # محاولة الإدراج (إذا كان موجوداً سيفشل بسبب PRIMARY KEY)
        try:
            execute_query("INSERT INTO likes (post_message_id, user_id, username) VALUES (?, ?, ?)", 
                          (mid, uid, uname), commit=True)
            
            # نجاح اللايك
            cnt = execute_query("SELECT COUNT(*) FROM likes WHERE post_message_id = ?", (mid,), fetch="one")[0]
            
            bot_user = bot.get_me().username
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(f"❤️ اضغط للدعم ({cnt})", callback_data="do_like"))
            markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
            markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت", url=f"https://t.me/{bot_user}?start=channel"))
            
            bot.edit_message_reply_markup(call.message.chat.id, mid, reply_markup=markup)
            bot.answer_callback_query(call.id, "✅ شكراً لدعمك!")
        except sqlite3.IntegrityError:
            # المستخدم قد ضغط لايك من قبل
            bot.answer_callback_query(call.id, "⚠️ لقد قمت بالدعم مسبقاً!", show_alert=True)
            
    except Exception as e:
        logging.error(f"Like Error: {e}")

# ==============================
# DELIVERY & CLEANING SYSTEM (SQLite)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "get_file")
def deliver_files(call):
    uid = call.from_user.id
    mid = call.message.message_id
    
    # تجاوز الأدمن
    if uid == ADMIN_ID:
        smart_clean_send(uid)
        bot.answer_callback_query(call.id, "👑 Admin Access", show_alert=False)
        return

    # التحقق من التفاعل (لايك)
    check = execute_query("SELECT * FROM likes WHERE post_message_id = ? AND user_id = ?", (mid, uid), fetch="one")
    
    if check:
        try:
            smart_clean_send(uid)
            bot.answer_callback_query(call.id, "✅ Files Sent!", show_alert=False)
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ ابدأ البوت أولاً (Start)!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "⛔ يجب الضغط على زر الدعم (❤️) أولاً!", show_alert=True)

def smart_clean_send(user_id):
    # 1. حذف الرسائل القديمة
    old_msgs = execute_query("SELECT message_id FROM history WHERE user_id = ?", (user_id,), fetch="all")
    if old_msgs:
        for msg in old_msgs:
            try:
                bot.delete_message(user_id, msg[0])
            except: pass
        # حذف السجل القديم
        execute_query("DELETE FROM history WHERE user_id = ?", (user_id,), commit=True)
    
    # 2. إرسال الملفات الجديدة
    configs = execute_query("SELECT file_id FROM configs", fetch="all")
    new_msg_ids = []
    
    if not configs:
        m = bot.send_message(user_id, "⚠️ لا توجد ملفات متاحة حالياً.")
        execute_query("INSERT INTO history (user_id, message_id) VALUES (?, ?)", (user_id, m.message_id), commit=True)
        return

    m1 = bot.send_message(user_id, "✨ **New Configs:**", parse_mode="Markdown")
    new_msg_ids.append(m1.message_id)
    
    for config in configs:
        fid = config[0]
        m_doc = bot.send_document(user_id, fid)
        new_msg_ids.append(m_doc.message_id)
        
    # 3. حفظ السجل الجديد
    for mid in new_msg_ids:
        execute_query("INSERT INTO history (user_id, message_id) VALUES (?, ?)", (user_id, mid), commit=True)

# ==============================
# SERVER & KEEP ALIVE
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Bot V12 (SQLite) Running...</b>"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    logging.basicConfig(level=logging.INFO)
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=40)
