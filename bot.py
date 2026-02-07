import telebot
from telebot import types
from flask import Flask
from threading import Thread
import os
import time
import traceback

from database import (
    init_db, add_user, get_all_users, get_users_count,
    mark_user_blocked, add_like, has_liked, get_likes_count,
    get_all_likers, clear_likes, add_config, get_all_configs,
    get_configs_count, clear_configs, save_message_history,
    get_message_history, clear_message_history, add_post,
    full_reset, get_stats
)

# ══════════════════════════════════════════
# ⚙️ CONFIGURATION (من Environment Variables)
# ══════════════════════════════════════════
TOKEN      = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "7846022798"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003858414969"))

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ─── Runtime State ───
admin_upload_mode = False
last_upload_msg_id = None
broadcast_mode = False
cooldown_tracker = {}
COOLDOWN_SECONDS = 3


# ══════════════════════════════════════════
# 🛡️ HELPERS
# ══════════════════════════════════════════

def is_admin(uid):
    return uid == ADMIN_ID


def check_cooldown(uid):
    """حماية من السبام"""
    now = time.time()
    if now - cooldown_tracker.get(uid, 0) < COOLDOWN_SECONDS:
        return False
    cooldown_tracker[uid] = now
    return True


def display_name(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Unknown"


def channel_markup(msg_id=None):
    """أزرار بوست القناة"""
    bot_user = bot.get_me().username
    count = get_likes_count(msg_id) if msg_id else 0

    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(types.InlineKeyboardButton(
        f"❤️ اضغط للدعم ({count})", callback_data="do_like"
    ))
    mk.add(types.InlineKeyboardButton(
        "📥 استلام الكونفيجات", callback_data="get_file"
    ))
    mk.add(types.InlineKeyboardButton(
        "🤖 فعّل البوت أولاً", url=f"https://t.me/{bot_user}?start=channel"
    ))
    return mk


def admin_markup():
    """لوحة تحكم الأدمن"""
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add(
        types.KeyboardButton("📤 رفع ملفات"),
        types.KeyboardButton("✅ إنهاء وحفظ")
    )
    mk.add(
        types.KeyboardButton("📢 نشر بالقناة"),
        types.KeyboardButton("🗑️ حذف الملفات")
    )
    mk.add(
        types.KeyboardButton("👥 المتفاعلين"),
        types.KeyboardButton("📊 الإحصائيات")
    )
    mk.add(
        types.KeyboardButton("📣 إذاعة جماعية"),
        types.KeyboardButton("🔄 تصفير شامل")
    )
    mk.add(types.KeyboardButton("❌ إخفاء اللوحة"))
    return mk


# ══════════════════════════════════════════
# 🚀 START
# ══════════════════════════════════════════

@bot.message_handler(commands=["start"])
def cmd_start(message):
    u = message.from_user
    add_user(u.id, u.username, u.first_name)

    if is_admin(u.id):
        show_panel(message)
        return

    bot.send_message(message.chat.id,
        f"مرحباً {u.first_name}! 👋\n\n"
        "🔹 هذا البوت يوزع كونفيجات VPN\n"
        "🔹 تابع القناة واضغط ❤️\n"
        "🔹 ثم اضغط 📥 لاستلام الملفات\n\n"
        "✅ تم تفعيل البوت!"
    )


@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if is_admin(message.from_user.id):
        show_panel(message)


def show_panel(message):
    s = get_stats()
    up = "🟢" if admin_upload_mode else "🔴"
    bc = "🟢" if broadcast_mode else "🔴"

    bot.send_message(message.chat.id,
        "👑 *Admin Panel V12*\n"
        "━━━━━━━━━━━━━━━\n"
        f"📂 Files: `{s['configs']}`\n"
        f"👥 Users: `{s['active_users']}` / `{s['total_users']}`\n"
        f"❤️ Likers: `{s['unique_likers']}`\n"
        f"📡 Upload: {up}  |  📣 Broadcast: {bc}\n"
        "━━━━━━━━━━━━━━━\n"
        "🗄️ MongoDB Atlas | Smart Delete",
        reply_markup=admin_markup()
    )


# ══════════════════════════════════════════
# 🎛️ ADMIN BUTTONS
# ══════════════════════════════════════════

BUTTONS = [
    "📤 رفع ملفات", "✅ إنهاء وحفظ", "📢 نشر بالقناة",
    "🗑️ حذف الملفات", "👥 المتفاعلين", "📊 الإحصائيات",
    "📣 إذاعة جماعية", "🔄 تصفير شامل", "❌ إخفاء اللوحة",
    "✅ تأكيد التصفير", "❌ إلغاء التصفير"
]


@bot.message_handler(func=lambda m: m.text in BUTTONS)
def handle_buttons(message):
    if not is_admin(message.from_user.id):
        return

    global admin_upload_mode, last_upload_msg_id, broadcast_mode
    act = message.text

    # ── 📤 رفع ملفات ──
    if act == "📤 رفع ملفات":
        admin_upload_mode = True
        clear_configs()
        s = bot.reply_to(message, "📂 *Upload Mode: ON*\n🔢 Counter: 0")
        last_upload_msg_id = s.message_id

    # ── ✅ إنهاء وحفظ ──
    elif act == "✅ إنهاء وحفظ":
        admin_upload_mode = False
        broadcast_mode = False
        last_upload_msg_id = None
        bot.reply_to(message,
            f"✅ *Saved!*\n📂 Total: `{get_configs_count()}`"
        )

    # ── 🗑️ حذف الملفات ──
    elif act == "🗑️ حذف الملفات":
        clear_configs()
        bot.reply_to(message, "🗑️ All configs deleted.")

    # ── 📊 الإحصائيات ──
    elif act == "📊 الإحصائيات":
        s = get_stats()
        bot.reply_to(message,
            "📊 *Statistics*\n"
            "━━━━━━━━━━━━━━━\n"
            f"👥 Total Users: `{s['total_users']}`\n"
            f"✅ Active: `{s['active_users']}`\n"
            f"🚫 Blocked: `{s['blocked_users']}`\n"
            f"📂 Configs: `{s['configs']}`\n"
            f"❤️ Likers: `{s['unique_likers']}`"
        )

    # ── 👥 المتفاعلين ──
    elif act == "👥 المتفاعلين":
        likers = get_all_likers()
        if not likers:
            bot.reply_to(message, "⚠️ No interactions yet.")
        else:
            names = list(set(u["name"] for u in likers))
            txt = f"👥 *Likers ({len(names)}):*\n"
            txt += "\n".join(f"  • {n}" for n in names[:50])
            if len(names) > 50:
                txt += f"\n... +{len(names)-50} more"
            bot.reply_to(message, txt[:4000])

    # ── 📢 نشر بالقناة ──
    elif act == "📢 نشر بالقناة":
        configs = get_all_configs()
        if not configs:
            bot.reply_to(message, "⚠️ No files! Upload first.")
            return

        text = (
            "🔥 *كونفيجات جديدة!* 🚀\n\n"
            f"📂 عدد الملفات: `{len(configs)}`\n"
            "⚡️ سرعة عالية | 🔓 غير محدود\n\n"
            "⚠️ *الخطوات:*\n"
            "1️⃣ فعّل البوت 🤖\n"
            "2️⃣ اضغط لايك ❤️\n"
            "3️⃣ استلم الملفات 📥"
        )

        try:
            mk = channel_markup(None)
            sent = bot.send_message(CHANNEL_ID, text,
                parse_mode="Markdown", reply_markup=mk)
            add_post(sent.message_id)

            # تحديث العداد
            bot.edit_message_reply_markup(
                CHANNEL_ID, sent.message_id,
                reply_markup=channel_markup(sent.message_id)
            )
            bot.reply_to(message, "✅ *Posted!*")
        except Exception as e:
            bot.reply_to(message, f"❌ Error:\n`{e}`")

    # ── 📣 إذاعة جماعية ──
    elif act == "📣 إذاعة جماعية":
        broadcast_mode = True
        bot.reply_to(message,
            "📣 *Broadcast Mode: ON*\n\n"
            "أرسل الرسالة الآن (نص/صورة/ملف/فيديو)\n\n"
            "اضغط *✅ إنهاء وحفظ* للإلغاء"
        )

    # ── 🔄 تصفير شامل ──
    elif act == "🔄 تصفير شامل":
        mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
        mk.add(
            types.KeyboardButton("✅ تأكيد التصفير"),
            types.KeyboardButton("❌ إلغاء التصفير")
        )
        bot.send_message(message.chat.id,
            "⚠️ *متأكد؟*\nسيتم حذف: لايكات + ملفات + سجل رسائل\n"
            "(المستخدمين لن يُحذفوا)",
            reply_markup=mk
        )

    elif act == "✅ تأكيد التصفير":
        full_reset()
        bot.send_message(message.chat.id,
            "🔄 *Reset Done!*",
            reply_markup=admin_markup()
        )

    elif act == "❌ إلغاء التصفير":
        bot.send_message(message.chat.id,
            "❌ Cancelled.",
            reply_markup=admin_markup()
        )

    # ── ❌ إخفاء ──
    elif act == "❌ إخفاء اللوحة":
        bot.send_message(message.chat.id,
            "🔒 Hidden. /admin to reopen.",
            reply_markup=types.ReplyKeyboardRemove()
        )


# ══════════════════════════════════════════
# 📣 BROADCAST
# ══════════════════════════════════════════

@bot.message_handler(
    func=lambda m: broadcast_mode and is_admin(m.from_user.id),
    content_types=["text","photo","document","video","audio","sticker"]
)
def do_broadcast(message):
    global broadcast_mode

    if message.text and message.text in BUTTONS:
        return

    broadcast_mode = False
    users = get_all_users()

    if not users:
        bot.reply_to(message, "⚠️ No users!")
        return

    st = bot.reply_to(message,
        f"📣 *Broadcasting to {len(users)} users...*"
    )

    ok = fail = block = 0

    for uid in users:
        try:
            bot.forward_message(uid, message.chat.id, message.message_id)
            ok += 1
            time.sleep(0.05)
        except telebot.apihelper.ApiTelegramException as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err:
                mark_user_blocked(uid)
                block += 1
            else:
                fail += 1
        except:
            fail += 1

    try:
        bot.edit_message_text(
            f"📣 *Broadcast Done!*\n"
            f"✅ Sent: `{ok}`\n"
            f"🚫 Blocked: `{block}`\n"
            f"❌ Failed: `{fail}`",
            message.chat.id, st.message_id,
            parse_mode="Markdown"
        )
    except:
        bot.send_message(message.chat.id,
            f"✅ {ok} | 🚫 {block} | ❌ {fail}")


# ══════════════════════════════════════════
# 📂 UPLOAD
# ══════════════════════════════════════════

@bot.message_handler(content_types=["document"])
def handle_doc(message):
    if not is_admin(message.from_user.id):
        return
    global last_upload_msg_id

    if not admin_upload_mode:
        bot.reply_to(message, "⚠️ Upload OFF. Press 📤 first.")
        return

    add_config(message.document.file_id)
    cnt = get_configs_count()
    text = f"📂 *Uploading...*\n🔢 Counter: `{cnt}` ✅"

    try:
        if last_upload_msg_id:
            bot.edit_message_text(text, message.chat.id,
                last_upload_msg_id, parse_mode="Markdown")
        else:
            s = bot.send_message(message.chat.id, text)
            last_upload_msg_id = s.message_id
    except:
        s = bot.send_message(message.chat.id, text)
        last_upload_msg_id = s.message_id


# ══════════════════════════════════════════
# ❤️ LIKE
# ══════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data == "do_like")
def handle_like(call):
    try:
        uid = call.from_user.id
        mid = call.message.message_id
        name = display_name(call.from_user)

        if not check_cooldown(uid):
            bot.answer_callback_query(call.id, "⏳ انتظر...")
            return

        is_new = add_like(uid, mid, name)

        if not is_new:
            bot.answer_callback_query(call.id,
                "⚠️ سبق أن دعمت! ❤️", show_alert=True)
            return

        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, mid,
                reply_markup=channel_markup(mid)
            )
        except:
            pass

        bot.answer_callback_query(call.id, "✅ شكراً لدعمك! ❤️")

    except Exception as e:
        print(f"Like Error: {e}")
        bot.answer_callback_query(call.id, "❌ خطأ")


# ══════════════════════════════════════════
# 📥 DELIVERY + SMART CLEAN
# ══════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data == "get_file")
def handle_delivery(call):
    uid = call.from_user.id
    mid = call.message.message_id

    if not check_cooldown(uid):
        bot.answer_callback_query(call.id, "⏳ انتظر...")
        return

    # أدمن
    if is_admin(uid):
        try:
            smart_send(uid)
            bot.answer_callback_query(call.id, "👑 Admin")
        except Exception as e:
            bot.answer_callback_query(call.id,
                f"❌ {str(e)[:80]}", show_alert=True)
        return

    # تحقق لايك
    if not has_liked(uid, mid):
        bot.answer_callback_query(call.id,
            "⛔ اضغط ❤️ للدعم أولاً!", show_alert=True)
        return

    # إرسال
    try:
        smart_send(uid)
        bot.answer_callback_query(call.id, "✅ تم الإرسال!")
    except telebot.apihelper.ApiTelegramException as e:
        err = str(e).lower()
        if "blocked" in err or "chat not found" in err:
            bot.answer_callback_query(call.id,
                "❌ فعّل البوت أولاً! اضغط 🤖", show_alert=True)
        else:
            bot.answer_callback_query(call.id,
                "❌ خطأ، حاول مرة أخرى", show_alert=True)


def smart_send(user_id):
    """حذف القديم → إرسال الجديد → حفظ السجل"""

    # 1️⃣ حذف القديم
    old = get_message_history(user_id)
    for mid in old:
        try:
            bot.delete_message(user_id, mid)
        except:
            pass
    clear_message_history(user_id)

    # 2️⃣ جلب الملفات
    configs = get_all_configs()
    if not configs:
        m = bot.send_message(user_id, "⚠️ لا توجد ملفات حالياً.")
        save_message_history(user_id, [m.message_id])
        return

    # 3️⃣ إرسال
    ids = []

    h = bot.send_message(user_id,
        f"✨ *كونفيجاتك ({len(configs)} ملفات):*")
    ids.append(h.message_id)

    for fid in configs:
        try:
            d = bot.send_document(user_id, fid)
            ids.append(d.message_id)
        except Exception as e:
            print(f"Send error {user_id}: {e}")

    f = bot.send_message(user_id,
        "━━━━━━━━━━━━━━━\n"
        "✅ تم!\n"
        "🔄 ستُحذف تلقائياً عند توفر ملفات جديدة")
    ids.append(f.message_id)

    # 4️⃣ حفظ السجل
    save_message_history(user_id, ids)


# ══════════════════════════════════════════
# 🌐 FLASK
# ══════════════════════════════════════════

app = Flask(__name__)


@app.route("/")
def home():
    try:
        s = get_stats()
        return (
            f"<h2>🤖 Bot V12 Running</h2>"
            f"<p>👥 {s['total_users']} users | "
            f"📂 {s['configs']} configs | "
            f"❤️ {s['unique_likers']} likers</p>"
        )
    except:
        return "Bot Running"


@app.route("/health")
def health():
    return "OK", 200


def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    Thread(
        target=lambda: app.run(host="0.0.0.0", port=port),
        daemon=True
    ).start()


# ══════════════════════════════════════════
# 🚀 MAIN
# ══════════════════════════════════════════

if __name__ == "__main__":
    print("🔧 Connecting to MongoDB...")
    init_db()

    print("🌐 Starting web server...")
    keep_alive()

    print("🤖 Bot V12 starting...")
    print(f"👑 Admin: {ADMIN_ID}")
    print(f"📢 Channel: {CHANNEL_ID}")

    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=20,
                long_polling_timeout=40,
                allowed_updates=["message", "callback_query"]
            )
        except Exception as e:
            print(f"❌ Error: {e}")
            traceback.print_exc()
            time.sleep(5)
            print("🔄 Restarting...")
