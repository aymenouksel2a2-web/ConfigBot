import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json
import io

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAFSFBOSuhWgM-mSqJwEs8EyLQc6NAWjwBk"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة
LIKES_FILE = "likes_db.json"
CONFIGS_FILE = "configs_db.json"

bot = telebot.TeleBot(TOKEN)
admin_upload_mode = False

# ==============================
# 💾 الدوال المساعدة
# ==============================
def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f: return json.load(f)
        except: return {} if filename == LIKES_FILE else []
    return {} if filename == LIKES_FILE else []

def save_json(filename, data):
    try:
        with open(filename, "w") as f: json.dump(data, f)
    except: pass

likes_data = load_json(LIKES_FILE)
stored_configs = load_json(CONFIGS_FILE)

# ==============================
# 🎮 لوحة تحكم الأدمن (كيبورد سفلي)
# ==============================
@bot.message_handler(commands=['admin', 'start'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        # رد للأعضاء العاديين
        bot.reply_to(message, "🤖 هذا البوت مخصص لخدمة القناة فقط.")
        return

    # إنشاء الكيبورد السفلي (ReplyKeyboardMarkup)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # تعريف الأزرار
    btn1 = types.KeyboardButton("📤 رفع ملفات")
    btn2 = types.KeyboardButton("✅ إنهاء وحفظ")
    btn3 = types.KeyboardButton("📢 نشر بالقناة")
    btn4 = types.KeyboardButton("🗑️ حذف الملفات")
    btn5 = types.KeyboardButton("👥 ملف المتفاعلين")
    btn6 = types.KeyboardButton("📊 فحص المخزن")
    btn_close = types.KeyboardButton("❌ إخفاء اللوحة") # زر لإغلاق الكيبورد

    # إضافة الأزرار للكيبورد
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5, btn6)
    markup.add(btn_close)
    
    status = "🟢 مفعل" if admin_upload_mode else "🔴 مغلق"
    files_count = len(stored_configs)
    
    msg = (
        "👑 **أهلاً بك في لوحة القيادة V5**\n\n"
        f"📂 الملفات الجاهزة: `{files_count}`\n"
        f"📡 وضع الرفع: {status}\n\n"
        "👇 **التحكم أصبح بالأسفل الآن:**"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

# ==============================
# 🕹️ معالج الأزرار السفلية (Text Handler)
# ==============================
@bot.message_handler(func=lambda message: message.text in [
    "📤 رفع ملفات", "✅ إنهاء وحفظ", "📢 نشر بالقناة", 
    "🗑️ حذف الملفات", "👥 ملف المتفاعلين", "📊 فحص المخزن", "❌ إخفاء اللوحة"
])
def handle_admin_buttons(message):
    if message.from_user.id != ADMIN_ID: return
    
    global admin_upload_mode, stored_configs
    action = message.text # النص المكتوب على الزر
    
    # 1. زر رفع الملفات
    if action == "📤 رفع ملفات":
        admin_upload_mode = True
        stored_configs = [] 
        save_json(CONFIGS_FILE, stored_configs)
        bot.reply_to(message, "📂 **تم تفعيل وضع الرفع!**\nقم بإرسال الملفات الآن واحداً تلو الآخر..")
        
    # 2. زر الإنهاء
    elif action == "✅ إنهاء وحفظ":
        admin_upload_mode = False
        bot.reply_to(message, f"✅ **تم الحفظ بنجاح!**\nالعدد الكلي: {len(stored_configs)} ملف.")

    # 3. زر الحذف
    elif action == "🗑️ حذف الملفات":
        stored_configs = []
        save_json(CONFIGS_FILE, stored_configs)
        bot.reply_to(message, "🗑️ تم تنظيف المخزن وحذف جميع الملفات!")

    # 4. زر الفحص
    elif action == "📊 فحص المخزن":
        bot.reply_to(message, f"📊 لديك حالياً **{len(stored_configs)}** ملف جاهز للنشر.")

    # 5. زر الإخفاء
    elif action == "❌ إخفاء اللوحة":
        # إزالة الكيبورد
        hide_markup = types.ReplyKeyboardRemove()
        bot.send_message(message.chat.id, "تم إخفاء اللوحة. اكتب /admin لإظهارها.", reply_markup=hide_markup)

    # 6. زر المتفاعلين (تقرير txt)
    elif action == "👥 ملف المتفاعلين":
        all_users = set()
        for msg_id in likes_data:
            for uid in likes_data[msg_id]:
                all_users.add(uid)
        
        if not all_users:
            bot.reply_to(message, "⚠️ لا يوجد متفاعلين حتى الآن.")
            return

        report = f"📊 تقرير المتفاعلين (العدد: {len(all_users)})\n---------------------------\n"
        for uid in all_users:
            report += f"ID: {uid}\n"
        
        file_obj = io.BytesIO(report.encode())
        file_obj.name = "reactors_list.txt"
        bot.send_document(message.chat.id, file_obj, caption="👥 تفضل قائمة المتفاعلين.")

    # 7. زر النشر بالقناة
    elif action == "📢 نشر بالقناة":
        if not stored_configs:
            bot.reply_to(message, "⚠️ المخزن فارغ! استخدم '📤 رفع ملفات' أولاً.")
            return
        
        bot_user = bot.get_me().username
        
        # أزرار القناة (تبقى Inline لأنها للمستخدمين)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (اضغط هنا أولاً)", url=f"https://t.me/{bot_user}?start=channel"))
        
        msg_text = (
            "🔥 **كونفيج Dark Tunnel صاروخ!** 🚀\n\n"
            "⚡️ السرعة: عالية جداً\n"
            "🔓 المدة: مفتوحة\n\n"
            "⚠️ **طريقة التحميل:**\n1. اضغط زر التفعيل (🤖) وابدأ البوت.\n2. عد واضغط زر القلب (❤️) للدعم.\n3. اضغط استلام (📥) وسيصلك الملف."
        )
        try:
            sent = bot.send_message(CHANNEL_ID, msg_text, parse_mode="Markdown", reply_markup=markup)
            likes_data[str(sent.message_id)] = []
            save_json(LIKES_FILE, likes_data)
            bot.reply_to(message, "✅ **تم النشر في القناة بنجاح!**")
        except Exception as e:
            bot.reply_to(message, f"❌ خطأ في النشر: {e}")

# ==============================
# 📥 استقبال الملفات (أثناء الرفع)
# ==============================
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    if admin_upload_mode:
        stored_configs.append(message.document.file_id)
        save_json(CONFIGS_FILE, stored_configs)
        bot.reply_to(message, f"✅ تم استلام الملف رقم {len(stored_configs)}")

# ==============================
# ❤️ معالجة تفاعل الأعضاء (المنطق كما هو)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "do_like")
def user_like(call):
    try:
        uid = call.from_user.id
        mid = str(call.message.message_id)
        
        if mid not in likes_data: likes_data[mid] = []
        if uid in likes_data[mid]:
            bot.answer_callback_query(call.id, "⚠️ تفاعلت مسبقاً!", show_alert=True)
            return
            
        likes_data[mid].append(uid)
        save_json(LIKES_FILE, likes_data)
        
        count = len(likes_data[mid])
        bot_user = bot.get_me().username
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"❤️ اضغط للدعم ({count})", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (اضغط هنا أولاً)", url=f"https://t.me/{bot_user}?start=channel"))
        
        bot.edit_message_reply_markup(call.message.chat.id, mid, reply_markup=markup)
        bot.answer_callback_query(call.id, "✅ شكراً للدعم!")
    except: pass

# ==============================
# 📂 تسليم الملفات
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "get_file")
def deliver_files(call):
    uid = call.from_user.id
    mid = str(call.message.message_id)
    
    if uid == ADMIN_ID:
        send_files(uid)
        bot.answer_callback_query(call.id, "👑 أهلاً بالأدمن", show_alert=False)
        return

    if mid in likes_data and uid in likes_data[mid]:
        try:
            send_files(uid)
            bot.answer_callback_query(call.id, "✅ تم الإرسال!", show_alert=False)
        except:
            me = bot.get_me().username
            bot.answer_callback_query(call.id, f"❌ يجب تفعيل البوت أولاً!\nاضغط الزر السفلي 🤖", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "⛔ اضغط زر القلب ❤️ أولاً!", show_alert=True)

def send_files(uid):
    if not stored_configs:
        bot.send_message(uid, "⚠️ لا توجد ملفات حالياً.")
        return
    bot.send_message(uid, "🎉 **ملفاتك جاهزة:**", parse_mode="Markdown")
    for fid in stored_configs:
        bot.send_document(uid, fid)

# ==============================
# 🌐 التشغيل
# ==============================
app = Flask('')
@app.route('/')
def home(): return "<b>Keyboard Bot V5 Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
