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

# ضع توكن البوت الخاص بك هنا
TOKEN = "8579121219:AAGT5OZmZSU4p_-jm2taPrFwRTNyfKcrFvw"

# 🔒 الآيدي الخاص بالمجموعة المسموح لها فقط
ALLOWED_GROUP_ID = -1003858414969 

# رابط القناة أو الملف
CHANNEL_LINK = "https://t.me/AymenOxel"

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

# 1. استقبال وتخزين التفاعلات (فقط من المجموعة المحددة)
@bot.message_reaction_handler()
def handle_reactions(message):
    try:
        # 🔒 نقطة تفتيش: هل التفاعل حدث في مجموعتك؟
        if message.chat.id != ALLOWED_GROUP_ID:
            return # تجاهل أي تفاعل خارج المجموعة

        user_id = message.user.id
        message_id = str(message.message_id)
        
        if message_id not in reactions_data:
            reactions_data[message_id] = []
        
        if user_id not in reactions_data[message_id]:
            reactions_data[message_id].append(user_id)
            save_data()
            print(f"✅ User {user_id} reacted in Allowed Group")
    except Exception as e:
        print(f"Error in reaction: {e}")

# 2. أمر نشر الكونفيج (يعمل فقط داخل المجموعة)
@bot.message_handler(commands=['config'])
def send_config_post(message):
    # 🔒 نقطة تفتيش: هل الأمر مكتوب في مجموعتك؟
    if message.chat.id != ALLOWED_GROUP_ID:
        # اختياري: يمكنك الرد عليه بأنه ممنوع، أو تجاهله
        bot.reply_to(message, "❌ عذراً، هذا البوت يعمل حصرياً في مجموعة Aymen Oxel فقط.")
        return

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
        reactions_data[str(sent_msg.message_id)] = []
        save_data()
    except Exception as e:
        bot.reply_to(message, f"خطأ: {e}")

# 3. عند الضغط على الزر
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    try:
        # 🔒 نقطة تفتيش: هل الزر المضغوط موجود في رسالة داخل مجموعتك؟
        if call.message.chat.id != ALLOWED_GROUP_ID:
            bot.answer_callback_query(call.id, "❌ هذا الزر لا يعمل خارج المجموعة الأصلية!", show_alert=True)
            return

        user_id = call.from_user.id
        message_id = str(call.message.message_id)
        
        # التحقق من التفاعل
        if message_id in reactions_data and user_id in reactions_data[message_id]:
            try:
                bot.send_message(
                    user_id, 
                    f"🎉 **أهلاً بك يا بطل!**\n\nتفضل هذا هو الكونفيج الخاص بك 👇:\n{CHANNEL_LINK}", 
                    parse_mode="Markdown"
                )
                bot.answer_callback_query(call.id, "✅ تم إرسال الكونفيج إلى خاصك!", show_alert=False)
            
            except Exception as e:
                bot_username = bot.get_me().username
                bot.answer_callback_query(call.id, "❌ يجب أن تبدأ البوت في الخاص أولاً!", show_alert=True)
                
        else:
            bot.answer_callback_query(call.id, "❌ لم تتفاعل!\nمن فضلك ضع قلباً (❤️) على الرسالة أولاً.", show_alert=True)
            
    except Exception as e:
        print(f"Callback error: {e}")

# ==========================================
# ▶️ التشغيل
# ==========================================
if __name__ == "__main__":
    keep_alive()
    
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass
        
    print(f"Bot started for Group ID: {ALLOWED_GROUP_ID}...")
    
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'], timeout=20, long_polling_timeout=10)
