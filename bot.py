import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json

# ------------------- 1. إعدادات البوت -------------------
# ضع التوكن الخاص بك هنا
TOKEN = "8579121219:AAFRtkpzmqngUUjhg3FG7EKoYHdOghTa3_c"
bot = telebot.TeleBot(TOKEN)

# اسم الملف الذي سنحفظ فيه التفاعلات
DATA_FILE = "reactions_db.json"

# تحميل البيانات القديمة عند تشغيل البوت
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            # البيانات تكون على شكل: "message_id": [user_id1, user_id2, ...]
            reactions_data = json.load(f)
        except:
            reactions_data = {}
else:
    reactions_data = {}

def save_data():
    """وظيفة لحفظ التفاعلات في الملف"""
    with open(DATA_FILE, "w") as f:
        json.dump(reactions_data, f)

# ------------------- 2. السيرفر الوهمي (لحل مشكلة Render) -------------------
app = Flask('')

@app.route('/')
def home():
    return "<b>Telegram Bot is Running!</b>"

def run_web_server():
    # Render يعطينا بورت تلقائي، نستخدمه هنا
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# ------------------- 3. كود البوت والذكاء -------------------

# استقبال التفاعلات (قلب، نار، الخ)
@bot.message_reaction_handler()
def handle_reactions(message):
    user_id = message.user.id
    message_id = str(message.message_id) # نحوله لنص ليسهل حفظه
    chat_id = message.chat.id

    # التأكد أن الرسالة مسجلة في القاموس
    if message_id not in reactions_data:
        reactions_data[message_id] = []
    
    # إضافة الشخص إذا لم يكن موجوداً
    if user_id not in reactions_data[message_id]:
        reactions_data[message_id].append(user_id)
        save_data() # حفظ في الملف
        print(f"User {user_id} reacted to message {message_id}")

# أمر نشر الكونفيج (للمشرفين)
@bot.message_handler(commands=['config'])
def send_config_post(message):
    markup = types.InlineKeyboardMarkup()
    # الزر يحتوي على "callback_data" مميز لنتحقق لاحقاً
    btn = types.InlineKeyboardButton("📥 تحميل الكونفيج (Dark Tunnel)", callback_data="check_reaction")
    markup.add(btn)
    
    sent_msg = bot.send_message(
        message.chat.id, 
        "🔥 **كونفيج Dark Tunnel جديد!**\n\n⚡️ السرعة: صاروخ\n🔓 المدة: مفتوحة\n\n⚠️ **لتحميل الملف: يجب أن تضع تفاعلاً (❤️ أو 🔥) على هذه الرسالة أولاً!**", 
        parse_mode="Markdown", 
        reply_markup=markup
    )
    # تهيئة سجل لهذه الرسالة الجديدة
    reactions_data[str(sent_msg.message_id)] = []
    save_data()

# عند الضغط على الزر
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    user_id = call.from_user.id
    message_id = str(call.message.message_id) # رقم الرسالة التي ضغط عليها

    # التحقق: هل رقم هذا الشخص موجود في قائمة من تفاعلوا على هذه الرسالة؟
    if message_id in reactions_data and user_id in reactions_data[message_id]:
        # نعم، تفاعل
        bot.answer_callback_query(call.id, "✅ تم التحقق! جاري الإرسال...")
        
        # --- هنا تضع رابط الملف أو ترفعه ---
        try:
            bot.send_message(user_id, "📂 **تفضل ملف الكونفيج:**\nhttps://t.me/AymenOxel", parse_mode="Markdown")
        except:
            # لو كان حظر البوت في الخاص
            bot.answer_callback_query(call.id, "❌ لا أستطيع مراسلتك، ابدأ البوت في الخاص أولاً!", show_alert=True)
            
    else:
        # لا، لم يتفاعل
        bot.answer_callback_query(call.id, "❌ لم تتفاعل!\nيجب وضع (❤️) على الرسالة في القناة أولاً.", show_alert=True)

# ------------------- 4. التشغيل -------------------
keep_alive() # تشغيل السيرفر الوهمي أولاً
bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'])
