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
TOKEN = "8579121219:AAEDfEOa3KZXRImkRNIuUMHKPvw-yD0l7f4"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة

# الملفات
LIKES_FILE = "likes_users_db.json"
CONFIGS_FILE = "configs_db.json"
HISTORY_FILE = "history_db.json" # هنا ذاكرة الحذف

bot = telebot.TeleBot(TOKEN)

# متغيرات التشغيل
admin_upload_mode = False
last_upload_msg_id = None

# ==============================
# 💾 قاعدة البيانات
# ==============================
def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f: return json.load(f)
        except: return {} if filename != CONFIGS_FILE else []
    return {} if filename != CONFIGS_FILE else []

def save_json(filename, data):
    try:
        with open(filename, "w") as f: json.dump(data, f)
    except: pass

likes_data = load_json(LIKES_FILE)
stored_configs = load_json(CONFIGS_FILE)
user_history = load_json(HISTORY_FILE) # {user_id: [id1, id2, id3...]}

# ==============================
# 🎮 لوحة تحكم الأدمن
# ==============================
@bot.message_handler(commands=['admin', 'start'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        # إذا كان عضواً عادياً، لا نرد عليه برسالة تبقى، بل نحذفها لاحقاً إن أمكن
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📤 رفع ملفات"), types.KeyboardButton("✅ إنهاء وحفظ"))
    markup.add(types.KeyboardButton("📢 نشر بالقناة"), types.KeyboardButton("🗑️ تصفير شامل (Reset)"))
    markup.add(types.KeyboardButton("👥 المتفاعلين"), types.KeyboardButton("📊 فحص المخزن"))
    markup.add(types.KeyboardButton("❌ إخفاء اللوحة"))

    status = "🟢 مفعل" if admin_upload_mode else "🔴 مغلق"
    count = len(stored_configs)
    
    msg = (
        "👑 **لوحة تحكم الأدمن V9**\n"
        "✨ **ميزة التنظيف الكامل مفعلة**\n\n"
        f"📂 الملفات: `{count}`\n"
        f"📡 الوضع: {status}"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

# ==============================
# 🕹️ الأزرار
# ==============================
@bot.message_handler(func=lambda message: message.text in [
    "📤 رفع ملفات", "✅ إنهاء وحفظ", "📢 نشر بالقناة", 
    "🗑️ تصفير شامل (Reset)", "👥 المتفاعلين", "📊 فحص المخزن", "❌ إخفاء اللوحة"
])
def handle_buttons(message):
    if message.from_user.id != ADMIN_ID: return
    
    global admin_upload_mode, stored_configs, likes_data, user_history, last_upload_msg_id
    action = message.text
    
    if action == "📤 رفع ملفات":
        admin_upload_mode = True
        stored_configs = [] 
        save_json(CONFIGS_FILE, stored_configs)
        sent = bot.reply_to(message, "📂 **وضع الرفع مفعل!**\nالعداد: 0")
        last_upload_msg_id = sent.message_id
        
    elif action == "✅ إنهاء وحفظ":
        admin_upload_mode = False
        last_upload_msg_id = None
        bot.reply_to(message, f"✅ **تم الحفظ!** العدد: {len(stored_configs)}")

    elif action == "🗑️ تصفير شامل (Reset)":
        stored_configs = []
        likes_data = {}
        user_history = {} # ⚠️ تحذير: هذا يمسح ذاكرة الرسائل القديمة
        save_json(CONFIGS_FILE, stored_configs)
        save_json(LIKES_FILE, likes_data)
        save_json(HISTORY_FILE, user_history)
        bot.reply_to(message, "♻️ **تم الفرمتة!**\nالآن البوت نظيف تماماً.")

    elif action == "📊 فحص المخزن":
        bot.reply_to(message, f"📊 لديك **{len(stored_configs)}** ملف.")

    elif action == "👥 المتفاعلين":
        users = []
        for mid in likes_data:
            for u in likes_data[mid]:
                if isinstance(u, dict): users.append(u.get('name', 'Unknown'))
        users = list(set(users))
        if not users: bot.reply_to(message, "⚠️ لا يوجد.")
        else:
            txt = f"👥 **المتفاعلين ({len(users)}):**\n\n" + "\n".join([f"- {u}" for u in users])
            bot.reply_to(message, txt[:4000])

    elif action == "📢 نشر بالقناة":
        if not stored_configs:
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
            likes_data[str(sent.message_id)] = []
            save_json(LIKES_FILE, likes_data)
            bot.reply_to(message, "✅ **تم النشر!**")
        except Exception as e:
            bot.reply_to(message, f"❌ خطأ: {e}")

    elif action == "❌ إخفاء اللوحة":
        bot.send_message(message.chat.id, "تم.", reply_markup=types.ReplyKeyboardRemove())

# ==============================
# 📥 الرفع (Edit Message)
# ==============================
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    global stored_configs, last_upload_msg_id
    
    if admin_upload_mode:
        stored_configs.append(message.document.file_id)
        save_json(CONFIGS_FILE, stored_configs)
        text = f"📂 **وضع الرفع مفعل!**\nالعداد: {len(stored_configs)} ✅"
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
        
        if mid not in likes_data: likes_data[mid] = []
        for u in likes_data[mid]:
            if u['id'] == uid:
                bot.answer_callback_query(call.id, "⚠️ تم الدعم مسبقاً!", show_alert=True)
                return
            
        likes_data[mid].append({'id': uid, 'name': uname})
        save_json(LIKES_FILE, likes_data)
        
        cnt = len(likes_data[mid])
        bot_user = bot.get_me().username
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"❤️ اضغط للدعم ({cnt})", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (Start)", url=f"https://t.me/{bot_user}?start=channel"))
        
        bot.edit_message_reply_markup(call.message.chat.id, mid, reply_markup=markup)
        bot.answer_callback_query(call.id, "✅ شكراً!")
    except: pass

# ==============================
# 🧹🧹🧹 نظام التنظيف العنيف والإرسال 🧹🧹🧹
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "get_file")
def deliver_files(call):
    uid = call.from_user.id
    mid = str(call.message.message_id)
    
    # الأدمن
    if uid == ADMIN_ID:
        clean_and_send_aggressive(uid)
        bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن", show_alert=False)
        return

    # المستخدم
    user_found = False
    if mid in likes_data:
        for u in likes_data[mid]:
            if u['id'] == uid:
                user_found = True
                break

    if user_found:
        try:
            # هنا نستدعي دالة التنظيف
            clean_and_send_aggressive(uid)
            bot.answer_callback_query(call.id, "✅ تم تحديث الملفات!", show_alert=False)
        except Exception as e:
            # إذا فشل، غالباً البوت لم يبدأ
            bot.answer_callback_query(call.id, "❌ ابدأ البوت أولاً (Start)", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "⛔ اضغط زر القلب ❤️ أولاً!", show_alert=True)

def clean_and_send_aggressive(uid):
    """
    هذه الدالة تقوم بحذف كل رسالة تم تسجيلها لهذا المستخدم
    ثم ترسل الجديد وتسجله
    """
    global user_history
    
    str_uid = str(uid)
    
    # 1. مرحلة التنظيف (الحذف)
    if str_uid in user_history:
        # ننسخ القائمة لنحذفها بأمان
        messages_to_delete = user_history[str_uid]
        
        for msg_id in messages_to_delete:
            try:
                bot.delete_message(uid, msg_id)
                time.sleep(0.05) # تأخير بسيط جداً لتجنب ضغط السيرفر
            except:
                # إذا كانت الرسالة محذوفة مسبقاً أو قديمة جداً، نتجاهل الخطأ
                pass
        
        # بعد الحذف، نصفر القائمة لهذا المستخدم
        user_history[str_uid] = []
    
    # 2. مرحلة الإرسال والحفظ
    if not stored_configs:
        # نرسل رسالة تحذير ونحفظ آيديها أيضاً لنحذفه لاحقاً
        m = bot.send_message(uid, "⚠️ لا توجد ملفات حالياً.")
        if str_uid not in user_history: user_history[str_uid] = []
        user_history[str_uid].append(m.message_id)
        save_json(HISTORY_FILE, user_history)
        return
    
    new_ids = []
    
    # إرسال رسالة نصية
    m1 = bot.send_message(uid, "🎉 **تفضل الملفات الجديدة:**", parse_mode="Markdown")
    new_ids.append(m1.message_id)
    
    # إرسال الملفات
    for fid in stored_configs:
        m_doc = bot.send_document(uid, fid)
        new_ids.append(m_doc.message_id)
        
    # حفظ الآيديات الجديدة في السجل
    if str_uid not in user_history: user_history[str_uid] = []
    
    # ⚠️ نستخدم extend لإضافة الجديد إلى القائمة (في حال وجود بقايا)
    user_history[str_uid].extend(new_ids)
    
    save_json(HISTORY_FILE, user_history)

# ==============================
# 🌐 التشغيل
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Bot V9 (Cleaner) Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    print("Bot started...")
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=40)
