import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json
import time

# ==========================================
# ⚙️ إعدادات البوت
# ==========================================

# ضع توكن البوت الخاص بك هنا بدلاً من النص الموجود
TOKEN = "8579121219:AAFRtkpzmqngUUjhg3FG7EKoYHdOghTa3_c"

# رابط القناة أو الملف الذي تريد إرساله في الخاص
CHANNEL_LINK = "https://t.me/AymenOxel"

# اسم الملف الذي سنحفظ فيه بيانات المتفاعلين
DATA_FILE = "reactions_db.json"

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 💾 نظام حفظ البيانات (Database)
# ==========================================

# تحميل البيانات عند تشغيل البوت لضمان عدم نسيان التفاعلات
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            reactions_data = json.load(f)
        except:
            reactions_data = {}
else:
    reactions_data = {}

def save_data():
    """حفظ التفاعلات في ملف خارجي"""
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(reactions_data, f)
    except Exception as e:
        print(f"Error saving data: {e}")

# ==========================================
# 🌐 السيرفر الوهمي (Render Fix)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "<b>Telegram Bot is Running via Render! 🚀</b>"

def run_web_server():
    # Render يعطي منفذ (Port) تلقائي، نستخدمه هنا
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# ==========================================
# 🤖 كود البوت (Logic)
# ==========================================

# 1. استقبال وتخزين التفاعلات (Reactions)
@bot.message_reaction_handler()
def handle_reactions(message):
    try:
        user_id = message.user.id
        message_id = str(message.message_id)
        
        # التأكد من وجود سجل لهذه الرسالة
        if message_id not in reactions_data:
            reactions_data[message_id] = []
        
        # إضافة الشخص إذا لم يكن موجوداً
        if user_id not in reactions_data[message_id]:
            reactions_data[message_id].append(user_id)
            save_data()
            print(f"✅ User {user_id} reacted to msg {message_id}")
    except Exception as e:
        print(f"Error in reaction handler: {e}")

# 2. أمر نشر الكونفيج (للمشرفين فقط) - اكتب /config في القناة
@bot.message_handler(commands=['config'])
def send_config_post(message):
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
        sent_msg = bot.send_message(message.chat.id, msg_text, parse_mode="Markdown", reply_markup=markup)
        
        # فتح سجل جديد لهذه الرسالة
        reactions_data[str(sent_msg.message_id)] = []
        save_data()
    except Exception as e:
        bot.reply_to(message, f"حدث خطأ: {e}")

# 3. عند الضغط على الزر (الفحص والإرسال)
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    try:
        user_id = call.from_user.id
        message_id = str(call.message.message_id)
        
        # --- التحقق: هل تفاعل الشخص؟ ---
        if message_id in reactions_data and user_id in reactions_data[message_id]:
            # نعم، تفاعل. نحاول الإرسال للخاص
            try:
                bot.send_message(
                    user_id, 
                    f"🎉 **أهلاً بك يا بطل!**\n\nتفضل هذا هو الكونفيج الخاص بك 👇:\n{CHANNEL_LINK}", 
                    parse_mode="Markdown"
                )
                # إشعار نجاح
                bot.answer_callback_query(call.id, "✅ تم إرسال الكونفيج إلى خاصك! تفقد الرسائل.", show_alert=False)
            
            except Exception as e:
                # فشل الإرسال (لم يبدأ البوت)
                bot_username = bot.get_me().username
                bot.answer_callback_query(call.id, "❌ يجب أن تبدأ البوت في الخاص أولاً!", show_alert=True)
                
        else:
            # لا، لم يتفاعل
            bot.answer_callback_query(call.id, "❌ لم تتفاعل!\nمن فضلك ضع قلباً (❤️) على الرسالة أولاً.", show_alert=True)
            
    except Exception as e:
        print(f"Callback error: {e}")

# ==========================================
# ▶️ التشغيل (مع حل مشكلة 409)
# ==========================================
if __name__ == "__main__":
    keep_alive() # تشغيل السيرفر الوهمي
    
    # محاولة حذف أي Webhook عالق لمنع التضارب
    try:
        print("Removing old webhook...")
        bot.remove_webhook()
        time.sleep(1) 
    except Exception as e:
        print(e)
        
    print("Bot is running...")
    
    # استخدام إعدادات خاصة لمنع التضارب (timeout)
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'], timeout=20, long_polling_timeout=10)
