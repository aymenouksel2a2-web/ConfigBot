import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import json

# ==============================
# ⚙️ الإعدادات
# ==============================
TOKEN = "8579121219:AAEknN3xKk3ZhCUbPC_jaUCRvS6MUurpeJo"   # ⚠️ ضع التوكن
ADMIN_ID = 7846022798           # آيدي الأدمن
CHANNEL_ID = -1003858414969     # آيدي القناة
LIKES_FILE = "likes_users_db.json" # اسم جديد لقاعدة البيانات (لتغيير النظام لليوزرات)
CONFIGS_FILE = "configs_db.json"

bot = telebot.TeleBot(TOKEN)

# متغيرات التشغيل
admin_upload_mode = False
last_upload_msg_id = None # لتتبع رسالة العداد وحذف القديم

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
        bot.reply_to(message, "🤖 هذا البوت مخصص لخدمة القناة فقط.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    markup.add(types.KeyboardButton("📤 رفع ملفات"), types.KeyboardButton("✅ إنهاء وحفظ"))
    markup.add(types.KeyboardButton("📢 نشر بالقناة"), types.KeyboardButton("🗑️ حذف الملفات"))
    markup.add(types.KeyboardButton("👥 المتفاعلين (Users)"), types.KeyboardButton("📊 فحص المخزن"))
    markup.add(types.KeyboardButton("❌ إخفاء اللوحة"))

    status = "🟢 مفعل" if admin_upload_mode else "🔴 مغلق"
    files_count = len(stored_configs)
    
    msg = (
        "👑 **لوحة تحكم الأدمن V6**\n\n"
        f"📂 الملفات الجاهزة: `{files_count}`\n"
        f"📡 وضع الرفع: {status}\n\n"
        "👇 **التحكم:**"
    )
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=markup)

# ==============================
# 🕹️ معالج الأزرار السفلية
# ==============================
@bot.message_handler(func=lambda message: message.text in [
    "📤 رفع ملفات", "✅ إنهاء وحفظ", "📢 نشر بالقناة", 
    "🗑️ حذف الملفات", "👥 المتفاعلين (Users)", "📊 فحص المخزن", "❌ إخفاء اللوحة"
])
def handle_admin_buttons(message):
    if message.from_user.id != ADMIN_ID: return
    
    global admin_upload_mode, stored_configs, last_upload_msg_id
    action = message.text
    
    # 1. زر رفع الملفات
    if action == "📤 رفع ملفات":
        admin_upload_mode = True
        stored_configs = [] 
        save_json(CONFIGS_FILE, stored_configs)
        bot.reply_to(message, "📂 **تم تفعيل وضع الرفع!**\nأرسل الملفات الآن...")
        
    # 2. زر الإنهاء
    elif action == "✅ إنهاء وحفظ":
        admin_upload_mode = False
        last_upload_msg_id = None # تصفير متغير الرسالة
        bot.reply_to(message, f"✅ **تم الحفظ بنجاح!**\nالعدد النهائي: {len(stored_configs)}")

    # 3. زر الحذف
    elif action == "🗑️ حذف الملفات":
        stored_configs = []
        save_json(CONFIGS_FILE, stored_configs)
        bot.reply_to(message, "🗑️ تم تنظيف المخزن (0 ملفات).")

    # 4. زر الفحص
    elif action == "📊 فحص المخزن":
        bot.reply_to(message, f"📊 المخزن يحتوي على **{len(stored_configs)}** ملف.")

    # 5. زر المتفاعلين (عرض اليوزرات مباشرة)
    elif action == "👥 المتفاعلين (Users)":
        users_list = []
        
        # استخراج الأسماء من قاعدة البيانات
        for msg_id in likes_data:
            for user_info in likes_data[msg_id]:
                # user_info أصبح الآن قاموساً {id, name}
                if isinstance(user_info, dict):
                    name = user_info.get('name', 'Unknown')
                    users_list.append(name)
        
        # إزالة التكرار
        users_list = list(set(users_list))
        
        if not users_list:
            bot.reply_to(message, "⚠️ القائمة فارغة! لم يتفاعل أحد بعد.")
        else:
            # تنسيق القائمة كرسالة
            text_report = "👥 **قائمة المتفاعلين:**\n\n"
            for idx, user in enumerate(users_list, 1):
                text_report += f"{idx}. {user}\n"
            
            # إرسال الرسالة (مع مراعاة طول الرسالة في تيليجرام)
            if len(text_report) > 4000:
                # إذا كانت طويلة جداً نقطعها
                bot.reply_to(message, text_report[:4000] + "\n... (القائمة طويلة)")
            else:
                bot.reply_to(message, text_report)

    # 6. زر النشر
    elif action == "📢 نشر بالقناة":
        if not stored_configs:
            bot.reply_to(message, "⚠️ المخزن فارغ!")
            return
        
        bot_user = bot.get_me().username
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❤️ اضغط للدعم (0)", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (اضغط هنا)", url=f"https://t.me/{bot_user}?start=channel"))
        
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
            bot.reply_to(message, "✅ **تم النشر!**")
        except Exception as e:
            bot.reply_to(message, f"❌ خطأ: {e}")

    # 7. إخفاء
    elif action == "❌ إخفاء اللوحة":
        bot.send_message(message.chat.id, "تم الإخفاء. /admin للإظهار", reply_markup=types.ReplyKeyboardRemove())

# ==============================
# 📥 استقبال الملفات (التحسين: رسالة واحدة)
# ==============================
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if message.from_user.id != ADMIN_ID: return
    
    global stored_configs, last_upload_msg_id
    
    if admin_upload_mode:
        # 1. حفظ الملف
        stored_configs.append(message.document.file_id)
        save_json(CONFIGS_FILE, stored_configs)
        
        # 2. إدارة رسائل التنبيه (حذف القديم وإرسال الجديد)
        new_text = f"✅ **تم رفع عدد الكونفيجات:** {len(stored_configs)}"
        
        try:
            # حاول حذف الرسالة السابقة للبوت إذا وجدت
            if last_upload_msg_id:
                bot.delete_message(message.chat.id, last_upload_msg_id)
        except: pass # تجاهل الخطأ إذا كانت الرسالة محذوفة أصلاً
        
        # إرسال الرسالة الجديدة وحفظ الآيدي الخاص بها
        sent = bot.send_message(message.chat.id, new_text, parse_mode="Markdown")
        last_upload_msg_id = sent.message_id

# ==============================
# ❤️ معالجة تفاعل الأعضاء (حفظ اليوزرات)
# ==============================
@bot.callback_query_handler(func=lambda call: call.data == "do_like")
def user_like(call):
    try:
        uid = call.from_user.id
        mid = str(call.message.message_id)
        
        # جلب اليوزر نيم
        username = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        
        # هيكل الحفظ الجديد: {id: 123, name: "@user"}
        user_obj = {'id': uid, 'name': username}
        
        if mid not in likes_data: likes_data[mid] = []
        
        # التحقق من التكرار (نبحث عن الآيدي داخل القائمة)
        # القائمة تحتوي قواميس، لذا نحتاج طريقة ذكية للتحقق
        already_liked = False
        for user in likes_data[mid]:
            if user['id'] == uid:
                already_liked = True
                break
        
        if already_liked:
            bot.answer_callback_query(call.id, "⚠️ تفاعلت مسبقاً!", show_alert=True)
            return
            
        likes_data[mid].append(user_obj)
        save_json(LIKES_FILE, likes_data)
        
        # تحديث العداد
        count = len(likes_data[mid])
        bot_user = bot.get_me().username
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"❤️ اضغط للدعم ({count})", callback_data="do_like"))
        markup.add(types.InlineKeyboardButton("📥 استلام الكونفيجات", callback_data="get_file"))
        markup.add(types.InlineKeyboardButton("🤖 تفعيل البوت (اضغط هنا)", url=f"https://t.me/{bot_user}?start=channel"))
        
        bot.edit_message_reply_markup(call.message.chat.id, mid, reply_markup=markup)
        bot.answer_callback_query(call.id, "✅ شكراً للدعم!")
    except Exception as e:
        print(e)

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

    # التحقق: هل الآيدي موجود في القائمة؟
    user_found = False
    if mid in likes_data:
        for user in likes_data[mid]:
            if user['id'] == uid:
                user_found = True
                break

    if user_found:
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
def home(): return "<b>Pro V6 Bot Running...</b>"
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(skip_pending=True)

