import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAGArk_w-Cv3uPJkZJi7Fi4y-5KUzZI2saU"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة
LIKES_FILE = "likes_db.json"    # ملف التفاعلات
CONFIGS_FILE = "configs_db.json" # ملف حفظ الكونفيجات

bot = telebot.TeleBot(TOKEN)

# متغير لمعرفة هل الأدمن في وضع الرفع أم لا
admin_upload_mode = False

# ==============================
# 💾 دوال حفظ وتحميل البيانات
# ==============================
def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except:
            return {} if filename == LIKES_FILE else []
    return {} if filename == LIKES_FILE else []

def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except: pass

# تحميل البيانات عند التشغيل
likes_data = load_json(LIKES_FILE)       # قاموس {msg_id: [users]}
stored_configs = load_json(CONFIGS_FILE) # قائمة [file_id1, file_id2]

# ==============================
# 📤 1. نظام رفع الملفات (للأدمن)
# ==============================

@bot.message_handler(commands=['upload'])
def start_upload_mode(message):
    if message.from_user.id != ADMIN_ID: return
    
    global admin_upload_mode, stored_configs
    admin_upload_mode = True
    stored_configs = [] # تفريغ القائمة القديمة لبدء قائمة جديدة
    save_json(CONFIGS_FILE, stored_configs)
    
    bot.reply_to(message, "📂 **تم تفعيل وضع الرفع!**\n\nقم بإرسال ملفات الكونفيج الآن (واحد تلو الآخر).\nعند الانتهاء اكتب الأمر: `/done`")

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    global stored_configs
    
    # إذا كان الأدمن في وضع الرفع، نحفظ الملف
    if admin_upload_mode:
        file_id = message.document.file_id
        file_name = message.document.file_name
        
        stored_configs.append(file_id)
        save_json(CONFIGS_FILE, stored_configs)
        
        bot.reply_to(message, f"✅ تم حفظ الملف: `{file_name}`")

@bot.message_handler(commands=['done'])
def stop_upload_mode(message):
    if message.from_user.id != ADMIN_ID: return
    
    global admin_upload_mode
    if admin_upload_mode:
        admin_upload_mode = False
        count = len(stored_configs)
        bot.reply_to(message, f"🛑 **تم إنهاء الرفع.**\nعدد الملفات المحفوظة: {count}\n\nيمكنك الآن نشر البوست في القناة عبر `/config`")
    else:
        bot.reply_to(message, "⚠️ أنت لم تبدأ وضع الرفع أصلاً! استخدم `/upload` أولاً.")

# ==============================
# 📢 2. أمر النشر في القناة
# ==============================
@bot.message_handler(commands=['config'])
def send_config_post(message):
    if message.from_user.id != ADMIN_ID: return

    # التأكد من وجود ملفات
    if not stored_configs:
        bot.reply_to(message, "⚠️ **تنبيه:** لا توجد ملفات محفوظة!\nاستخدم `/upload` لرفع ملفات جديدة أولاً.")
        return

    markup = types.InlineKeyboardMarkup()
    btn_like = types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like")
    btn_get = types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file")
    
    markup.add(btn_like)
    markup.add(btn_get)
    
    msg_text = (
        "🔥 **كونفيج Dark Tunnel صاروخ!** 🚀\n\n"
        "⚡️ السرعة: عالية جداً\n"
        "🔓 المدة: مفتوحة\n\n"
        "⚠️ **شرط التحميل:** اضغط على زر القلب (❤️) في الأسفل أولاً لدعمنا!"
    )
    
    try:
        sent_msg = bot.send_message(CHANNEL_ID, msg_text, parse_mode="Markdown", reply_markup=markup)
        likes_data[str(sent_msg.message_id)] = []
        save_json(LIKES_FILE, likes_data)
        bot.reply_to(message, "✅ تم النشر!")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

# ==============================
# ❤️ 3. معالج زر الدعم
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "do_like")
def handle_like_click(call):
    try:
        user_id = call.from_user.id
        msg_id = str(call.message.message_id)
        
        # إشعار الأدمن
        username = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        
        if msg_id not in likes_data: likes_data[msg_id] = []
        
        if user_id in likes_data[msg_id]:
            bot.answer_callback_query(call.id, "⚠️ تفاعلت مسبقاً!", show_alert=True)
            return
        
        likes_data[msg_id].append(user_id)
        save_json(LIKES_FILE, likes_data)
        
        # إرسال إشعار للأدمن
        try:
            bot.send_message(ADMIN_ID, f"🔔 **تفاعل جديد:** {username}")
        except: pass

        # تحديث العداد
        count = len(likes_data[msg_id])
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"❤️ اضغط للدعم ({count})", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=msg_id, reply_markup=markup)
        bot.answer_callback_query(call.id, "✅ تم التسجيل! يمكنك التحميل.")
        
    except Exception as e:
        print(e)

# ==============================
# 📂 4. معالج الاستلام (إرسال الملفات المحفوظة)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "get_file")
def handle_get_file(call):
    try:
        user_id = call.from_user.id
        msg_id = str(call.message.message_id)
        
        # السماح للأدمن فوراً
        if user_id == ADMIN_ID:
            send_stored_files(user_id)
            bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن", show_alert=False)
            return

        # التحقق من المستخدم
        if msg_id in likes_data and user_id in likes_data[msg_id]:
            try:
                send_stored_files(user_id)
                bot.answer_callback_query(call.id, "✅ تم الإرسال!", show_alert=False)
            except:
                bot_user = bot.get_me().username
                bot.answer_callback_query(call.id, f"❌ ابدأ البوت أولاً!\n@{bot_user}", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "⛔ اضغط زر القلب (❤️) أولاً!", show_alert=True)
            
    except Exception as e:
        print(e)

def send_stored_files(user_id):
    """دالة مساعدة لإرسال جميع الملفات المحفوظة"""
    if not stored_configs:
        bot.send_message(user_id, "⚠️ عذراً، لا توجد ملفات مرفوعة حالياً.")
        return
        
    bot.send_message(user_id, "🎉 **تفضل الكونفيجات الخاصة بك:**", parse_mode="Markdown")
    for file_id in stored_configs:
        bot.send_document(user_id, file_id)

# ==============================
# 🌐 التشغيل
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>File Upload Bot Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
