import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAE_qzT4J4i1ZsgQwDbNfZG1n9l_8h1XBVk"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة
FILE_LINK = "https://t.me/AymenOxel"
DATA_FILE = "likes_db.json"

bot = telebot.TeleBot(TOKEN)

# ==============================
# 💾 قاعدة البيانات
# ==============================
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r") as f:
            likes_data = json.load(f)
    except:
        likes_data = {}
else:
    likes_data = {}

def save_data():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(likes_data, f)
    except: pass

# ==============================
# 📨 أمر النشر (للأدمن)
# ==============================
@bot.message_handler(commands=['config'])
def send_config_post(message):
    if message.from_user.id != ADMIN_ID: return

    # تحضير الأزرار
    markup = types.InlineKeyboardMarkup()
    btn_like = types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like")
    btn_get = types.InlineKeyboardButton("📥 استلام الكونفيج", callback_data="get_file")
    
    markup.add(btn_like)
    markup.add(btn_get)
    
    msg_text = (
        "🔥 **كونفيج Dark Tunnel صاروخ!** 🚀\n\n"
        "⚡️ السرعة: عالية جداً\n"
        "🔓 المدة: مفتوحة\n\n"
        "⚠️ **شرط التحميل:** اضغط على زر القلب (❤️) في الأسفل أولاً لتثبت تفاعلك!"
    )
    
    try:
        sent_msg = bot.send_message(CHANNEL_ID, msg_text, parse_mode="Markdown", reply_markup=markup)
        likes_data[str(sent_msg.message_id)] = []
        save_data()
        bot.reply_to(message, "✅ تم النشر بالتحديثات الجديدة!")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

# ==============================
# ❤️ معالج زر الدعم (مع إشعار الأدمن)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "do_like")
def handle_like_click(call):
    try:
        user_id = call.from_user.id
        msg_id = str(call.message.message_id)
        
        # جلب اسم المستخدم لإشعار الأدمن
        username = call.from_user.username
        first_name = call.from_user.first_name
        
        # تنسيق اسم الشخص (يوزر أو اسم)
        user_tag = f"@{username}" if username else f"{first_name}"
        
        if msg_id not in likes_data: likes_data[msg_id] = []
        
        # هل الشخص تفاعل مسبقاً؟
        if user_id in likes_data[msg_id]:
            bot.answer_callback_query(call.id, "⚠️ لقد دعمتنا مسبقاً! شكراً لك ❤️", show_alert=True)
            return
        
        # 1. تسجيل التفاعل
        likes_data[msg_id].append(user_id)
        save_data()
        
        # 2. إشعار الأدمن فوراً 🔔
        try:
            bot.send_message(
                ADMIN_ID, 
                f"🔔 **تفاعل جديد!**\n\n👤 العضو: {user_tag}\n🆔 الآيدي: `{user_id}`\n❤️ ضغط على زر الدعم.",
                parse_mode="Markdown"
            )
        except: pass # تجاهل الخطأ إذا لم يستطع إرسال إشعار للأدمن

        # 3. تحديث العداد في الزر
        count = len(likes_data[msg_id])
        markup = types.InlineKeyboardMarkup()
        btn_like = types.InlineKeyboardButton(f"❤️ اضغط للدعم ({count})", callback_data="do_like")
        btn_get = types.InlineKeyboardButton("📥 استلام الكونفيج", callback_data="get_file")
        markup.add(btn_like)
        markup.add(btn_get)
        
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=msg_id, reply_markup=markup)
        
        bot.answer_callback_query(call.id, "✅ شكراً لدعمك! يمكنك التحميل الآن.")
        
    except Exception as e:
        print(e)

# ==============================
# 📂 معالج زر الاستلام (مع التوجيه الذكي)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "get_file")
def handle_get_file(call):
    try:
        user_id = call.from_user.id
        msg_id = str(call.message.message_id)
        
        # حصانة الأدمن
        if user_id == ADMIN_ID:
            bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن", show_alert=False)
            bot.send_message(user_id, f"📂 ملفك:\n{FILE_LINK}")
            return

        # التحقق من الضغط على زر الدعم
        if msg_id in likes_data and user_id in likes_data[msg_id]:
            try:
                # محاولة الإرسال
                bot.send_message(user_id, f"🎉 **تفضل الكونفيج:**\n{FILE_LINK}", parse_mode="Markdown")
                bot.answer_callback_query(call.id, "✅ تم الإرسال لخاصك!", show_alert=False)
            
            except:
                # ❌ فشل الإرسال (البوت محظور أو لم يبدأ)
                # جلب يوزر البوت تلقائياً ليظهر في الرسالة
                bot_username = bot.get_me().username
                
                error_msg = (
                    "❌ عذراً، لا أستطيع مراسلتك!\n\n"
                    f"يجب عليك الدخول للبوت @{bot_username} \n"
                    "والضغط على (Start) أو (بدء) أولاً، ثم عد واضغط الزر."
                )
                bot.answer_callback_query(call.id, error_msg, show_alert=True)
        else:
            bot.answer_callback_query(call.id, "⛔ لم تضغط على زر الدعم!\nاضغط على (❤️) أولاً ثم حمل الملف.", show_alert=True)
            
    except Exception as e:
        print(e)

# ==============================
# 🌐 تشغيل السيرفر
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Pro Bot Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
