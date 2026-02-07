import telebot
from flask import Flask
from threading import Thread
import os

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAFyM_Tai5pTIpRBYGzzBvYzJTeR0QmCDM8"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة

bot = telebot.TeleBot(TOKEN)

# ==============================
# 🕵️‍♂️ الجاسوس (كاشف التفاعل)
# ==============================
@bot.message_reaction_handler()
def i_see_reaction(message):
    try:
        user_name = message.user.first_name if message.user else "مجهول/قناة"
        user_id = message.user.id if message.user else 0
        chat_id = message.chat.id
        
        # طباعة في اللوج
        print(f"👀 Reaction Detected! User: {user_name} ({user_id}) in Chat: {chat_id}")

        # إرسال تقرير للأدمن
        bot.send_message(ADMIN_ID, f"🚨 **كشفنا واحد!**\n👤 {user_name} (`{user_id}`)\n❤️ وضع تفاعلاً في القناة!")

    except Exception as e:
        print(f"Error: {e}")

# ==============================
# 📨 أمر التجربة
# ==============================
@bot.message_handler(commands=['config'])
def send_test(message):
    if message.from_user.id == ADMIN_ID:
        # إرسال رسالة جديدة للقناة
        msg = bot.send_message(CHANNEL_ID, "🧪 **رسالة اختبار الجاسوس** 🕵️‍♂️\n\nضع قلباً (❤️) هنا الآن!")
        bot.reply_to(message, "✅ تم الإرسال للقناة. اذهب وضع قلباً!")

# تشغيل السيرفر
app = Flask('')
@app.route('/')
def home(): return "<b>Spy Bot Running (v4.26.0)</b>"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    # فتح كل التحديثات (مهم جداً)
    print("Bot started...")
    bot.infinity_polling(allowed_updates=None, skip_pending=True)
