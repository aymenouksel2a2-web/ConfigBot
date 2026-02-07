import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json
import io # مكتبة لصنع الملفات النصية

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAGRF0uCeBP8-Xa6RYniY5WGUc7W3Bw1CEc"   # ⚠️ ضع التوكن
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
# 🎮 لوحة تحكم الأدمن (المطورة)
# ==============================
@bot.message_handler(commands=['admin', 'start'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "🤖 أهلاً بك! هذا البوت مخصص لخدمة القناة.")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    # الصف الأول
    btn1 = types.InlineKeyboardButton("📤 رفع ملفات", callback_data="admin_upload")
    btn2 = types.InlineKeyboardButton("✅ إنهاء وحفظ", callback_data="admin_done")
    # الصف الثاني
    btn3 = types.InlineKeyboardButton("📢 نشر بالقناة", callback_data="admin_post")
    btn4 = types.InlineKeyboardButton("🗑️ حذف الملفات", callback_data="admin_clear")
    # الصف الثالث
    btn5 = types.InlineKeyboardButton("👥 ملف المتفاعلين", callback_data="admin_reactors")
    btn6 = types.InlineKeyboardButton("📊 فحص المخزن", callback_data="admin_check")
    
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    markup.add(btn5, btn6)
    
    status = "🟢 مفعل" if admin_upload_mode else "🔴 مغلق"
    files_count = len(stored_configs)
    
    msg = (
        "👑 **لوحة تحكم الأدمن V4**\n\n"
        f"📂 الملفات الجاهزة: `{files_count}`\n"
        f"📡 وضع الرفع: {status}\n\n"
        "تحكم بالبوت من الأزرار أدناه:"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

# ==============================
# 🕹️ معالج أزرار الأدمن
# ==============================
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_actions(call):
    if call.from_user.id != ADMIN_ID: return
    
    global admin_upload_mode, stored_configs
    action = call.data
    
    if action == "admin_upload":
        admin_upload_mode = True
        stored_configs = [] 
        save_json(CONFIGS_FILE, stored_configs)
        bot.edit_message_text("📂 **وضع الرفع مفعل!**\nأرسل الملفات الآن..", call.message.chat.id, call.message.message_id)
        
    elif action == "admin_done":
        admin_upload_mode = False
        bot.edit_message_text(f"✅ **تم الحفظ!** العدد: {len(stored_configs)}\nعد للقائمة /admin للنشر.", call.message.chat.id, call.message.message_id)

    elif action == "admin_clear":
        stored_configs = []
        save_json(CONFIGS_FILE, stored_configs)
        bot.answer_callback_query(call.id, "🗑️ تم حذف جميع الملفات المحفوظة!", show_alert=True)
        admin_panel(call.message) # تحديث اللوحة

    elif action == "admin_check":
        bot.answer_callback_query(call.id, f"📂 الملفات الحالية: {len(stored_configs)}", show_alert=True)

    elif action == "admin_reactors":
        # تجميع المتفاعلين في ملف نصي
        all_users = set()
        for msg_id in likes_data:
            for uid in likes_data[msg_id]:
                all_users.add(uid)
        
        if not all_users:
            bot.answer_callback_query(call.id, "⚠️ لا يوجد متفاعلين حتى الآن.", show_alert=True)
            return

        report = f"📊 تقرير المتفاعلين (العدد: {len(all_users)})\n---------------------------\n"
        for uid in all_users:
            report += f"ID: {uid}\n"
        
        # تحويل النص لملف وهمي للإرسال
        file_obj = io.BytesIO(report.encode())
        file_obj.name = "reactors_list.txt"
        
        bot.send_document(call.message.chat.id, file_obj, caption="👥 قائمة بجميع الآيديات التي تفاعلت.")
        bot.answer_callback_query(call.id, "✅ تم إرسال الملف")

    elif action == "admin_post":
        if not stored_configs:
            bot.answer_callback_query(call.id, "⚠️ المخزن فارغ! ارفع ملفات أولاً.", show_alert=True)
            return
        
        # جلب يوزر البوت لرابط التفعيل
        bot_user = bot.get_me().username
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        # الزر الجديد للتفعيل 👇
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
            bot.answer_callback_query(call.id, "✅ تم النشر!")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ خطأ: {e}")

# ==============================
# 📥 استقبال الملفات
# ==============================
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    if admin_upload_mode:
        stored_configs.append(message.document.file_id)
        save_json(CONFIGS_FILE, stored_configs)
        bot.reply_to(message, f"✅ تم الحفظ ({len(stored_configs)})")

# ==============================
# ❤️ معالجة تفاعل الأعضاء
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
        
        # 🚫 تم حذف رسالة الإشعار للأدمن هنا (لمنع الإزعاج)

        # تحديث العداد
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
def home(): return "<b>Ultimate Bot V4 Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)
