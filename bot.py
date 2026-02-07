import telebot
from telebot import types
from telebot.types import InputMediaDocument
from flask import Flask
from threading import Thread
import os
import time
import traceback

from database import (
    init_db, add_user, get_all_users, get_users_count,
    get_active_count, mark_user_blocked, add_like, has_liked,
    get_likes_count, get_all_likers, clear_likes, add_config,
    get_all_configs, get_configs_count, clear_configs,
    save_message_history, get_message_history,
    clear_message_history, add_post, get_last_post,
    full_reset, get_stats, get_setting, set_setting,
    ban_user, unban_user, is_banned, search_user,
    export_users_list, record_download, get_total_downloads,
    get_referral_count, get_referral_leaderboard,
    get_post_downloads
)


# ══════════════════════════════════════════
# ⚙️ CONFIGURATION
# ══════════════════════════════════════════

TOKEN      = os.environ.get("BOT_TOKEN", "YOUR_TOKEN")
ADMIN_ID   = int(os.environ.get("ADMIN_ID", "7846022798"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003858414969"))

EXTRA_ADMINS = os.environ.get("EXTRA_ADMINS", "")
ADMIN_IDS = {ADMIN_ID}
if EXTRA_ADMINS:
    for a in EXTRA_ADMINS.split(","):
        try:
            ADMIN_IDS.add(int(a.strip()))
        except:
            pass

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
BOT_USERNAME = None

admin_states = {}
admin_panel_msg = {}
cooldowns = {}
COOLDOWN_SEC = 3
last_cleanup = time.time()


# ══════════════════════════════════════════
# 🛡️ HELPERS
# ══════════════════════════════════════════

def is_admin(uid):
    return uid in ADMIN_IDS

def get_state(uid):
    return admin_states.get(uid)

def set_state(uid, state):
    admin_states[uid] = state

def clear_state(uid):
    admin_states.pop(uid, None)

def check_cooldown(uid):
    now = time.time()
    if now - cooldowns.get(uid, 0) < COOLDOWN_SEC:
        return False
    cooldowns[uid] = now
    return True

def cleanup_memory():
    global last_cleanup
    now = time.time()
    if now - last_cleanup < 3600:
        return
    last_cleanup = now
    cutoff = now - 7200
    expired = [k for k, v in cooldowns.items() if v < cutoff]
    for k in expired:
        del cooldowns[k]

def dname(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name or "Unknown"

def delete_msg(chat_id, msg_id):
    try:
        bot.delete_message(chat_id, msg_id)
    except:
        pass

def notify_admins(text):
    for aid in ADMIN_IDS:
        try:
            bot.send_message(aid, text, parse_mode="Markdown")
        except:
            pass

def check_subscription(user_id):
    if not get_setting("require_subscription", True):
        return True
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

def check_maintenance(call_or_msg, is_callback=False):
    if get_setting("maintenance_mode", False):
        text = "🔧 البوت في وضع الصيانة\nيرجى المحاولة لاحقاً..."
        if is_callback:
            bot.answer_callback_query(call_or_msg.id, text, show_alert=True)
        else:
            bot.send_message(call_or_msg.chat.id, text)
        return True
    return False

def safe_edit_markup(chat_id, message_id, markup):
    try:
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        return True
    except:
        return False


# ══════════════════════════════════════════
# 📨 نظام الرسالة الواحدة
# ══════════════════════════════════════════

def admin_respond(chat_id, uid, text, inline_markup=None):
    msg_id = admin_panel_msg.get(uid)
    if msg_id:
        try:
            bot.edit_message_text(
                text, chat_id, msg_id,
                parse_mode="Markdown",
                reply_markup=inline_markup)
            return
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                return
        except:
            pass

    m = bot.send_message(chat_id, text,
        parse_mode="Markdown", reply_markup=inline_markup)
    admin_panel_msg[uid] = m.message_id


# ══════════════════════════════════════════
# 🎨 MARKUPS
# ══════════════════════════════════════════

def channel_markup(msg_id=None):
    likes = get_likes_count(msg_id) if msg_id else 0
    dl = get_post_downloads(msg_id) if msg_id else 0
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.row(
        types.InlineKeyboardButton(f"❤️ دعم ({likes})", callback_data="do_like"),
        types.InlineKeyboardButton(f"📥 استلم ({dl})", callback_data="get_file"))
    mk.add(types.InlineKeyboardButton(
        "🤖 فعّل البوت أولاً",
        url=f"https://t.me/{BOT_USERNAME}?start=channel"))
    return mk

def main_admin_markup():
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add("📤 رفع ملفات",   "📤 إضافة ملفات")
    mk.add("✅ إنهاء",       "📢 نشر بالقناة")
    mk.add("🗑️ حذف الملفات", "📊 الإحصائيات")
    mk.add("👥 المتفاعلين",  "📣 إذاعة جماعية")
    mk.add("✏️ تخصيص البوست", "🔄 تصفير شامل")
    mk.add("🔍 بحث مستخدم",  "🚫 بان مستخدم")
    mk.add("📋 تصدير المستخدمين", "🏆 المُحيلين")
    mk.add("⚙️ الإعدادات",   "❌ إخفاء")
    return mk

def back_markup():
    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("🔙 رجوع للوحة", callback_data="back_panel"))
    return mk

def settings_markup():
    maint = get_setting("maintenance_mode", False)
    sub   = get_setting("require_subscription", True)
    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(types.InlineKeyboardButton(
        f"🔧 الصيانة: {'🟢 مفعل' if maint else '🔴 مغلق'}",
        callback_data="toggle_maintenance"))
    mk.add(types.InlineKeyboardButton(
        f"📢 فحص الاشتراك: {'🟢 مفعل' if sub else '🔴 مغلق'}",
        callback_data="toggle_subscription"))
    mk.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_panel"))
    return mk

def reset_markup():
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.row(
        types.InlineKeyboardButton("✅ تأكيد", callback_data="confirm_reset"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="back_panel"))
    return mk

def panel_text(uid=None):
    s = get_stats()
    state = get_state(uid) if uid else None
    state_txt = f"\n📝 الحالة: `{state}`" if state else ""
    return (
        "👑 *لوحة التحكم*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📂 الملفات: `{s['configs']}`\n"
        f"👥 المستخدمين: `{s['active_users']}` / `{s['total_users']}`\n"
        f"❤️ متفاعلين: `{s['unique_likers']}`\n"
        f"📥 تحميلات: `{s['total_downloads']}`\n"
        f"🔗 إحالات: `{s['total_referrals']}`\n"
        f"🆕 اليوم: `{s['new_today']}`"
        f"{state_txt}\n"
        "━━━━━━━━━━━━━━━━━━━")


# ══════════════════════════════════════════
# 🚀 START
# ══════════════════════════════════════════

@bot.message_handler(commands=["start"])
def cmd_start(message):
    u = message.from_user
    uid = u.id

    if is_banned(uid) and not is_admin(uid):
        bot.send_message(uid, "🚫 تم حظرك.")
        return

    referrer = None
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer = int(args[1].replace("ref_", ""))
            if referrer == uid: referrer = None
        except: pass

    is_new = add_user(uid, u.username, u.first_name, referrer)

    if is_admin(uid):
        delete_msg(message.chat.id, message.message_id)
        show_panel(message.chat.id, uid)
        return

    bot.send_message(uid, "✅ تم تفعيل البوت، ارجع للقناة واستلم ملفاتك.")

    if is_new:
        ref_text = ""
        if referrer:
            ref_text = f"\n🔗 أحاله: `{referrer}`"
            try:
                bot.send_message(referrer,
                    f"🎉 شخص جديد عبر إحالتك!\n📊 إحالاتك: `{get_referral_count(referrer)}`")
            except: pass
        notify_admins(
            f"👤 *مستخدم جديد!*\n• {dname(u)}\n• ID: `{uid}`{ref_text}\n📊 الإجمالي: `{get_users_count()}`")


@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if is_admin(message.from_user.id):
        delete_msg(message.chat.id, message.message_id)
        show_panel(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["myref"])
def cmd_myref(message):
    uid = message.from_user.id
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    bot.send_message(uid, f"🔗 `{link}`\n👥 إحالاتك: `{get_referral_count(uid)}`")


def show_panel(chat_id, uid):
    old = admin_panel_msg.get(uid)
    if old: delete_msg(chat_id, old)
    m = bot.send_message(chat_id, panel_text(uid),
        parse_mode="Markdown", reply_markup=main_admin_markup())
    admin_panel_msg[uid] = m.message_id


# ══════════════════════════════════════════
# 🎛️ ADMIN BUTTONS
# ══════════════════════════════════════════

BTN_LIST = [
    "📤 رفع ملفات", "📤 إضافة ملفات", "✅ إنهاء",
    "📢 نشر بالقناة", "🗑️ حذف الملفات", "📊 الإحصائيات",
    "👥 المتفاعلين", "📣 إذاعة جماعية", "✏️ تخصيص البوست",
    "🔄 تصفير شامل", "🔍 بحث مستخدم", "🚫 بان مستخدم",
    "📋 تصدير المستخدمين", "🏆 المُحيلين", "⚙️ الإعدادات",
    "❌ إخفاء"
]

@bot.message_handler(func=lambda m: m.text in BTN_LIST)
def handle_btns(message):
    if not is_admin(message.from_user.id): return
    uid = message.from_user.id
    chat_id = message.chat.id
    act = message.text
    delete_msg(chat_id, message.message_id)

    if act == "📤 رفع ملفات":
        set_state(uid, "uploading")
        clear_configs()
        admin_respond(chat_id, uid,
            "📂 *وضع الرفع (جديد)*\n🗑️ تم مسح القديم\n🔢 العداد: `0`\n\n📎 أرسل الملفات...",
            back_markup())

    elif act == "📤 إضافة ملفات":
        set_state(uid, "uploading")
        admin_respond(chat_id, uid,
            f"📂 *وضع الرفع (إضافة)*\n📁 الحالي: `{get_configs_count()}`\n\n📎 أرسل الملفات...",
            back_markup())

    elif act == "✅ إنهاء":
        old_state = get_state(uid)
        clear_state(uid)
        admin_respond(chat_id, uid,
            f"✅ *تم!* ملفات: `{get_configs_count()}` | أُغلق: `{old_state or '-'}`\n\n{panel_text(uid)}",
            back_markup())

    elif act == "🗑️ حذف الملفات":
        clear_configs()
        admin_respond(chat_id, uid,
            f"🗑️ *تم حذف الملفات!*\n\n{panel_text(uid)}", back_markup())

    elif act == "📊 الإحصائيات":
        s = get_stats()
        admin_respond(chat_id, uid,
            "📊 *الإحصائيات*\n━━━━━━━━━━━━━━━\n"
            f"👥 الإجمالي: `{s['total_users']}` | النشطين: `{s['active_users']}`\n"
            f"⛔ بلوك: `{s['blocked_users']}` | 🚫 محظور: `{s['banned_users']}`\n"
            f"📂 ملفات: `{s['configs']}`\n"
            f"❤️ متفاعلين: `{s['unique_likers']}`\n"
            f"📥 تحميلات: `{s['total_downloads']}` (اليوم: `{s['dl_today']}`)\n"
            f"🔗 إحالات: `{s['total_referrals']}`\n"
            f"🆕 جدد اليوم: `{s['new_today']}`",
            back_markup())

    elif act == "👥 المتفاعلين":
        likers = get_all_likers()
        if not likers:
            admin_respond(chat_id, uid, "⚠️ لا يوجد متفاعلين.", back_markup())
        else:
            names = list({u["name"] for u in likers})
            txt = f"👥 *المتفاعلين ({len(names)}):*\n"
            txt += "\n".join(f"  • {n}" for n in names[:40])
            if len(names) > 40: txt += f"\n... +{len(names)-40}"
            admin_respond(chat_id, uid, txt[:4000], back_markup())

    elif act == "📢 نشر بالقناة":
        configs = get_all_configs()
        if not configs:
            admin_respond(chat_id, uid, "⚠️ لا توجد ملفات!", back_markup())
            return
        custom = get_setting("custom_post_text", "")
        text = custom if custom else (
            "🔥 *كونفيجات جديدة!* 🚀\n\n"
            f"📂 الملفات: `{len(configs)}`\n"
            "⚡️ سرعة عالية | 🔓 غير محدود\n\n"
            "⚠️ *الخطوات:*\n1️⃣ فعّل البوت 🤖\n2️⃣ اضغط ❤️\n3️⃣ استلم 📥")
        try:
            sent = bot.send_message(CHANNEL_ID, text,
                parse_mode="Markdown", reply_markup=channel_markup(None))
            add_post(sent.message_id, text)
            admin_respond(chat_id, uid,
                f"✅ *تم النشر!* ID: `{sent.message_id}`\n\n{panel_text(uid)}", back_markup())
        except Exception as e:
            admin_respond(chat_id, uid, f"❌ خطأ:\n`{e}`", back_markup())

    elif act == "✏️ تخصيص البوست":
        set_state(uid, "custom_post")
        current = get_setting("custom_post_text", "")
        preview = current[:200] if current else "(افتراضي)"
        admin_respond(chat_id, uid,
            f"✏️ *تخصيص البوست*\n📝 الحالي:\n{preview}\n\nأرسل الجديد أو `reset`",
            back_markup())

    elif act == "📣 إذاعة جماعية":
        set_state(uid, "broadcast")
        admin_respond(chat_id, uid,
            f"📣 *إذاعة*\n👥 الهدف: `{get_active_count()}`\n\nأرسل الرسالة الآن",
            back_markup())

    elif act == "🔍 بحث مستخدم":
        set_state(uid, "search_user")
        admin_respond(chat_id, uid, "🔍 أرسل *User ID*", back_markup())

    elif act == "🚫 بان مستخدم":
        set_state(uid, "ban_user")
        admin_respond(chat_id, uid,
            "🚫 أرسل *ID* للحظر\nأو `unban ID` لفك الحظر", back_markup())

    elif act == "📋 تصدير المستخدمين":
        users = export_users_list()
        if not users:
            admin_respond(chat_id, uid, "⚠️ لا يوجد.", back_markup())
            return
        chunk = "\n".join(users[:80])
        txt = f"📋 *المستخدمين ({len(users)}):*\n\n{chunk}"
        if len(users) > 80: txt += f"\n... +{len(users)-80}"
        admin_respond(chat_id, uid, txt[:4000], back_markup())

    elif act == "🏆 المُحيلين":
        leaders = get_referral_leaderboard(10)
        if not leaders:
            admin_respond(chat_id, uid, "⚠️ لا توجد إحالات.", back_markup())
            return
        txt = "🏆 *أعلى المُحيلين:*\n━━━━━━━━━━━━━━━\n"
        for i, r in enumerate(leaders, 1):
            medal = "🥇🥈🥉"[i-1] if i <= 3 else f"{i}."
            txt += f"{medal} {r['name']} → `{r['count']}`\n"
        admin_respond(chat_id, uid, txt, back_markup())

    elif act == "⚙️ الإعدادات":
        admin_respond(chat_id, uid, "⚙️ *الإعدادات:*", settings_markup())

    elif act == "🔄 تصفير شامل":
        admin_respond(chat_id, uid,
            "⚠️ *تصفير شامل!*\n\nحذف: لايكات + ملفات + تحميلات\n❗ المستخدمين وسجل الرسائل *لن تُحذف*",
            reset_markup())

    elif act == "❌ إخفاء":
        old = admin_panel_msg.get(uid)
        if old:
            delete_msg(chat_id, old)
            admin_panel_msg.pop(uid, None)
        clear_state(uid)
        bot.send_message(chat_id, "🔒 /admin",
            reply_markup=types.ReplyKeyboardRemove())


# ══════════════════════════════════════════
# 🔙 INLINE CALLBACKS
# ══════════════════════════════════════════

@bot.callback_query_handler(
    func=lambda c: c.data in [
        "back_panel", "toggle_maintenance",
        "toggle_subscription", "confirm_reset"
    ] or c.data.startswith("ban_") or c.data.startswith("unban_")
)
def handle_admin_cb(call):
    if not is_admin(call.from_user.id): return
    uid = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "back_panel":
        clear_state(uid)
        admin_respond(chat_id, uid, panel_text(uid))
        bot.answer_callback_query(call.id)

    elif call.data == "toggle_maintenance":
        cur = get_setting("maintenance_mode", False)
        set_setting("maintenance_mode", not cur)
        bot.answer_callback_query(call.id, f"🔧 {'ON' if not cur else 'OFF'}")
        admin_respond(chat_id, uid, "⚙️ *الإعدادات:*", settings_markup())

    elif call.data == "toggle_subscription":
        cur = get_setting("require_subscription", True)
        set_setting("require_subscription", not cur)
        bot.answer_callback_query(call.id, f"📢 {'ON' if not cur else 'OFF'}")
        admin_respond(chat_id, uid, "⚙️ *الإعدادات:*", settings_markup())

    elif call.data == "confirm_reset":
        full_reset()
        bot.answer_callback_query(call.id, "✅ تم!")
        admin_respond(chat_id, uid, f"🔄 *تم التصفير!*\n\n{panel_text(uid)}", back_markup())

    elif call.data.startswith("ban_"):
        ban_user(int(call.data.replace("ban_", "")))
        bot.answer_callback_query(call.id, "🚫 تم!", show_alert=True)

    elif call.data.startswith("unban_"):
        unban_user(int(call.data.replace("unban_", "")))
        bot.answer_callback_query(call.id, "✅ تم!", show_alert=True)


# ══════════════════════════════════════════
# 📝 STATE HANDLERS
# ══════════════════════════════════════════

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_state(m.from_user.id) == "custom_post" and m.text not in BTN_LIST,
    content_types=["text"])
def handle_custom_post(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    delete_msg(chat_id, message.message_id)
    if message.text.lower() == "reset":
        set_setting("custom_post_text", "")
        clear_state(uid)
        admin_respond(chat_id, uid, f"✅ *تم الإعادة للافتراضي!*\n\n{panel_text(uid)}", back_markup())
    else:
        set_setting("custom_post_text", message.text)
        clear_state(uid)
        admin_respond(chat_id, uid, f"✅ *تم الحفظ!*\n\n{panel_text(uid)}", back_markup())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_state(m.from_user.id) == "search_user" and m.text not in BTN_LIST,
    content_types=["text"])
def handle_search(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    delete_msg(chat_id, message.message_id)
    clear_state(uid)
    try: target = int(message.text.strip())
    except:
        admin_respond(chat_id, uid, "❌ ID غير صحيح!", back_markup())
        return
    info = search_user(target)
    if not info:
        admin_respond(chat_id, uid, f"❌ `{target}` غير موجود.", back_markup())
        return
    status = "🚫 محظور" if info.get("is_banned") else ("⛔ بلوك" if info.get("is_blocked") else "✅ نشط")
    joined = time.strftime("%Y-%m-%d %H:%M", time.localtime(info.get("joined_at", 0)))
    mk = types.InlineKeyboardMarkup()
    if info.get("is_banned"):
        mk.add(types.InlineKeyboardButton("✅ فك الحظر", callback_data=f"unban_{target}"))
    else:
        mk.add(types.InlineKeyboardButton("🚫 حظر", callback_data=f"ban_{target}"))
    mk.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_panel"))
    admin_respond(chat_id, uid,
        f"🔍 *المستخدم:*\n━━━━━━━━━━━━━━━\n"
        f"👤 {info.get('first_name','?')} | @{info.get('username','none')}\n"
        f"🆔 `{target}` | {status}\n📅 {joined}\n"
        f"❤️ `{info.get('like_count',0)}` | 📥 `{info.get('download_count',0)}` | 🔗 `{info.get('referral_count',0)}`",
        mk)


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_state(m.from_user.id) == "ban_user" and m.text not in BTN_LIST,
    content_types=["text"])
def handle_ban(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    delete_msg(chat_id, message.message_id)
    clear_state(uid)
    text = message.text.strip()
    try:
        if text.lower().startswith("unban"):
            target = int(text.split()[1])
            unban_user(target)
            admin_respond(chat_id, uid, f"✅ فك حظر `{target}`\n\n{panel_text(uid)}", back_markup())
        else:
            target = int(text)
            if target in ADMIN_IDS:
                admin_respond(chat_id, uid, "❌ لا يمكن حظر أدمن!", back_markup())
                return
            ban_user(target)
            admin_respond(chat_id, uid, f"🚫 حظر `{target}`\n\n{panel_text(uid)}", back_markup())
    except:
        admin_respond(chat_id, uid, "❌ صيغة خاطئة!", back_markup())


# ══════════════════════════════════════════
# 📣 BROADCAST
# ══════════════════════════════════════════

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and get_state(m.from_user.id) == "broadcast" and (m.text not in BTN_LIST if m.text else True),
    content_types=["text","photo","document","video","audio","sticker","animation","voice"])
def do_broadcast(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    clear_state(uid)
    users = get_all_users()
    if not users:
        admin_respond(chat_id, uid, "⚠️ لا يوجد مستخدمين!", back_markup())
        return

    total = len(users)
    admin_respond(chat_id, uid, f"📣 *جاري الإرسال...*\n👥 `{total}`\n⏳ 0%")
    ok = fail = block = 0
    t0 = time.time()

    for i, tuid in enumerate(users, 1):
        try:
            bot.forward_message(tuid, chat_id, message.message_id)
            ok += 1
            time.sleep(0.04)
        except telebot.apihelper.ApiTelegramException as e:
            if any(x in str(e).lower() for x in ["blocked","deactivated","not found"]):
                mark_user_blocked(tuid)
                block += 1
            else: fail += 1
        except: fail += 1

        if i % 25 == 0 or i == total:
            pct = int(i/total*100)
            bar = "█"*(pct//5) + "░"*(20-pct//5)
            admin_respond(chat_id, uid,
                f"📣 *إرسال...*\n[{bar}] {pct}%\n`{i}/{total}`\n✅{ok} 🚫{block} ❌{fail}")

    delete_msg(chat_id, message.message_id)
    admin_respond(chat_id, uid,
        f"📣 *تم!*\n✅ {ok} | 🚫 {block} | ❌ {fail}\n⏱️ {int(time.time()-t0)}s",
        back_markup())


# ══════════════════════════════════════════
# 📂 FILE UPLOAD
# ══════════════════════════════════════════

@bot.message_handler(content_types=["document"])
def handle_doc(message):
    if not is_admin(message.from_user.id): return
    uid = message.from_user.id
    chat_id = message.chat.id

    if get_state(uid) != "uploading":
        delete_msg(chat_id, message.message_id)
        admin_respond(chat_id, uid, "⚠️ اضغط 📤 أولاً.", back_markup())
        return

    fname = message.document.file_name or "file"
    add_config(message.document.file_id, fname)
    delete_msg(chat_id, message.message_id)
    admin_respond(chat_id, uid,
        f"📂 *وضع الرفع*\n━━━━━━━━━━━━━━━\n✅ `{fname}`\n📊 الإجمالي: `{get_configs_count()}`\n\n📎 أرسل المزيد أو ✅ إنهاء",
        back_markup())


# ══════════════════════════════════════════
# ❤️ LIKE
# ══════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data == "do_like")
def handle_like(call):
    try:
        uid = call.from_user.id
        mid = call.message.message_id
        cleanup_memory()
        if not check_cooldown(uid):
            bot.answer_callback_query(call.id, "⏳ انتظر...")
            return
        if check_maintenance(call, True): return
        if is_banned(uid):
            bot.answer_callback_query(call.id, "🚫 محظور!", show_alert=True)
            return
        is_new = add_like(uid, mid, dname(call.from_user))
        if not is_new:
            bot.answer_callback_query(call.id, "⚠️ سبق أن دعمت! ❤️", show_alert=True)
            return
        safe_edit_markup(call.message.chat.id, mid, channel_markup(mid))
        bot.answer_callback_query(call.id, "✅ شكراً! ❤️")
    except Exception as e:
        print(f"Like Error: {e}")
        try: bot.answer_callback_query(call.id, "❌ خطأ")
        except: pass


# ══════════════════════════════════════════
# 📥 DELIVERY (ألبوم + حذف ذكي)
# ══════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data == "get_file")
def handle_delivery(call):
    uid = call.from_user.id
    mid = call.message.message_id

    if not check_cooldown(uid):
        bot.answer_callback_query(call.id, "⏳ انتظر...")
        return
    if check_maintenance(call, True): return
    if is_banned(uid) and not is_admin(uid):
        bot.answer_callback_query(call.id, "🚫 محظور!", show_alert=True)
        return

    if is_admin(uid):
        try:
            smart_send(uid, mid)
            bot.answer_callback_query(call.id, "👑 Admin")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ {str(e)[:80]}", show_alert=True)
        return

    if get_setting("require_subscription", True):
        if not check_subscription(uid):
            bot.answer_callback_query(call.id, "⚠️ اشترك بالقناة أولاً!", show_alert=True)
            return

    if not has_liked(uid, mid):
        bot.answer_callback_query(call.id, "⛔ اضغط ❤️ أولاً!", show_alert=True)
        return

    try:
        smart_send(uid, mid)
        bot.answer_callback_query(call.id, "✅ تم!")
        safe_edit_markup(call.message.chat.id, mid, channel_markup(mid))
    except telebot.apihelper.ApiTelegramException as e:
        if any(x in str(e).lower() for x in ["blocked","not found","deactivated"]):
            bot.answer_callback_query(call.id, "❌ فعّل البوت أولاً! 🤖", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)
    except Exception as e:
        print(f"Delivery Error: {e}")
        bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)


def smart_send(user_id, post_id=None):
    # 1️⃣ حذف القديم
    old = get_message_history(user_id)
    for mid in old:
        try: bot.delete_message(user_id, mid)
        except: pass
    clear_message_history(user_id)

    # 2️⃣ جلب الملفات
    configs = get_all_configs()
    if not configs:
        m = bot.send_message(user_id, "⚠️ لا توجد ملفات حالياً.")
        save_message_history(user_id, [m.message_id])
        return False                          # ✅ أضفنا return False

    ids = []

    # 3️⃣ إرسال
    if len(configs) == 1:
        cfg = configs[0]
        caption = "📄 1/1"
        if cfg.get("name"): caption += f" • {cfg['name']}"
        try:
            d = bot.send_document(
                user_id,
                cfg["file_id"],
                caption=caption,
                parse_mode=None               # ✅ هذا السطر الجديد!
            )
            ids.append(d.message_id)
        except Exception as e:
            print(f"Single file error: {e}")
    else:
        chunks = [configs[i:i+10] for i in range(0, len(configs), 10)]
        for ci, chunk in enumerate(chunks):
            media = []
            for i, cfg in enumerate(chunk):
                num = ci * 10 + i + 1
                caption = f"📄 {num}/{len(configs)}"
                if cfg.get("name"): caption += f" • {cfg['name']}"
                media.append(InputMediaDocument(media=cfg["file_id"], caption=caption))
            try:
                msgs = bot.send_media_group(user_id, media)
                ids.extend([m.message_id for m in msgs])
            except:
                for cfg in chunk:
                    try:
                        d = bot.send_document(
                            user_id,
                            cfg["file_id"],
                            parse_mode=None   # ✅ هذا السطر الجديد!
                        )
                        ids.append(d.message_id)
                    except: pass

    # 4️⃣ حفظ
    if ids:                                   # ✅ فحص قبل الحفظ
        save_message_history(user_id, ids)
        record_download(user_id, post_id)
        return True                           # ✅ نجح
    return False                              # ✅ فشل


# ══════════════════════════════════════════
# 🌐 FLASK
# ══════════════════════════════════════════

app = Flask(__name__)

@app.route("/")
def home():
    return "<h2>🤖 Bot Running</h2>"

@app.route("/health")
def health():
    return "OK", 200

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()


# ══════════════════════════════════════════
# 🚀 MAIN (حل 409 النهائي)
# ══════════════════════════════════════════

def force_clear_session():
    """إزالة أي جلسة قديمة بالقوة"""
    print("🧹 Step 1: Remove webhook...")
    for i in range(3):
        try:
            bot.remove_webhook()
            break
        except:
            time.sleep(2)

    print("🧹 Step 2: Wait for old instance to die...")
    time.sleep(15)

    print("🧹 Step 3: Clear updates...")
    for attempt in range(10):
        try:
            bot.get_updates(offset=-1, timeout=1)
            print(f"   ✅ Cleared! (attempt {attempt+1})")
            return True
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                wait = 5
                print(f"   ⏳ 409 (attempt {attempt+1}) - wait {wait}s...")
                time.sleep(wait)
            else:
                print(f"   ❌ {e}")
                time.sleep(3)
        except Exception as e:
            print(f"   ❌ {e}")
            time.sleep(3)

    print("   ⚠️ Could not fully clear, trying anyway...")
    return False


if __name__ == "__main__":
    print("=" * 45)
    print("  🤖 VPN Bot V13 - Polling Mode")
    print("=" * 45)

    print("🔧 MongoDB...")
    if not init_db():
        exit(1)

    try:
        me = bot.get_me()
        BOT_USERNAME = me.username
        print(f"✅ @{BOT_USERNAME}")
    except Exception as e:
        print(f"❌ {e}")
        exit(1)

    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"📢 Channel: {CHANNEL_ID}")

    # ✅ تنظيف الجلسة القديمة
    force_clear_session()

    # ✅ تشغيل الويب سيرفر
    print("🌐 Web server...")
    keep_alive()

    print("🚀 Starting polling...\n")

    consecutive_409 = 0

    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=25,
                long_polling_timeout=20,
                allowed_updates=["message", "callback_query"],
                logger_level=None
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                consecutive_409 += 1
                wait = min(consecutive_409 * 5, 30)
                print(f"⚠️ 409 #{consecutive_409} - wait {wait}s...")

                if consecutive_409 >= 30:
                    print("❌ Too many 409! Exiting for restart...")
                    break

                time.sleep(wait)

                # محاولة تنظيف
                try:
                    bot.remove_webhook()
                    time.sleep(1)
                    bot.get_updates(offset=-1, timeout=1)
                except:
                    pass
            else:
                print(f"❌ API Error: {e}")
                time.sleep(5)
                consecutive_409 = 0

        except KeyboardInterrupt:
            print("\n🛑 Stopped.")
            break

        except Exception as e:
            consecutive_409 = 0
            print(f"❌ {e}")
            traceback.print_exc()
            time.sleep(5)
            print("🔄 Restarting...")
        else:
            consecutive_409 = 0

