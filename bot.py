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
    except telebot.apihelper.ApiTelegramException as e:
        err = str(e).lower()
        if any(x in err for x in [
            "message is not modified", "message to edit not found",
            "message can't be edited", "message not found"
        ]):
            return False
        print(f"⚠️ Edit error: {e}")
        return False
    except:
        return False


# ══════════════════════════════════════════
# 🎨 MARKUPS
# ══════════════════════════════════════════

def channel_markup(msg_id=None):
    likes = get_likes_count(msg_id) if msg_id else 0
    dl = get_post_downloads(msg_id) if msg_id else 0

    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.row(
        types.InlineKeyboardButton(f"❤️ دعم ({likes})", callback_data="do_like"),
        types.InlineKeyboardButton(f"📥 استلم ({dl})", callback_data="get_file")
    )
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
    mk.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="close_settings"))
    return mk


# ══════════════════════════════════════════
# 🚀 START
# ══════════════════════════════════════════

@bot.message_handler(commands=["start"])
def cmd_start(message):
    u = message.from_user
    uid = u.id

    if is_banned(uid) and not is_admin(uid):
        bot.send_message(uid, "🚫 تم حظرك من استخدام البوت.")
        return

    referrer = None
    args = message.text.split()
    if len(args) > 1:
        param = args[1]
        if param.startswith("ref_"):
            try:
                referrer = int(param.replace("ref_", ""))
                if referrer == uid:
                    referrer = None
            except:
                referrer = None

    is_new = add_user(uid, u.username, u.first_name, referrer)

    if is_admin(uid):
        show_panel(message)
        return

    bot.send_message(uid, "✅ تم تفعيل البوت، ارجع للقناة واستلم ملفاتك.")

    if is_new:
        ref_text = ""
        if referrer:
            ref_text = f"\n🔗 أحاله: `{referrer}`"
            try:
                bot.send_message(referrer,
                    f"🎉 شخص جديد انضم عبر رابط إحالتك!\n"
                    f"📊 إحالاتك: `{get_referral_count(referrer)}`")
            except:
                pass

        notify_admins(
            f"👤 *مستخدم جديد!*\n"
            f"• الاسم: {dname(u)}\n"
            f"• ID: `{uid}`{ref_text}\n"
            f"📊 الإجمالي: `{get_users_count()}`"
        )


@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if is_admin(message.from_user.id):
        show_panel(message)


@bot.message_handler(commands=["myref"])
def cmd_myref(message):
    uid = message.from_user.id
    count = get_referral_count(uid)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    bot.send_message(uid,
        f"🔗 *رابط إحالتك:*\n`{link}`\n\n"
        f"👥 عدد إحالاتك: `{count}`")


def show_panel(message):
    s = get_stats()
    state = get_state(message.from_user.id)
    state_txt = f"📝 State: `{state}`" if state else ""

    bot.send_message(message.chat.id,
        "👑 *Admin Panel V13*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📂 Files: `{s['configs']}`\n"
        f"👥 Users: `{s['active_users']}` / `{s['total_users']}`\n"
        f"🚫 Banned: `{s['banned_users']}` | ⛔ Blocked: `{s['blocked_users']}`\n"
        f"❤️ Likers: `{s['unique_likers']}`\n"
        f"📥 Downloads: `{s['total_downloads']}`\n"
        f"🔗 Referrals: `{s['total_referrals']}`\n"
        f"🆕 Today: `{s['new_today']}`\n"
        f"{state_txt}\n"
        "━━━━━━━━━━━━━━━━━━━",
        reply_markup=main_admin_markup()
    )


# ══════════════════════════════════════════
# 🎛️ ADMIN BUTTONS
# ══════════════════════════════════════════

BTN_LIST = [
    "📤 رفع ملفات", "📤 إضافة ملفات", "✅ إنهاء",
    "📢 نشر بالقناة", "🗑️ حذف الملفات", "📊 الإحصائيات",
    "👥 المتفاعلين", "📣 إذاعة جماعية", "✏️ تخصيص البوست",
    "🔄 تصفير شامل", "🔍 بحث مستخدم", "🚫 بان مستخدم",
    "📋 تصدير المستخدمين", "🏆 المُحيلين", "⚙️ الإعدادات",
    "❌ إخفاء", "✅ تأكيد التصفير", "❌ إلغاء"
]


@bot.message_handler(func=lambda m: m.text in BTN_LIST)
def handle_btns(message):
    if not is_admin(message.from_user.id):
        return

    uid = message.from_user.id
    act = message.text

    if act == "📤 رفع ملفات":
        set_state(uid, "uploading")
        clear_configs()
        bot.reply_to(message,
            "📂 *Upload Mode: ON (جديد)*\n"
            "🗑️ تم مسح القديم\n🔢 Counter: `0`\n\n📎 أرسل الملفات...")

    elif act == "📤 إضافة ملفات":
        set_state(uid, "uploading")
        current = get_configs_count()
        bot.reply_to(message,
            f"📂 *Upload Mode: ON (إضافة)*\n📁 الحالي: `{current}`\n\n📎 أرسل الملفات...")

    elif act == "✅ إنهاء":
        old_state = get_state(uid)
        clear_state(uid)
        bot.reply_to(message,
            f"✅ *Done!* Files: `{get_configs_count()}` | Closed: `{old_state or 'none'}`")

    elif act == "🗑️ حذف الملفات":
        clear_configs()
        bot.reply_to(message, "🗑️ All configs deleted.")

    elif act == "📊 الإحصائيات":
        s = get_stats()
        bot.reply_to(message,
            "📊 *Full Statistics*\n━━━━━━━━━━━━━━━\n"
            f"👥 Total: `{s['total_users']}` | Active: `{s['active_users']}`\n"
            f"⛔ Blocked: `{s['blocked_users']}` | 🚫 Banned: `{s['banned_users']}`\n"
            f"📂 Configs: `{s['configs']}`\n"
            f"❤️ Likers: `{s['unique_likers']}`\n"
            f"📥 Downloads: `{s['total_downloads']}` (Today: `{s['dl_today']}`)\n"
            f"🔗 Referrals: `{s['total_referrals']}`\n"
            f"🆕 New Today: `{s['new_today']}`")

    elif act == "👥 المتفاعلين":
        likers = get_all_likers()
        if not likers:
            bot.reply_to(message, "⚠️ No interactions.")
        else:
            names = list({u["name"] for u in likers})
            txt = f"👥 *Likers ({len(names)}):*\n"
            txt += "\n".join(f"  • {n}" for n in names[:50])
            if len(names) > 50:
                txt += f"\n... +{len(names)-50}"
            bot.reply_to(message, txt[:4000])

    elif act == "📢 نشر بالقناة":
        configs = get_all_configs()
        if not configs:
            bot.reply_to(message, "⚠️ No files!")
            return

        custom = get_setting("custom_post_text", "")
        if custom:
            text = custom
        else:
            text = (
                "🔥 *كونفيجات جديدة!* 🚀\n\n"
                f"📂 الملفات: `{len(configs)}`\n"
                "⚡️ سرعة عالية | 🔓 غير محدود\n\n"
                "⚠️ *الخطوات:*\n"
                "1️⃣ فعّل البوت 🤖\n"
                "2️⃣ اضغط ❤️\n"
                "3️⃣ استلم 📥"
            )

        try:
            mk = channel_markup(None)
            sent = bot.send_message(CHANNEL_ID, text,
                parse_mode="Markdown", reply_markup=mk)
            add_post(sent.message_id, text)
            bot.reply_to(message, f"✅ *Posted!* ID: `{sent.message_id}`")
        except Exception as e:
            bot.reply_to(message, f"❌ Error:\n`{e}`")

    elif act == "✏️ تخصيص البوست":
        set_state(uid, "custom_post")
        current = get_setting("custom_post_text", "")
        preview = current[:200] if current else "(افتراضي)"
        bot.reply_to(message,
            f"✏️ *Custom Post*\n📝 الحالي:\n{preview}\n\n"
            "أرسل النص الجديد أو `reset` للافتراضي\n✅ إنهاء للإلغاء")

    elif act == "📣 إذاعة جماعية":
        set_state(uid, "broadcast")
        bot.reply_to(message,
            f"📣 *Broadcast*\n👥 Target: `{get_active_count()}`\n\n"
            "أرسل الرسالة الآن\n✅ إنهاء للإلغاء")

    elif act == "🔍 بحث مستخدم":
        set_state(uid, "search_user")
        bot.reply_to(message, "🔍 أرسل *User ID*\n✅ إنهاء للإلغاء")

    elif act == "🚫 بان مستخدم":
        set_state(uid, "ban_user")
        bot.reply_to(message,
            "🚫 أرسل *User ID* للحظر\nأو `unban ID` لفك الحظر\n✅ إنهاء للإلغاء")

    elif act == "📋 تصدير المستخدمين":
        users = export_users_list()
        if not users:
            bot.reply_to(message, "⚠️ No users.")
            return
        chunk = "\n".join(users[:100])
        bot.reply_to(message, (f"📋 *Users ({len(users)}):*\n\n" + chunk)[:4000])

    elif act == "🏆 المُحيلين":
        leaders = get_referral_leaderboard(10)
        if not leaders:
            bot.reply_to(message, "⚠️ No referrals.")
            return
        txt = "🏆 *Top Referrers:*\n━━━━━━━━━━━━━━━\n"
        for i, r in enumerate(leaders, 1):
            medal = "🥇🥈🥉"[i-1] if i <= 3 else f"{i}."
            txt += f"{medal} {r['name']} → `{r['count']}`\n"
        bot.reply_to(message, txt)

    elif act == "⚙️ الإعدادات":
        bot.send_message(uid, "⚙️ *Settings:*", reply_markup=settings_markup())

    elif act == "🔄 تصفير شامل":
        mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
        mk.add("✅ تأكيد التصفير", "❌ إلغاء")
        bot.send_message(uid,
            "⚠️ *حذف:* لايكات + ملفات + سجل + تحميلات\n❗ المستخدمين *لن تُحذف*",
            reply_markup=mk)

    elif act == "✅ تأكيد التصفير":
        full_reset()
        bot.send_message(uid, "🔄 *Reset Done!*", reply_markup=main_admin_markup())

    elif act == "❌ إلغاء":
        clear_state(uid)
        bot.send_message(uid, "❌ Cancelled.", reply_markup=main_admin_markup())

    elif act == "❌ إخفاء":
        clear_state(uid)
        bot.send_message(uid, "🔒 /admin to reopen.",
            reply_markup=types.ReplyKeyboardRemove())


# ══════════════════════════════════════════
# 📝 STATE HANDLERS
# ══════════════════════════════════════════

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and
                   get_state(m.from_user.id) == "custom_post" and
                   m.text not in BTN_LIST,
    content_types=["text"]
)
def handle_custom_post(message):
    uid = message.from_user.id
    if message.text.lower() == "reset":
        set_setting("custom_post_text", "")
        clear_state(uid)
        bot.reply_to(message, "✅ تم الإعادة للافتراضي.", reply_markup=main_admin_markup())
    else:
        set_setting("custom_post_text", message.text)
        clear_state(uid)
        bot.reply_to(message, "✅ تم الحفظ!", reply_markup=main_admin_markup())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and
                   get_state(m.from_user.id) == "search_user" and
                   m.text not in BTN_LIST,
    content_types=["text"]
)
def handle_search(message):
    uid = message.from_user.id
    clear_state(uid)
    try:
        target = int(message.text.strip())
    except:
        bot.reply_to(message, "❌ ID غير صحيح!", reply_markup=main_admin_markup())
        return

    info = search_user(target)
    if not info:
        bot.reply_to(message, "❌ غير موجود.", reply_markup=main_admin_markup())
        return

    status = "🚫 Banned" if info.get("is_banned") else \
             ("⛔ Blocked" if info.get("is_blocked") else "✅ Active")
    joined = time.strftime("%Y-%m-%d %H:%M", time.localtime(info.get("joined_at", 0)))

    mk = types.InlineKeyboardMarkup()
    if info.get("is_banned"):
        mk.add(types.InlineKeyboardButton("✅ فك الحظر", callback_data=f"unban_{target}"))
    else:
        mk.add(types.InlineKeyboardButton("🚫 حظر", callback_data=f"ban_{target}"))

    bot.reply_to(message,
        f"🔍 *User Info:*\n━━━━━━━━━━━━━━━\n"
        f"👤 {info.get('first_name', '?')} | @{info.get('username', 'none')}\n"
        f"🆔 `{target}` | {status}\n📅 {joined}\n"
        f"❤️ Likes: `{info.get('like_count', 0)}` | "
        f"📥 DL: `{info.get('download_count', 0)}` | "
        f"🔗 Refs: `{info.get('referral_count', 0)}`",
        reply_markup=mk)


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and
                   get_state(m.from_user.id) == "ban_user" and
                   m.text not in BTN_LIST,
    content_types=["text"]
)
def handle_ban(message):
    uid = message.from_user.id
    clear_state(uid)
    text = message.text.strip()
    try:
        if text.lower().startswith("unban"):
            target = int(text.split()[1])
            unban_user(target)
            bot.reply_to(message, f"✅ Unbanned `{target}`", reply_markup=main_admin_markup())
        else:
            target = int(text)
            if target in ADMIN_IDS:
                bot.reply_to(message, "❌ لا يمكن حظر أدمن!", reply_markup=main_admin_markup())
                return
            ban_user(target)
            bot.reply_to(message, f"🚫 Banned `{target}`", reply_markup=main_admin_markup())
    except:
        bot.reply_to(message, "❌ صيغة خاطئة!", reply_markup=main_admin_markup())


# ══════════════════════════════════════════
# ⚙️ SETTINGS CALLBACKS
# ══════════════════════════════════════════

@bot.callback_query_handler(
    func=lambda c: c.data in ["toggle_maintenance", "toggle_subscription", "close_settings"]
                   or c.data.startswith("ban_") or c.data.startswith("unban_")
)
def handle_settings_cb(call):
    if not is_admin(call.from_user.id):
        return

    if call.data == "toggle_maintenance":
        cur = get_setting("maintenance_mode", False)
        set_setting("maintenance_mode", not cur)
        bot.answer_callback_query(call.id, f"🔧 {'ON' if not cur else 'OFF'}")
        safe_edit_markup(call.message.chat.id, call.message.message_id, settings_markup())

    elif call.data == "toggle_subscription":
        cur = get_setting("require_subscription", True)
        set_setting("require_subscription", not cur)
        bot.answer_callback_query(call.id, f"📢 {'ON' if not cur else 'OFF'}")
        safe_edit_markup(call.message.chat.id, call.message.message_id, settings_markup())

    elif call.data == "close_settings":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass

    elif call.data.startswith("ban_"):
        ban_user(int(call.data.replace("ban_", "")))
        bot.answer_callback_query(call.id, "🚫 Banned!", show_alert=True)

    elif call.data.startswith("unban_"):
        unban_user(int(call.data.replace("unban_", "")))
        bot.answer_callback_query(call.id, "✅ Unbanned!", show_alert=True)


# ══════════════════════════════════════════
# 📣 BROADCAST
# ══════════════════════════════════════════

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and
                   get_state(m.from_user.id) == "broadcast" and
                   (m.text not in BTN_LIST if m.text else True),
    content_types=["text","photo","document","video","audio","sticker","animation","voice"]
)
def do_broadcast(message):
    uid = message.from_user.id
    clear_state(uid)
    users = get_all_users()
    if not users:
        bot.reply_to(message, "⚠️ No users!")
        return

    total = len(users)
    st = bot.reply_to(message, f"📣 *Broadcasting to {total}...*")
    ok = fail = block = 0
    t0 = time.time()

    for i, tuid in enumerate(users, 1):
        try:
            bot.forward_message(tuid, message.chat.id, message.message_id)
            ok += 1
            time.sleep(0.04)
        except telebot.apihelper.ApiTelegramException as e:
            if any(x in str(e).lower() for x in ["blocked","deactivated","not found"]):
                mark_user_blocked(tuid)
                block += 1
            else:
                fail += 1
        except:
            fail += 1

        if i % 25 == 0 or i == total:
            pct = int(i/total*100)
            bar = "█"*(pct//5) + "░"*(20-pct//5)
            try:
                bot.edit_message_text(
                    f"📣 *Broadcasting...*\n[{bar}] {pct}%\n"
                    f"⏳ `{i}/{total}`\n✅{ok} 🚫{block} ❌{fail}",
                    message.chat.id, st.message_id, parse_mode="Markdown")
            except:
                pass

    try:
        bot.edit_message_text(
            f"📣 *Done!*\n✅ {ok} | 🚫 {block} | ❌ {fail}\n⏱️ {int(time.time()-t0)}s",
            message.chat.id, st.message_id, parse_mode="Markdown")
    except:
        pass


# ══════════════════════════════════════════
# 📂 FILE UPLOAD
# ══════════════════════════════════════════

@bot.message_handler(content_types=["document"])
def handle_doc(message):
    if not is_admin(message.from_user.id):
        return
    if get_state(message.from_user.id) != "uploading":
        bot.reply_to(message, "⚠️ اضغط 📤 أولاً.")
        return

    fname = message.document.file_name or "file"
    add_config(message.document.file_id, fname)
    bot.reply_to(message, f"✅ `{fname}` | Total: `{get_configs_count()}`")


# ══════════════════════════════════════════
# ❤️ LIKE (عداد حي)
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
        if check_maintenance(call, True):
            return
        if is_banned(uid):
            bot.answer_callback_query(call.id, "🚫 محظور!", show_alert=True)
            return

        is_new = add_like(uid, mid, dname(call.from_user))
        if not is_new:
            bot.answer_callback_query(call.id, "⚠️ سبق أن دعمت! ❤️", show_alert=True)
            return

        # ✅ تحديث العداد الحي فوراً
        safe_edit_markup(call.message.chat.id, mid, channel_markup(mid))
        bot.answer_callback_query(call.id, "✅ شكراً! ❤️")

    except Exception as e:
        print(f"Like Error: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ خطأ")
        except:
            pass


# ══════════════════════════════════════════
# 📥 DELIVERY (ألبوم + حذف ذكي + عداد حي)
# ══════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data == "get_file")
def handle_delivery(call):
    uid = call.from_user.id
    mid = call.message.message_id

    if not check_cooldown(uid):
        bot.answer_callback_query(call.id, "⏳ انتظر...")
        return
    if check_maintenance(call, True):
        return
    if is_banned(uid) and not is_admin(uid):
        bot.answer_callback_query(call.id, "🚫 محظور!", show_alert=True)
        return

    # أدمن
    if is_admin(uid):
        try:
            smart_send(uid, mid)
            bot.answer_callback_query(call.id, "👑 Admin")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ {str(e)[:80]}", show_alert=True)
        return

    # فحص اشتراك
    if get_setting("require_subscription", True):
        if not check_subscription(uid):
            bot.answer_callback_query(call.id,
                "⚠️ اشترك بالقناة أولاً!", show_alert=True)
            return

    # فحص لايك
    if not has_liked(uid, mid):
        bot.answer_callback_query(call.id, "⛔ اضغط ❤️ أولاً!", show_alert=True)
        return

    # إرسال
    try:
        smart_send(uid, mid)
        bot.answer_callback_query(call.id, "✅ تم!")

        # ✅ تحديث عداد التحميلات الحي
        safe_edit_markup(call.message.chat.id, mid, channel_markup(mid))

    except telebot.apihelper.ApiTelegramException as e:
        if any(x in str(e).lower() for x in ["blocked","not found","deactivated"]):
            bot.answer_callback_query(call.id,
                "❌ فعّل البوت أولاً! 🤖", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)
    except Exception as e:
        print(f"Delivery Error: {e}")
        bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)


def smart_send(user_id, post_id=None):
    """⚡ حذف ذكي + إرسال كألبوم"""

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

    ids = []

    # 3️⃣ إرسال كألبوم
    if len(configs) == 1:
        # ملف واحد فقط
        cfg = configs[0]
        caption = f"📄 1/1"
        if cfg.get("name"):
            caption += f" • {cfg['name']}"
        try:
            d = bot.send_document(user_id, cfg["file_id"], caption=caption)
            ids.append(d.message_id)
        except Exception as e:
            print(f"Send error: {e}")
    else:
        # عدة ملفات = ألبومات (10 بكل ألبوم كحد أقصى)
        chunks = [configs[i:i+10] for i in range(0, len(configs), 10)]

        for chunk_idx, chunk in enumerate(chunks):
            media = []
            for i, cfg in enumerate(chunk):
                file_num = chunk_idx * 10 + i + 1
                caption = f"📄 {file_num}/{len(configs)}"
                if cfg.get("name"):
                    caption += f" • {cfg['name']}"

                media.append(InputMediaDocument(
                    media=cfg["file_id"],
                    caption=caption
                ))

            try:
                msgs = bot.send_media_group(user_id, media)
                ids.extend([m.message_id for m in msgs])
            except Exception as e:
                print(f"Album error: {e}")
                # فشل الألبوم = إرسال فردي
                for cfg in chunk:
                    try:
                        d = bot.send_document(user_id, cfg["file_id"])
                        ids.append(d.message_id)
                    except:
                        pass

    # 4️⃣ حفظ + تسجيل
    save_message_history(user_id, ids)
    record_download(user_id, post_id)


# ══════════════════════════════════════════
# 🌐 FLASK (بسيط بدون Dashboard)
# ══════════════════════════════════════════

app = Flask(__name__)

@app.route("/")
def home():
    return "<h2>🤖 Bot V13 Running</h2>"

@app.route("/health")
def health():
    return "OK", 200

def keep_alive():
    port = int(os.environ.get("PORT", 8080))
    Thread(target=lambda: app.run(host="0.0.0.0", port=port), daemon=True).start()


# ══════════════════════════════════════════
# 🚀 MAIN
# ══════════════════════════════════════════

def clear_old_sessions():
    for attempt in range(1, 6):
        try:
            bot.delete_webhook(drop_pending_updates=True)
            bot.get_updates(offset=-1, timeout=1)
            print(f"✅ Session cleared (attempt {attempt})")
            return True
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                wait = attempt * 3
                print(f"⏳ 409 (attempt {attempt}) - Wait {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(3)
        except:
            time.sleep(3)
    return False


if __name__ == "__main__":
    print("=" * 45)
    print("  🤖 VPN Bot V13")
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

    print("🧹 Clearing sessions...")
    clear_old_sessions()
    print("⏳ Wait 10s...")
    time.sleep(10)

    print("🌐 Web server...")
    keep_alive()
    print("🚀 Started!\n")

    retry_count = 0
    while True:
        try:
            bot.infinity_polling(
                skip_pending=True, timeout=20,
                long_polling_timeout=40,
                allowed_updates=["message", "callback_query"]
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                retry_count += 1
                wait = min(retry_count * 5, 60)
                print(f"⚠️ 409 #{retry_count} - Wait {wait}s")
                if retry_count >= 20:
                    break
                time.sleep(wait)
                try:
                    bot.delete_webhook(drop_pending_updates=True)
                    time.sleep(2)
                    bot.get_updates(offset=-1, timeout=1)
                except:
                    pass
            else:
                time.sleep(5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            retry_count = 0
            print(f"❌ {e}")
            traceback.print_exc()
            time.sleep(5)
        else:
            retry_count = 0
