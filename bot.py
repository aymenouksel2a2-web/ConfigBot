import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json
import time

# ==========================================
# ⚙️ الإعدادات (تأكد من صحتها)
# ==========================================
TOKEN = "8579121219:AAHJSTY9rwumBc9wEXYiRgt_P5AyGoseyUU"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة
FILE_LINK = "https://t.me/AymenOxel"
DATA_FILE = "reactions_db.json" # اسم ملف الحفظ

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 💾 قاعدة البيانات (ملف JSON)
# ==========================================
# تحميل البيانات عند التشغيل
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r") as f:
            reactions_data = json.load(f)
            print("✅ Database loaded successfully.")
    except:
        reactions_data = {}
        print("⚠️ Database created new.")
else:
    reactions_data = {}

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(reactions_data, f)
    except Exception as e:
        print(f"Error saving data: {e}")

# ==========================================
# 🌐 سيرفر Render
# ==========================================
app = Flask('')
@app.route('/')
def home(): return "<b>Bot is Running!</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# ==========================================
# 🤖 المنطق والذكاء
# ==========================================

# 1. صائد التفاعلات (مهم جداً)
@bot.message_reaction_handler()
def handle_reactions(message):
    try:
        # 1. التأكد أن التفاعل في القناة الصحيحة
        if message.chat.id != CHANNEL_ID:
            print(f"Ignored reaction from wrong chat: {message.chat.id}")
            return

        # 2. معرفة من تفاعل
        user_id = None
        if message.user:
            user_id = message.user.id
        elif message.actor_chat:
            # هذا يحدث إذا تفاعل شخص بصفته قناة أو مجموعة
            print(f"Reaction from Channel/Group Actor: {message.actor_chat.id}")
            return
        
        # 3. الحفظ
        if user_id:
            msg_id = str(message.message_id)
            
            # التأكد من وجود سجل للرسالة
            if msg_id not in reactions_data:
                reactions_data[msg_id] = []
            
            # إضافة الشخص إذا لم يكن موجوداً
            if user_id not in reactions_data[msg_id]:
                reactions_data[msg_id].append(user_id)
                save_data()
                print(f"✅ CAPTURED: User {user_id} reacted to {msg_id}")
            else:
                print(f"ℹ️ User {user_id} already exists.")

    except Exception as e:
        print(f"❌ Error in handler: {e}")

# 2. أمر النشر (للأدمن)
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
        
        # تهيئة القائمة لهذه الرسالة
        reactions_data[str(sent_msg.message_id)] = []
        save_data()
        
        bot.reply_to(message, f"✅ تم النشر! (ID: {sent_msg.message_id})")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

# 3. التحقق (مع الحل الذكي)
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    try:
        user_id = call.from_user.id
        msg_id = str(call.message.message_id)
        
        print(f"🔎 Checking User: {user_id} on Msg: {msg_id}")

        # 👑 حصانة الأدمن
        if user_id == ADMIN_ID:
            bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن!", show_alert=False)
            bot.send_message(user_id, f"📂 تفضل (نسخة الأدمن):\n{FILE_LINK}")
            return

        # 🔍 فحص الأعضاء
        # هل الرسالة موجودة في البيانات؟ وهل المستخدم موجود فيها؟
        if msg_id in reactions_data and user_id in reactions_data[msg_id]:
            try:
                bot.send_message(user_id, f"🎉 **تفضل الكونفيج:**\n{FILE_LINK}", parse_mode="Markdown")
                bot.answer_callback_query(call.id, "✅ تم الإرسال!", show_alert=False)
            except:
                bot.answer_callback_query(call.id, "❌ ابدأ البوت في الخاص أولاً!", show_alert=True)
        else:
            # 💡 هنا الحل الذكي: نطلب منهم إعادة التفاعل
            error_msg = (
                "❌ **لم يتم رصد تفاعلك!**\n\n"
                "🔄 **الحل:** قم بإزالة التفاعل (Remove Reaction) ثم ضعه مرة أخرى الآن.\n"
                "ثم اضغط الزر مجدداً."
            )
            bot.answer_callback_query(call.id, error_msg, show_alert=True)
            
    except Exception as e:
        print(f"Callback Error: {e}")

# التشغيل
if __name__ == "__main__":
    keep_alive()
    try:
        bot.remove_webhook()
        time.sleep(1)
    except: pass
    
    print("Bot started with JSON Database...")
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'], timeout=20, long_polling_timeout=10)
