import telebot
from flask import Flask
from threading import Thread
import os
import time

# ==============================
# ⚙️ إعدادات الاختبار
# ==============================
TOKEN = "8579121219:AAF1D6hqMU8BAr3IPd6rDqcUK7aTeGbYjco"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن (أنت)

bot = telebot.TeleBot(TOKEN)

# ==============================
# 🕵️‍♂️ كود الجاسوس (المراقب)
# ==============================

# هذا الكود يعمل فوراً عند وضع أي ريكشن في القناة
@bot.message_reaction_handler()
def i_see_reaction(message):
    try:
        # 1. جمع المعلومات
        chat_title = message.chat.title if message.chat.title else "قناة/مجموعة"
        chat_id = message.chat.id
        msg_id = message.message_id
        
        # معرفة من الفاعل
        user_name = "مجهول"
        user_id = "غير معروف"
        
        if message.user:
            user_name = message.user.first_name
            user_id = message.user.id
        elif message.actor_chat:
            user_name = f"قناة/مجموعة ({message.actor_chat.title})"
            user_id = message.actor_chat.id

        # 2. إرسال تقرير فوري للأدمن
        report = (
            f"🚨 **كشف تفاعل جديد!**\n\n"
            f"👤 **الفاعل:** {user_name}\n"
            f"🆔 **الآيدي:** `{user_id}`\n"
            f"📍 **المكان:** {chat_title}\n"
            f"📄 **رقم الرسالة:** `{msg_id}`\n\n"
            f"✅ **الحالة:** البوت يرى التفاعل بنجاح!"
        )
        
        bot.send_message(ADMIN_ID, report, parse_mode="Markdown")
        print(f"Reaction detected from {user_name}")

    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ حدث خطأ في الكشف: {e}")

# ==============================
# 🌐 تشغيل السيرفر
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Spy Bot Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    # إزالة الفلاتر للسماع لكل شيء
    bot.infinity_polling(allowed_updates=None, skip_pending=True)
