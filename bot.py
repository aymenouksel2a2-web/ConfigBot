import telebot
import flask
from flask import Flask
from threading import Thread
import os

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAG-t6MhfudeJKYT3_T6ipJ1hHl58p9kntA"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة

# طباعة رقم الإصدار للتأكد
print(f"🤖 المكتبة الحالية: {telebot.__version__}")

bot = telebot.TeleBot(TOKEN)

# ==============================
# 🕵️‍♂️ الجاسوس (كاشف التفاعل)
# ==============================
@bot.message_reaction_handler()
def i_see_reaction(message):
    try:
        user_name = message.user.first_name if message.user else "مجهول/قناة"
        user_id = message.user.id if message.user else 0
        
        # إرسال تقرير للأدمن
        bot.send_message(ADMIN_ID, f"🚨 **كشفنا واحد!**\n👤 {user_name} (`{user_id}`)\n❤️ وضع تفاعلاً!")
        print(f"Reaction detected from {user_name}")

    except Exception as e:
        print(f"Error: {e}")

# ==============================
# 📨 أمر التجربة
# ==============================
@bot.message_handler(commands=['config'])
def send_test(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(CHANNEL_ID, "🧪 **رسالة اختبار جديدة**\nضع قلباً هنا!")
        bot.reply_to(message, f"✅ تم الإرسال. إصدار البوت: {telebot.__version__}")

# تشغيل السيرفر
app = Flask('')
@app.route('/')
def home(): return f"<b>Ver: {telebot.__version__}</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    # فتح كل التحديثات
    bot.infinity_polling(allowed_updates=None, skip_pending=True)
