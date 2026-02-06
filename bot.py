import telebot
from telebot import types
import os

# 1. ضع توكن البوت الخاص بك هنا بين علامتي التنصيص
TOKEN = "8579121219:AAFRtkpzmqngUUjhg3FG7EKoYHdOghTa3_c"

bot = telebot.TeleBot(TOKEN)
reacted_users = set()

print("Bot started...")

# استقبال التفاعلات
@bot.message_reaction_handler()
def handle_reactions(message):
    user_id = message.user.id
    chat_id = message.chat.id
    # حفظ المستخدم في الذاكرة
    reacted_users.add(user_id)
    print(f"User {user_id} reacted in chat {chat_id}")

# أمر نشر الكونفيج (اكتب /config في القناة أو القروب)
@bot.message_handler(commands=['config'])
def send_config_post(message):
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("📥 تحميل ملف Dark Tunnel", callback_data="get_file")
    markup.add(btn)
    bot.send_message(message.chat.id, "🔥 **كونفيج VIP سريع جداً**\n\n⚠️ للتحميل: ضع تفاعل (❤️) على هذه الرسالة أولاً!", parse_mode="Markdown", reply_markup=markup)

# عند الضغط على الزر
@bot.callback_query_handler(func=lambda call: call.data == "get_file")
def check_reaction(call):
    user_id = call.from_user.id
    if user_id in reacted_users:
        bot.answer_callback_query(call.id, "✅ جاري الإرسال...")
        # هنا يرسل الملف (مثال)
        bot.send_message(user_id, "تفضل الكونفيج:\n https://t.me/AymenOxel") 
    else:
        bot.answer_callback_query(call.id, "❌ ضع لايك/رياكشن على الرسالة أولاً!", show_alert=True)

# تشغيل البوت بشكل دائم
bot.infinity_polling(allowed_updates=['message', 'callback_query', 'message_reaction'])