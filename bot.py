import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json
import time

# ==========================================
# ⚙️ إعدادات البوت والتحكم
# ==========================================

# 1. ضع توكن البوت الخاص بك هنا
TOKEN = "8579121219:AAH3x0eUrmYAjV4htqDRgt81jCU6iUPyBnk"

# 2. آيدي الأدمن (أنت فقط من يتحكم بالبوت)
ADMIN_ID = 7846022798

# 3. آيدي القناة التي سينشر فيها البوت
CHANNEL_ID = -1003858414969

# رابط الملف أو القناة الذي سيصل للمستخدم
FILE_LINK = "https://t.me/AymenOxel"

# اسم ملف قاعدة البيانات
DATA_FILE = "reactions_db.json"

bot = telebot.TeleBot(TOKEN)

# ==========================================
# 💾 نظام حفظ البيانات
# ==========================================

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
        print(f"Error saving data: {e}")

# ==========================================
# 🌐 السيرفر الوهمي (Render Fix)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "<b>Admin Control Bot is Running! 🚀</b>"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# ==========================================
# 🤖 كود البوت (المنطق الجديد)
# ==========================================

# 1. أمر النشر (يعمل فقط في خاص الأدمن)
@bot.message_handler(commands=['config'])
def send_config_post(message):
    # 🔒 التحقق: هل المرسل هو الأدمن (7846022798)؟
    if message.from_user.id != ADMIN_ID:
        # إذا شخص غريب حاول استخدام الأمر، نتجاهله
        return

    # إعداد الزر
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
        # 🔥 هنا السحر: البوت يرسل الرسالة للقناة (وليس لك)
        sent_msg = bot.send_message(CHANNEL_ID, msg_text, parse_mode="Markdown", reply_markup=markup)
        
        # حفظ رقم الرسالة الجديدة لمراقبتها
        reactions_data[str(sent_msg.message_id)] = []
        save_data()
        
        # رسالة تأكيد لك أنت في الخاص
        bot.reply_to(message, "✅ تم نشر الكونفيج في القناة بنجاح يا زعيم!")
        
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ أثناء النشر: {e}")

# 2. استقبال وتخزين التفاعلات (يراقب القناة)
@bot.message_reaction_handler()
def handle_reactions(message):
    try:
        # التأكد أن التفاعل حدث في القناة المطلوبة
        if message.chat.id != CHANNEL_ID:
            return

        user_id = message.user.id
        message_id = str(message.message_id)
        
        if message_id not in reactions_data:
            reactions_data[message_id] = []
        
        if user_id not in reactions_data[message_id]:
            reactions_data[message_id].append(user_id)
            save_data()
            print(f"✅ User {user_id} reacted in Channel")
            
    except Exception as e:
        print(f"Reaction Error: {e}")

# 3. عند الضغط على الزر (التحقق والإرسال)
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    try:
        user_id = call.from_user.id
        message_id = str(call.message.message_id)
        
        # التحقق: هل الشخص وضع تفاعلاً؟
        if message_id in reactions_data and user_id in reactions_data[message_id]:
            try:
                # إرسال الملف للشخص في الخاص
                bot.send_message(
                    user_id, 
                    f"🎉 **أهلاً بك!**\n\nتفضل الكونفيج المطلوب 👇:\n{FILE_LINK}", 
                    parse_mode="Markdown"
                )
                bot.answer_callback_query(call.id, "✅ تم الإرسال لخاصك!", show_alert=False)
            
            except:
                # إذا كان البوت محظوراً من الشخص
                bot.answer_callback_query(call.id, "❌ ابدأ البوت في الخاص أولاً!", show_alert=True)
                
        else:
            bot.answer_callback_query(call.id, "❌ لم تتفاعل!\nضع قلباً (❤️) على رسالة القناة أولاً.", show_alert=True)
            
    except Exception as e:
        print(f"Callback Error: {e}")

# ==========================================
# ▶️ التشغيل
# ==========================================
if __name__ == "__main__":
    keep_alive()
    
    # حذف الويب هوك القديم لتجنب التضارب
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
        
    print(f"Bot started... Admin: {ADMIN_ID} -> Channel: {CHANNEL_ID}")
    
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'], timeout=20, long_polling_timeout=10)

