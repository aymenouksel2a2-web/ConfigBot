import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAF6YbkMttlGKzk38VpdyQj_7SgPjvT5kL4"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة

# أسماء ملفات البيانات
LIKES_FILE = "likes_users_db.json"    # المتفاعلين
CONFIGS_FILE = "configs_db.json"      # الكونفيجات
HISTORY_FILE = "history_db.json"      # سجل رسائل الأعضاء (للحذف)

bot = telebot.TeleBot(TOKEN)

# متغيرات التشغيل
admin_upload_mode = False
last_upload_msg_id = None # لتعديل رسالة العداد

# ==============================
# 💾 الدوال المساعدة (قواعد البيانات)
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

# تحميل البيانات عند البدء
likes_data = load_json(LIKES_FILE)
stored_configs = load_json(CONFIGS_FILE)
user_history = load_json(HISTORY_FILE) # {user_id: [msg_id1, msg_id2]}

# ==============================
# 🎮 لوحة تحكم الأدمن V8
# ==============================
@bot.message_handler(commands=['admin', 'start'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🤖 هذا البوت لخدمة القناة فقط.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    markup.add(types.KeyboardButton("📤 رفع ملفات"), types.KeyboardButton("✅ إنهاء وحفظ"))
    markup.add(types.KeyboardButton("📢 نشر بالقناة"), types.KeyboardButton("🗑️ تصفير شامل (Reset)")) # الزر الجديد
    markup.add(types.KeyboardButton("👥 المتفاعلين"), types.KeyboardButton("📊 فحص المخزن"))
    markup.add(types.KeyboardButton("❌ إخفاء اللوحة"))

    status = "🟢 مفعل" if admin_upload_mode else "🔴 مغلق"
    files_count = len(stored_configs)
    
    msg = (
        "👑 **لوحة تحكم الأدمن V8** (النسخة النظيفة)\n\n"
        f"📂 الملفات الجاهزة: `{files_count}`\n"
        f"📡 وضع الرفع: {status}\n\n"
        "👇 **التحكم:**"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

# ==============================
# 🕹️ معالج الأزرار
# ==============================
@bot.message_handler(func=lambda message: message.text in [
    "📤 رفع ملفات", "✅ إنهاء وحفظ", "📢 نشر بالقناة", 
    "🗑️ تصفير شامل (Reset)", "👥 المتفاعلين", "📊 فحص المخزن", "❌ إخفاء اللوحة"
])
def handle_admin_buttons(message):
    if message.from_user.id != ADMIN_ID: return
    
    global admin_upload_mode, stored_configs, likes_data, user_history, last_upload_msg_id
    action = message.text
    
    # 1. زر رفع الملفات
    if action == "📤 رفع ملفات":
        admin_upload_mode = True
        stored_configs = [] 
        save_json(CONFIGS_FILE, stored_configs)
        sent = bot.reply_to(message, "📂 **وضع الرفع مفعل!**\nالعداد: 0")
        last_upload_msg_id = sent.message_id # نحفظ الآيدي لنعدل عليه لاحقاً
        
    # 2. زر الإنهاء
    elif action == "✅ إنهاء وحفظ":
        admin_upload_mode = False
        last_upload_msg_id = None
        bot.reply_to(message, f"✅ **تم الحفظ!** العدد النهائي: {len(stored_configs)}")

    # 3. زر التصفير الشامل (الجديد)
    elif action == "🗑️ تصفير شامل (Reset)":
        # مسح كل المتغيرات
        stored_configs = []
        likes_data = {}
        user_history = {}
        
        # مسح الملفات
        save_json(CONFIGS_FILE, stored_configs)
        save_json(LIKES_FILE, likes_data)
        save_json(HISTORY_FILE, user_history)
        
        bot.reply_to(message, "♻️ **تم فرمتة البوت بنجاح!**\n- تم حذف الكونفيجات.\n- تم حذف قائمة المتفاعلين.\n- تم حذف سجلات الرسائل.")

    # 4. زر الفحص
    elif action == "📊 فحص المخزن":
        bot.reply_to(message, f"📊 لديك **{len(stored_configs)}** ملف جاهز.")

    # 5. زر المتفاعلين
    elif action == "👥 المتفاعلين":
        users_list = []
        for msg_id in likes_data:
            for user_info in likes_data[msg_id]:
                if isinstance(user_info, dict):
                    users_list.append(user_info.get('name', 'Unknown'))
        
        users_list = list(set(users_list)) # إزالة التكرار
        
        if not users_list:
            bot.reply_to(message, "⚠️ لا يوجد متفاعلين.")
        else:
            text = f"👥 **المتفاعلين ({len(users_list)}):**\n\n" + "\n".join([f"{i+1}. {u}" for i, u in enumerate(users_list)])
            if len(text) > 4000: text = text[:4000] + "\n..."
            bot.reply_to(message, text)

    # 6. زر النشر
    elif action == "📢 نشر بالقناة":
        if not stored_configs:
            bot.reply_to(message, "⚠️ المخزن فارغ!")
            return
        
        bot_user = bot.get_me().username
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (اضغط هنا)", url=f"https://t.me/{bot_user}?start=channel"))
        
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

    # 7. إخفاء
    elif action == "❌ إخفاء اللوحة":
        bot.send_message(message.chat.id, "تم الإخفاء.", reply_markup=types.ReplyKeyboardRemove())

# ==============================
# 📥 استقبال الملفات (تعديل الرسالة - Edit)
# ==============================
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    
    global stored_configs, last_upload_msg_id
    
    if admin_upload_mode:
        # حفظ الملف
        stored_configs.append(message.document.file_id)
        save_json(CONFIGS_FILE, stored_configs)
        
        # تعديل الرسالة الموجودة بدلاً من إرسال جديدة
        new_text = f"📂 **وضع الرفع مفعل!**\nالعداد: {len(stored_configs)} ✅"
        
        try:
            if last_upload_msg_id:
                bot.edit_message_text(new_text, message.chat.id, last_upload_msg_id)
            else:
                # إذا لم تكن هناك رسالة سابقة، نرسل واحدة
                sent = bot.send_message(message.chat.id, new_text)
                last_upload_msg_id = sent.message_id
        except:
            # في حال فشل التعديل (مثلاً مسحت الرسالة)، نرسل جديدة
            sent = bot.send_message(message.chat.id, new_text)
            last_upload_msg_id = sent.message_id

# ==============================
# ❤️ معالجة التفاعل
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "do_like")
def user_like(call):
    try:
        uid = call.from_user.id
        mid = str(call.message.message_id)
        username = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        
        if mid not in likes_data: likes_data[mid] = []
        
        # التحقق من التكرار
        for user in likes_data[mid]:
            if user['id'] == uid:
                bot.answer_callback_query(call.id, "⚠️ تم الدعم مسبقاً!", show_alert=True)
                return
            
        likes_data[mid].append({'id': uid, 'name': username})
        save_json(LIKES_FILE, likes_data)
        
        # تحديث الزر
        count = len(likes_data[mid])
        bot_user = bot.get_me().username
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"❤️ اضغط للدعم ({count})", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (اضغط هنا)", url=f"https://t.me/{bot_user}?start=channel"))
        
        bot.edit_message_reply_markup(call.message.chat.id, mid, reply_markup=markup)
        bot.answer_callback_query(call.id, "✅ شكراً لك!")
    except: pass

# ==============================
# 📂 تسليم الملفات (مع التنظيف الذكي 🧹)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "get_file")
def deliver_files(call):
    uid = call.from_user.id
    mid = str(call.message.message_id)
    
    if uid == ADMIN_ID:
        clean_and_send(uid) # للأدمن أيضاً
        bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن", show_alert=False)
        return

    # فحص التفاعل
    user_found = False
    if mid in likes_data:
        for user in likes_data[mid]:
            if user['id'] == uid:
                user_found = True
                break

    if user_found:
        try:
            clean_and_send(uid)
            bot.answer_callback_query(call.id, "✅ تم تحديث الملفات في الخاص!", show_alert=False)
        except:
            bot.answer_callback_query(call.id, "❌ يجب تفعيل البوت أولاً! 🤖", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "⛔ اضغط زر القلب ❤️ أولاً!", show_alert=True)

def clean_and_send(uid):
    """دالة تقوم بحذف الرسائل القديمة وإرسال الجديدة"""
    global user_history
    
    # 1. تنظيف القديم 🧹
    if str(uid) in user_history:
        old_messages = user_history[str(uid)]
        for msg_id in old_messages:
            try:
                bot.delete_message(uid, msg_id)
            except:
                pass # نتجاهل الخطأ إذا كانت الرسالة محذوفة أصلاً
    
    # 2. إرسال الجديد 📤
    if not stored_configs:
        bot.send_message(uid, "⚠️ لا توجد ملفات جديدة.")
        return
    
    new_messages_ids = []
    
    # رسالة ترحيبية (اختياري)
    m = bot.send_message(uid, "🎉 **ملفاتك الجديدة جاهزة:**", parse_mode="Markdown")
    new_messages_ids.append(m.message_id)
    
    for fid in stored_configs:
        m = bot.send_document(uid, fid)
        new_messages_ids.append(m.message_id)
        
    # 3. حفظ السجل الجديد 💾
    user_history[str(uid)] = new_messages_ids
    save_json(HISTORY_FILE, user_history)

# ==============================
# 🌐 التشغيل
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Bot V8 (Clean Mode) Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=40)
