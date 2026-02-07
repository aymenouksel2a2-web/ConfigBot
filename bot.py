# ==========================================
# 🤖 التعديلات الجديدة (انسخ هذا الكود بالكامل وضعه في bot.py)
# ==========================================

import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json
import time

# ⚙️ إعدادات البوت
TOKEN = "8579121219:AAEB8rO0TvG2hSAvOYVsUcfF5sPS4oStz-c"  # ⚠️ ضع التوكن الخاص بك هنا
ADMIN_ID = 7846022798          # آيدي الأدمن (أنت)
CHANNEL_ID = -1003858414969    # آيدي القناة
FILE_LINK = "https://t.me/AymenOxel"
DATA_FILE = "reactions_db.json"

bot = telebot.TeleBot(TOKEN)

# 💾 نظام حفظ البيانات
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            reactions_data = json.load(f)
        except:
            reactions_data = {}
else:
    reactions_data = {}

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(reactions_data, f)
    except Exception as e:
        print(f"Error saving: {e}")

# 🌐 سيرفر Render
app = Flask('')
@app.route('/')
def home(): return "<b>Bot is Running!</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# ---------------------------------------------
# 👇 المنطق الجديد والمحسن 👇
# ---------------------------------------------

# 1. نشر الكونفيج (أمر خاص بالأدمن)
@bot.message_handler(commands=['config'])
def send_config_post(message):
    if message.from_user.id != ADMIN_ID: return

    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("📥 استلام الكونفيج (الخاص)", callback_data="check_reaction")
    markup.add(btn)
    
    msg_text = (
        "🔥 **كونفيج Dark Tunnel صاروخ!** 🚀\n\n"
        "⚡️ السرعة: عالية جداً\n"
        "🔓 المدة: مفتوحة\n\n"
        "⚠️ **هام:** لن تستلم الملف إلا إذا وضعت تفاعلاً (❤️ / 🔥 / 👍) على هذه الرسالة!"
    )
    
    try:
        sent_msg = bot.send_message(CHANNEL_ID, msg_text, parse_mode="Markdown", reply_markup=markup)
        reactions_data[str(sent_msg.message_id)] = []
        save_data()
        bot.reply_to(message, "✅ تم النشر في القناة!")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

# 2. تسجيل التفاعلات (مع إصلاح مشكلة الأدمن)
@bot.message_reaction_handler()
def handle_reactions(message):
    try:
        if message.chat.id != CHANNEL_ID: return

        # محاولة جلب الآيدي سواء كان مستخدماً عادياً أو أدمن
        user_id = None
        if message.user:
            user_id = message.user.id
        elif message.actor_chat: # في حال تفاعل الشخص بصفته القناة
             # هنا نتجاهل تفاعل القناة لأنه لا يطابق الآيدي الشخصي
             print(f"Reaction from channel/chat: {message.actor_chat.id}")
             return

        if user_id:
            message_id = str(message.message_id)
            if message_id not in reactions_data: reactions_data[message_id] = []
            
            if user_id not in reactions_data[message_id]:
                reactions_data[message_id].append(user_id)
                save_data()
                print(f"✅ Saved reaction from user: {user_id}")

    except Exception as e:
        print(f"Reaction Error: {e}")

# 3. فحص التفاعل (مع كود الحصانة للأدمن 🔥)
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    try:
        user_id = call.from_user.id
        message_id = str(call.message.message_id)
        
        # 🔥🔥🔥 الحصانة: إذا كان المستخدم هو الأدمن، أرسل الملف فوراً بدون فحص
        if user_id == ADMIN_ID:
            bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن! (تم تجاوز الفحص)", show_alert=False)
            bot.send_message(user_id, f"📂 تفضل يا زعيم:\n{FILE_LINK}")
            return # انتهى هنا للأدمن

        # --- الفحص لباقي الأعضاء ---
        if message_id in reactions_data and user_id in reactions_data[message_id]:
            try:
                bot.send_message(user_id, f"🎉 **تفضل الكونفيج:**\n{FILE_LINK}", parse_mode="Markdown")
                bot.answer_callback_query(call.id, "✅ تم الإرسال!", show_alert=False)
            except:
                bot.answer_callback_query(call.id, "❌ ابدأ البوت في الخاص أولاً!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ لم تتفاعل!\nيجب وضع قلب (❤️) على المنشور في القناة.", show_alert=True)
            
    except Exception as e:
        print(f"Callback Error: {e}")

# التشغيل
if __name__ == "__main__":
    keep_alive()
    try:
        bot.remove_webhook()
        time.sleep(1)
    except: pass
    print("Bot is running...")
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'], timeout=20, long_polling_timeout=10)
