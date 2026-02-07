import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import time

# ==========================================
# ⚙️ الإعدادات
# ==========================================
TOKEN = "8579121219:AAH8wwIUejAsWlmk4G1O9r3AYeDGMZWAVaQ"  # ⚠️ ضع التوكن هنا
ADMIN_ID = 7846022798          # آيدي الأدمن
CHANNEL_ID = -1003858414969    # آيدي القناة
FILE_LINK = "https://t.me/AymenOxel"

bot = telebot.TeleBot(TOKEN)

# 💾 الذاكرة الحية (RAM) - أسرع من الملفات
# التنسيق: { "message_id": {user_id1, user_id2, ...} }
reactions_memory = {}

# ==========================================
# 🌐 سيرفر Render الوهمي
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
# 🤖 منطق البوت
# ==========================================

# 1. مراقبة التفاعلات (مع طباعة للتجربة)
@bot.message_reaction_handler()
def handle_reactions(message):
    try:
        # طباعة معلومات للتأكد أن البوت يرى التفاعل
        print(f"👀 New Reaction detected in Chat: {message.chat.id}")

        # التحقق من أن التفاعل في القناة الصحيحة
        if message.chat.id != CHANNEL_ID:
            print(f"❌ Ignored: Wrong Channel ID ({message.chat.id})")
            return

        # محاولة استخراج آيدي الشخص
        user_id = None
        if message.user:
            user_id = message.user.id
            print(f"👤 User detected: {user_id}")
        elif message.actor_chat:
            print(f"⚠️ Reaction by channel/group: {message.actor_chat.id}")
            # إذا تفاعل الشخص بصفته قناة، لا يمكننا التحقق منه بدقة
            return
        
        if user_id:
            msg_id = str(message.message_id)
            
            # التأكد من وجود سجل للرسالة
            if msg_id not in reactions_memory:
                reactions_memory[msg_id] = set()
            
            # حفظ المستخدم
            reactions_memory[msg_id].add(user_id)
            print(f"✅ SAVED: User {user_id} added to Message {msg_id}")
            print(f"📊 Current List for this msg: {reactions_memory[msg_id]}")

    except Exception as e:
        print(f"❌ Error in reaction handler: {e}")

# 2. أمر النشر (للأدمن فقط)
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
        
        # تهيئة الذاكرة لهذه الرسالة
        reactions_memory[str(sent_msg.message_id)] = set()
        
        bot.reply_to(message, f"✅ تم النشر! (ID: {sent_msg.message_id})")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

# 3. التحقق عند ضغط الزر
@bot.callback_query_handler(func=lambda call: call.data == "check_reaction")
def check_reaction_callback(call):
    try:
        user_id = call.from_user.id
        msg_id = str(call.message.message_id)
        
        print(f"🔎 Check Request: User {user_id} on Message {msg_id}")

        # حصانة الأدمن
        if user_id == ADMIN_ID:
            bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن!", show_alert=False)
            bot.send_message(user_id, f"📂 تفضل:\n{FILE_LINK}")
            return

        # التحقق من القائمة
        if msg_id in reactions_memory and user_id in reactions_memory[msg_id]:
            try:
                bot.send_message(user_id, f"🎉 **تفضل الكونفيج:**\n{FILE_LINK}", parse_mode="Markdown")
                bot.answer_callback_query(call.id, "✅ تم الإرسال!", show_alert=False)
            except:
                bot.answer_callback_query(call.id, "❌ ابدأ البوت في الخاص أولاً!", show_alert=True)
        else:
            # طباعة سبب الرفض في السجلات
            print(f"⛔ Denied: User {user_id} not found in {reactions_memory.get(msg_id, 'Empty')}")
            bot.answer_callback_query(call.id, "❌ لم تتفاعل!\nضع قلباً (❤️) على الرسالة في القناة أولاً.", show_alert=True)
            
    except Exception as e:
        print(f"Callback Error: {e}")

# التشغيل
if __name__ == "__main__":
    keep_alive()
    try:
        bot.remove_webhook()
        time.sleep(1)
    except: pass
    
    print("Bot started with RAM Memory...")
    bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'], timeout=20, long_polling_timeout=10)
