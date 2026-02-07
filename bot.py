import telebot
from flask import Flask
from threading import Thread
import os
import time

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAHQqKm7ZqLwXI-apTV-erlwW0pX-1ovRjA"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن (أنت)
CHANNEL_ID = -1003858414969     # ⚠️ ضع آيدي القناة هنا (تأكد أنه صحيح)

bot = telebot.TeleBot(TOKEN)

# ==============================
# 📨 1. أمر الإرسال (/config)
# ==============================
@bot.message_handler(commands=['config'])
def send_test_message(message):
    # حماية: للأدمن فقط
    if message.from_user.id != ADMIN_ID: return

    try:
        sent_msg = bot.send_message(
            CHANNEL_ID, 
            "🧪 **رسالة اختبار الجاسوس** 🕵️‍♂️\n\nقم بوضع قلب (❤️) على هذه الرسالة الآن لنرى هل البوت يعمل أم لا!",
            parse_mode="Markdown"
        )
        bot.reply_to(message, f"✅ تم الإرسال للقناة بنجاح!\nID الرسالة: {sent_msg.message_id}")
    except Exception as e:
        bot.reply_to(message, f"❌ فشل الإرسال للقناة!\nالسبب: {e}\n\nتأكد أن الآيدي صحيح وأن البوت مشرف (Admin).")

# ==============================
# 🕵️‍♂️ 2. كود الجاسوس (كاشف التفاعل)
# ==============================
@bot.message_reaction_handler()
def i_see_reaction(message):
    try:
        # بيانات التفاعل
        user_name = message.user.first_name if message.user else "قناة/مجهول"
        user_id = message.user.id if message.user else "Unknown"
        chat_title = message.chat.title if message.chat.title else "شات"

        # إرسال تقرير فوري للأدمن
        report = (
            f"🚨 **كشف تفاعل جديد!** (ناجح 100%)\n\n"
            f"👤 **الفاعل:** {user_name}\n"
            f"🆔 **الآيدي:** `{user_id}`\n"
            f"📍 **المكان:** {chat_title}\n"
        )
        bot.send_message(ADMIN_ID, report, parse_mode="Markdown")
        print(f"Reaction detected from {user_name}")

    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ حدث خطأ في الكشف: {e}")

# ==============================
# 🆔 3. كاشف الآيدي (مساعدة)
# ==============================
# هذا الجزء سيرسل لك آيدي القناة إذا كتبت أي شيء فيها (لتعرف الآيدي الجديد)
@bot.message_handler(func=lambda m: True)
def get_channel_id(message):
    if message.chat.type == "channel":
        try:
            bot.send_message(ADMIN_ID, f"📢 **آيدي هذه القناة هو:**\n`{message.chat.id}`", parse_mode="Markdown")
        except: pass

# ==============================
# 🌐 تشغيل السيرفر
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Spy Bot V2 Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    # إزالة الفلاتر (مهم جداً)
    bot.infinity_polling(allowed_updates=None, skip_pending=True)
