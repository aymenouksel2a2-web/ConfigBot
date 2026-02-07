import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAFFBPq_NY_yLx0xyEseOGe1d0FfmvQaPks"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة
FILE_LINK = "https://t.me/AymenOxel"
DATA_FILE = "likes_db.json"

bot = telebot.TeleBot(TOKEN)

# ==============================
# 💾 قاعدة البيانات (لحفظ اللايكات)
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

    # إنشاء الأزرار
    markup = types.InlineKeyboardMarkup()
    
    # زر اللايك (مع العداد 0 في البداية)
    btn_like = types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like")
    # زر التحميل
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
        
        # فتح سجل جديد لهذه الرسالة
        likes_data[str(sent_msg.message_id)] = []
        save_data()
        
        bot.reply_to(message, "✅ تم النشر بنظام الأزرار الجديد!")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {e}")

# ==============================
# ❤️ معالج زر اللايك (التفاعل)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "do_like")
def handle_like_click(call):
    try:
        user_id = call.from_user.id
        msg_id = str(call.message.message_id)
        
        if msg_id not in likes_data: likes_data[msg_id] = []
        
        # هل الشخص ضغط من قبل؟
        if user_id in likes_data[msg_id]:
            bot.answer_callback_query(call.id, "⚠️ لقد تفاعلت مسبقاً! يمكنك تحميل الملف الآن.", show_alert=True)
            return
        
        # تسجيل الشخص
        likes_data[msg_id].append(user_id)
        save_data()
        
        # تحديث العداد في الزر (حركة احترافية)
        count = len(likes_data[msg_id])
        
        # نعيد بناء الأزرار بالرقم الجديد
        markup = types.InlineKeyboardMarkup()
        btn_like = types.InlineKeyboardButton(f"❤️ اضغط للدعم ({count})", callback_data="do_like")
        btn_get = types.InlineKeyboardButton("📥 استلام الكونفيج", callback_data="get_file")
        markup.add(btn_like)
        markup.add(btn_get)
        
        # تعديل الرسالة لإظهار الرقم الجديد
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=msg_id, reply_markup=markup)
        
        bot.answer_callback_query(call.id, "✅ تم تسجيل تفاعلك! اضغط زر الاستلام الآن.")
        
    except Exception as e:
        print(e)

# ==============================
# 📂 معالج زر الاستلام
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

        # التحقق: هل اسمه موجود في قائمة اللايكات؟
        if msg_id in likes_data and user_id in likes_data[msg_id]:
            try:
                bot.send_message(user_id, f"🎉 **تفضل الكونفيج:**\n{FILE_LINK}", parse_mode="Markdown")
                bot.answer_callback_query(call.id, "✅ تم الإرسال لخاصك!", show_alert=False)
            except:
                bot.answer_callback_query(call.id, "❌ ابدأ البوت في الخاص أولاً!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "⛔ لم تضغط على زر القلب!\nاضغط على الزر (❤️) بجانب زر التحميل أولاً.", show_alert=True)
            
    except Exception as e:
        print(e)

# ==============================
# 🌐 تشغيل السيرفر
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Button Bot Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
