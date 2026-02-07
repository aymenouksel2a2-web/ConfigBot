import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json
import time

# ==========================================
# ⚙️ الإعدادات (تأكد من التوكن والآيدي الخاص بك)
# ==========================================
TOKEN = "8579121219:AAHhAsbZBXp0DtSY6KyOhSrbLEFrucarYR8"   # ⚠️ ضع التوكن هنا
ADMIN_ID = 7846022798           # آيدي الأدمن (أنت)
FILE_LINK = "https://t.me/AymenOxel"
DATA_FILE = "reactions_db.json"

bot = telebot.TeleBot(TOKEN)

# تحميل قاعدة البيانات
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r") as f:
            reactions_data = json.load(f)
    except:
        reactions_data = {}
else:
    reactions_data = {}

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(reactions_data, f)
    except: pass

# سيرفر وهمي
app = Flask('')
@app.route('/')
def home(): return "<b>Bot Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# ==========================================
# 🕵️‍♂️ المصحح الذكي (Debug System)
# ==========================================

def send_debug_to_admin(text):
    """دالة ترسل تقريراً للأدمن في الخاص لمعرفة ماذا يحدث"""
    try:
        bot.send_message(ADMIN_ID, f"🛠️ **تقرير:**\n{text}", parse_mode="Markdown")
    except: pass

# 1. صائد التفاعلات (مفتوح لكل القنوات للتجربة)
@bot.message_reaction_handler()
def handle_reactions(message):
    try:
        chat_id = message.chat.id
        user_id = None
        user_name = "Unknown"

        if message.user:
            user_id = message.user.id
            user_name = message.user.first_name
        
        # 🚨 تقرير فوري للأدمن
        debug_msg = (
            f"👀 **رصدت تفاعلاً جديداً!**\n"
            f"🆔 القناة: `{chat_id}`\n"
            f"👤 الشخص: {user_name} (`{user_id}`)\n"
            f"📄 الرسالة: `{message.message_id}`"
        )
        send_debug_to_admin(debug_msg)

        if user_id:
            msg_id = str(message.message_id)
            if msg_id not in reactions_data: reactions_data[msg_id] = []
            
            if user_id not in reactions_data[msg_id]:
                reactions_data[msg_id].append(user_id)
                save_data()
                send_debug_to_admin("✅ **تم حفظ الشخص في القائمة!**")
            else:
                send_debug_to_admin("ℹ️ الشخص موجود مسبقاً.")

    except Exception as e:
        send_debug_to_admin(f"❌ خطأ في النظام: {e}")

# 2. أمر النشر
@bot.message_handler(commands=['config'])
def send_config_post(message):
    if message.from_user.id != ADMIN_ID: return

    # اطلب من الأدمن آيدي القناة
    msg = bot.reply_to(message, "أرسل لي الآن **آيدي القناة** (أو المعرف مثل @channel) التي تريد النشر فيها:")
    bot.register_next_step_handler(msg, process_channel_id)

def process_channel_id(message):
    try:
        target_channel = message.text
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton("📥 استلام الكونفيج (الخاص)", callback_data="check_reaction")
        markup.add(btn)
        
        sent_msg = bot.send_message(target_channel, "🔥 **اختبار البوت الجديد**\n\nاضغط لايك (❤️) ثم اضغط الزر.", reply_markup=markup)
        
        reactions_data[str(sent_msg.message_id)] = []
        save_data()
        bot.reply_to(message, f"✅ تم النشر في {target_channel}!\nالآيدي الحقيقي هو: `{sent_msg.chat.id}`")
        
    except Exception as e:
        bot.reply_to(message, f"❌ فشل النشر: {e}\nتأكد أن البوت **مشرف (Admin)** في القناة.")

# 3. فحص الزر
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    try:
        user_id = call.from_user.id
        msg_id = str(call.message.message_id)
        
        # حصانة الأدمن
        if user_id == ADMIN_ID:
            bot.answer_callback_query(call.id, "👑 مرحباً أدمن (تجاوز)", show_alert=False)
            bot.send_message(user_id, f"📂 ملفك:\n{FILE_LINK}")
            return

        if msg_id in reactions_data and user_id in reactions_data[msg_id]:
            bot.send_message(user_id, f"🎉 تفضل:\n{FILE_LINK}")
            bot.answer_callback_query(call.id, "✅ تم الإرسال!", show_alert=False)
        else:
            bot.answer_callback_query(call.id, "❌ لم يتم الرصد!\nجرب إزالة اللايك ووضعه مرة أخرى.", show_alert=True)
            # إرسال تقرير للأدمن يوضح سبب الفشل
            send_debug_to_admin(f"⛔ فشل التحقق للمستخدم {user_id}.\nالقائمة المسجلة لهذه الرسالة: {reactions_data.get(msg_id, 'فارغة')}")

    except Exception as e:
        print(e)

if __name__ == "__main__":
    keep_alive()
    try: bot.remove_webhook(); time.sleep(1)
    except: pass
    bot.infinity_polling(skip_pending=True)

