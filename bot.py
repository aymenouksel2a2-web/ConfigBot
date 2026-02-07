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

# 1. ضع توكن البوت الخاص بك هنا
TOKEN = "8579121219:AAFRtkpzmqngUUjhg3FG7EKoYHdOghTa3_c" 

# اسم القناة أو الرابط الذي تريد إرساله (مثال)
CHANNEL_LINK = "https://t.me/AymenOxel" 

# اسم الملف الذي سنحفظ فيه البيانات
DATA_FILE = "reactions_db.json"

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 💾 نظام حفظ البيانات (Database)
# ==========================================

# تحميل البيانات عند تشغيل البوت
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            reactions_data = json.load(f)
        except:
            reactions_data = {}
else:
    reactions_data = {}

def save_data():
    """حفظ التفاعلات في ملف خارجي لضمان عدم ضياعها"""
    with open(DATA_FILE, "w") as f:
        json.dump(reactions_data, f)

# ==========================================
# 🌐 السيرفر الوهمي (Render Fix)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "<b>Telegram Bot is Running via Render! 🚀</b>"

def run_web_server():
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
    user_id = message.user.id
    message_id = str(message.message_id) # نحوله لنص لأن JSON لا يقبل أرقاماً كمفاتيح
    
    # التأكد من وجود سجل لهذه الرسالة
    if message_id not in reactions_data:
        reactions_data[message_id] = []
    
    # إضافة الشخص إذا لم يكن موجوداً
    if user_id not in reactions_data[message_id]:
        reactions_data[message_id].append(user_id)
        save_data() # حفظ فوري
        print(f"✅ User {user_id} reacted to msg {message_id}")

# 2. أمر نشر الكونفيج (للمشرفين فقط)
@bot.message_handler(commands=['config'])
def send_config_post(message):
    # إنشاء الزر
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("📥 استلام الكونفيج (الخاص)", callback_data="check_reaction")
    markup.add(btn)
    
    # نص الرسالة
    msg_text = (
        "🔥 **كونفيج Dark Tunnel صاروخ!** 🚀\n\n"
        "⚡️ السرعة: عالية جداً\n"
        "🔓 المدة: مفتوحة\n\n"
        "⚠️ **ملاحظة هامة:** لن تتمكن من استلام الملف إلا إذا وضعت تفاعلاً (❤️ / 🔥 / 👍) على هذه الرسالة!"
    )
    
    sent_msg = bot.send_message(message.chat.id, msg_text, parse_mode="Markdown", reply_markup=markup)
    
    # فتح سجل جديد لهذه الرسالة في قاعدة البيانات
    reactions_data[str(sent_msg.message_id)] = []
    save_data()

# 3. عند الضغط على الزر (الفحص والإرسال)
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    user_id = call.from_user.id
    message_id = str(call.message.message_id)
    
    # --- التحقق: هل تفاعل الشخص؟ ---
    if message_id in reactions_data and user_id in reactions_data[message_id]:
        # نعم، تفاعل. نحاول الإرسال للخاص
        try:
            # هنا نرسل الملف أو الرابط في الخاص
            bot.send_message(
                user_id, 
                f"🎉 **أهلاً بك يا بطل!**\n\nتفضل هذا هو الكونفيج الخاص بك 👇:\n{CHANNEL_LINK}", 
                parse_mode="Markdown"
            )
            
            # إشعار نجاح (يختفي بعد ثواني)
            bot.answer_callback_query(call.id, "✅ تم إرسال الكونفيج إلى خاصك! تفقد الرسائل.", show_alert=False)
            
        except Exception as e:
            # فشل الإرسال (غالباً لأن الشخص لم يبدأ البوت)
            bot_username = bot.get_me().username
            error_msg = (
                "❌ **عذراً، لا أستطيع مراسلتك!**\n\n"
                "🔒 قوانين تيليجرام تمنعني من إرسال رسائل لمن لم يبدأ المحادثة.\n\n"
                f"1️⃣ ادخل هنا: @{bot_username}\n"
                "2️⃣ اضغط 'Start' أو 'بدء'\n"
                "3️⃣ ارجع هنا واضغط الزر مجدداً."
            )
            bot.answer_callback_query(call.id, "❌ يجب أن تبدأ البوت في الخاص أولاً!", show_alert=True)
            bot.send_message(call.message.chat.id, error_msg) # إرسال تنبيه في المجموعة أيضاً (اختياري)
            
    else:
        # لا، لم يتفاعل
        bot.answer_callback_query(call.id, "❌ لم تتفاعل!\nمن فضلك ضع قلباً (❤️) على الرسالة أولاً.", show_alert=True)

# ==========================================
# ▶️ التشغيل
# ==========================================
if __name__ == "__main__":
    keep_alive() # تشغيل السيرفر الوهمي
    print("Bot is running...")
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'])
