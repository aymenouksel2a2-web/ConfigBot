import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json
import time

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAGm7ybs8wAdRo40-Irv9nkAw-ycV6zvXGQ"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة

# ملفات التخزين
LIKES_FILE = "likes.json"
CONFIGS_FILE = "configs.json"
HISTORY_FILE = "history.json"   # 👈 هذا هو الملف الأهم للحذف

bot = telebot.TeleBot(TOKEN)

# متغيرات
admin_upload_mode = False
last_upload_msg_id = None

# ==============================
# 💾 دوال قاعدة البيانات (حفظ وتحميل)
# ==============================
def load_db(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f: return json.load(f)
        except: return {} if filename != CONFIGS_FILE else []
    return {} if filename != CONFIGS_FILE else []

def save_db(filename, data):
    try:
        with open(filename, "w") as f: json.dump(data, f)
    except: pass

# تحميل البيانات عند التشغيل
likes_db = load_db(LIKES_FILE)
configs_db = load_db(CONFIGS_FILE)
history_db = load_db(HISTORY_FILE) # { "user_id": [msg_id1, msg_id2, ...] }

# ==============================
# 🎮 لوحة تحكم الأدمن
# ==============================
@bot.message_handler(commands=['admin', 'start'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📤 رفع ملفات"), types.KeyboardButton("✅ إنهاء وحفظ"))
    markup.add(types.KeyboardButton("📢 نشر بالقناة"), types.KeyboardButton("🗑️ حذف الملفات"))
    markup.add(types.KeyboardButton("👥 المتفاعلين"), types.KeyboardButton("📊 فحص المخزن"))
    markup.add(types.KeyboardButton("❌ إخفاء اللوحة"))

    status = "🟢 مفعل" if admin_upload_mode else "🔴 مغلق"
    msg = f"👑 **لوحة الأدمن V11**\n🛡️ نظام الحذف الدائم مفعل\n📂 الملفات: `{len(configs_db)}`\n📡 الرفع: {status}"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

# ==============================
# 🕹️ الأزرار
# ==============================
@bot.message_handler(func=lambda message: message.text in [
    "📤 رفع ملفات", "✅ إنهاء وحفظ", "📢 نشر بالقناة", 
    "🗑️ حذف الملفات", "👥 المتفاعلين", "📊 فحص المخزن", "❌ إخفاء اللوحة"
])
def handle_buttons(message):
    if message.from_user.id != ADMIN_ID: return
    
    global admin_upload_mode, configs_db, likes_db, last_upload_msg_id
    action = message.text
    
    if action == "📤 رفع ملفات":
        admin_upload_mode = True
        configs_db = [] 
        save_db(CONFIGS_FILE, configs_db)
        s = bot.reply_to(message, "📂 **وضع الرفع مفعل!**\nالعداد: 0")
        last_upload_msg_id = s.message_id
        
    elif action == "✅ إنهاء وحفظ":
        admin_upload_mode = False
        last_upload_msg_id = None
        bot.reply_to(message, f"✅ **تم الحفظ!** العدد: {len(configs_db)}")

    elif action == "🗑️ حذف الملفات":
        configs_db = []
        save_db(CONFIGS_FILE, configs_db)
        bot.reply_to(message, "🗑️ تم حذف الملفات.")

    elif action == "📊 فحص المخزن":
        bot.reply_to(message, f"📊 لديك **{len(configs_db)}** ملف.")

    elif action == "👥 المتفاعلين":
        users = []
        for mid in likes_db:
            for u in likes_db[mid]:
                if isinstance(u, dict): users.append(u.get('name', 'Unknown'))
        users = list(set(users))
        if not users: bot.reply_to(message, "⚠️ لا يوجد.")
        else:
            txt = f"👥 **المتفاعلين ({len(users)}):**\n" + "\n".join([f"- {u}" for u in users])
            bot.reply_to(message, txt[:4000])

    elif action == "📢 نشر بالقناة":
        if not configs_db:
            bot.reply_to(message, "⚠️ المخزن فارغ!")
            return
        
        bot_user = bot.get_me().username
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (Start)", url=f"https://t.me/{bot_user}?start=channel"))
        
        msg_text = (
            "🔥 **كونفيج Dark Tunnel صاروخ!** 🚀\n\n"
            "⚡️ السرعة: عالية جداً\n"
            "🔓 المدة: مفتوحة\n\n"
            "⚠️ **الخطوات:**\n1. فعل البوت (🤖).\n2. ادعمنا بقلب (❤️).\n3. حمل ملفك (📥)."
        )
        try:
            sent = bot.send_message(CHANNEL_ID, msg_text, parse_mode="Markdown", reply_markup=markup)
            likes_db[str(sent.message_id)] = []
            save_db(LIKES_FILE, likes_db)
            bot.reply_to(message, "✅ **تم النشر!**")
        except Exception as e:
            bot.reply_to(message, f"❌ خطأ: {e}")

    elif action == "❌ إخفاء اللوحة":
        bot.send_message(message.chat.id, "تم.", reply_markup=types.ReplyKeyboardRemove())

# ==============================
# 📥 الرفع (Edit)
# ==============================
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    global configs_db, last_upload_msg_id
    
    if admin_upload_mode:
        configs_db.append(message.document.file_id)
        save_db(CONFIGS_FILE, configs_db)
        text = f"📂 **وضع الرفع مفعل!**\nالعداد: {len(configs_db)} ✅"
        try:
            if last_upload_msg_id: bot.edit_message_text(text, message.chat.id, last_upload_msg_id)
            else:
                s = bot.send_message(message.chat.id, text)
                last_upload_msg_id = s.message_id
        except:
            s = bot.send_message(message.chat.id, text)
            last_upload_msg_id = s.message_id

# ==============================
# ❤️ التفاعل
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "do_like")
def user_like(call):
    try:
        uid = call.from_user.id
        mid = str(call.message.message_id)
        uname = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        
        if mid not in likes_db: likes_db[mid] = []
        for u in likes_db[mid]:
            if u['id'] == uid:
                bot.answer_callback_query(call.id, "⚠️ تم الدعم مسبقاً!", show_alert=True)
                return
            
        likes_db[mid].append({'id': uid, 'name': uname})
        save_db(LIKES_FILE, likes_db)
        
        cnt = len(likes_db[mid])
        bot_user = bot.get_me().username
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"❤️ اضغط للدعم ({cnt})", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (Start)", url=f"https://t.me/{bot_user}?start=channel"))
        
        bot.edit_message_reply_markup(call.message.chat.id, mid, reply_markup=markup)
        bot.answer_callback_query(call.id, "✅ شكراً!")
    except: pass

# ==============================
# 🧹 نظام الحذف والإرسال (المنطق الجديد) 🧹
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "get_file")
def deliver_files(call):
    uid = call.from_user.id
    mid = str(call.message.message_id)
    
    # للأدمن
    if uid == ADMIN_ID:
        smart_clean_send(uid)
        bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن", show_alert=False)
        return

    # للمستخدم
    user_found = False
    if mid in likes_db:
        for u in likes_db[mid]:
            if u['id'] == uid:
                user_found = True
                break

    if user_found:
        try:
            smart_clean_send(uid)
            bot.answer_callback_query(call.id, "✅ تم التحديث!", show_alert=False)
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ ابدأ البوت أولاً (Start)", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "⛔ اضغط زر القلب ❤️ أولاً!", show_alert=True)

def smart_clean_send(user_id):
    """
    تقوم بحذف الرسائل المسجلة سابقاً في history.json
    ثم ترسل الجديد وتسجله
    """
    global history_db
    
    str_id = str(user_id)
    
    # 1. تنظيف القديم (الموجود في الذاكرة)
    if str_id in history_db:
        old_msgs = history_db[str_id]
        for msg_id in old_msgs:
            try:
                bot.delete_message(user_id, msg_id)
            except:
                pass # الرسالة محذوفة مسبقاً أو قديمة جداً
    
    # 2. إرسال الجديد
    if not configs_db:
        m = bot.send_message(user_id, "⚠️ لا توجد ملفات حالياً.")
        # نحفظ رسالة الخطأ هذه أيضاً لنحذفها لاحقاً
        history_db[str_id] = [m.message_id]
        save_db(HISTORY_FILE, history_db)
        return
    
    new_msg_ids = []
    
    # إرسال رسالة نصية
    m1 = bot.send_message(user_id, "✨ **الملفات الجديدة:**", parse_mode="Markdown")
    new_msg_ids.append(m1.message_id)
    
    # إرسال الملفات
    for fid in configs_db:
        m_doc = bot.send_document(user_id, fid)
        new_msg_ids.append(m_doc.message_id)
        
    # 3. تحديث الذاكرة الدائمة
    history_db[str_id] = new_msg_ids
    save_db(HISTORY_FILE, history_db) # 👈 حفظ فوري في الملف

# ==============================
# 🌐 التشغيل
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Bot V11 (Persistent Memory) Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=40)
