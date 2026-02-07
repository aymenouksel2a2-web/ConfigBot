import telebot
from telebot import types
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

# Runtime State
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
    """تعديل أزرار الرسالة بشكل آمن"""
    try:
        bot.edit_message_reply_markup(
            chat_id, message_id,
            reply_markup=markup
        )
        return True
    except telebot.apihelper.ApiTelegramException as e:
        err = str(e).lower()
        if any(x in err for x in [
            "message is not modified",
            "message to edit not found",
            "message can't be edited",
            "message not found"
        ]):
            return False
        else:
            print(f"⚠️ Edit markup error: {e}")
            return False
    except Exception as e:
        print(f"⚠️ Unexpected edit error: {e}")
        return False


# ══════════════════════════════════════════
# 🎨 MARKUPS
# ══════════════════════════════════════════

def channel_markup(msg_id=None):
    count = get_likes_count(msg_id) if msg_id else 0
    dl = get_post_downloads(msg_id) if msg_id else 0

    mk = types.InlineKeyboardMarkup(row_width=1)
    mk.add(types.InlineKeyboardButton(
        f"❤️ دعم ({count})", callback_data="do_like"))
    mk.add(types.InlineKeyboardButton(
        f"📥 استلام ({dl})", callback_data="get_file"))
    mk.add(types.InlineKeyboardButton(
        "🤖 تفعيل البوت أولاً",
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
    mk.add(types.InlineKeyboardButton(
        "🔙 رجوع", callback_data="close_settings"))
    return mk


# ══════════════════════════════════════════
# 🚀 START + REFERRAL
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

    # ✅ تفعيل صامت - بدون رسالة ترحيب
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

    bot.send_message(uid, welcome)

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
        f"👥 عدد إحالاتك: `{count}`\n\n"
        "📤 شارك الرابط مع أصدقائك!")


def show_panel(message):
    s = get_stats()
    state = get_state(message.from_user.id)
    state_txt = f"📝 State: `{state}`" if state else ""

    bot.send_message(message.chat.id,
        "👑 *Admin Panel V13 Ultimate*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📂 Files: `{s['configs']}`\n"
        f"👥 Users: `{s['active_users']}` / `{s['total_users']}`\n"
        f"🚫 Banned: `{s['banned_users']}` | ⛔ Blocked: `{s['blocked_users']}`\n"
        f"❤️ Likers: `{s['unique_likers']}`\n"
        f"📥 Downloads: `{s['total_downloads']}`\n"
        f"🔗 Referrals: `{s['total_referrals']}`\n"
        f"🆕 Today: `{s['new_today']}`\n"
        f"{state_txt}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🗄️ MongoDB | Smart Delete | Referral",
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

    # ── 📤 رفع ملفات (جديد) ──
    if act == "📤 رفع ملفات":
        set_state(uid, "uploading")
        clear_configs()
        bot.reply_to(message,
            "📂 *Upload Mode: ON (جديد)*\n"
            "🗑️ تم مسح الملفات القديمة\n"
            "🔢 Counter: `0`\n\n"
            "📎 أرسل الملفات الآن...")

    # ── 📤 إضافة ملفات ──
    elif act == "📤 إضافة ملفات":
        set_state(uid, "uploading")
        current = get_configs_count()
        bot.reply_to(message,
            "📂 *Upload Mode: ON (إضافة)*\n"
            f"📁 الملفات الحالية: `{current}`\n\n"
            "📎 أرسل الملفات الإضافية...")

    # ── ✅ إنهاء ──
    elif act == "✅ إنهاء":
        old_state = get_state(uid)
        clear_state(uid)
        count = get_configs_count()
        bot.reply_to(message,
            f"✅ *Done!*\n"
            f"📂 Total Files: `{count}`\n"
            f"📝 Closed: `{old_state or 'none'}`")

    # ── 🗑️ حذف الملفات ──
    elif act == "🗑️ حذف الملفات":
        clear_configs()
        bot.reply_to(message, "🗑️ All configs deleted.")

    # ── 📊 الإحصائيات ──
    elif act == "📊 الإحصائيات":
        s = get_stats()
        bot.reply_to(message,
            "📊 *Full Statistics*\n"
            "━━━━━━━━━━━━━━━\n"
            f"👥 Total Users: `{s['total_users']}`\n"
            f"✅ Active: `{s['active_users']}`\n"
            f"⛔ Blocked Bot: `{s['blocked_users']}`\n"
            f"🚫 Banned: `{s['banned_users']}`\n"
            f"📂 Configs: `{s['configs']}`\n"
            f"❤️ Unique Likers: `{s['unique_likers']}`\n"
            f"📥 Total Downloads: `{s['total_downloads']}`\n"
            f"🔗 Referrals: `{s['total_referrals']}`\n"
            f"🆕 New Today: `{s['new_today']}`\n"
            "━━━━━━━━━━━━━━━"
        )

    # ── 👥 المتفاعلين ──
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

    # ── 📢 نشر بالقناة ──
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
            sent = bot.send_message(
                CHANNEL_ID, text,
                parse_mode="Markdown",
                reply_markup=mk
            )
            add_post(sent.message_id, text)
            bot.reply_to(message,
                f"✅ *Posted!* (ID: `{sent.message_id}`)")
        except Exception as e:
            bot.reply_to(message, f"❌ Error:\n`{e}`")

    # ── ✏️ تخصيص البوست ──
    elif act == "✏️ تخصيص البوست":
        set_state(uid, "custom_post")
        current = get_setting("custom_post_text", "")
        preview = current[:200] if current else "(افتراضي)"

        bot.reply_to(message,
            "✏️ *Custom Post Text*\n\n"
            f"📝 الحالي:\n{preview}\n\n"
            "أرسل النص الجديد للبوست\n"
            "أو أرسل `reset` للعودة للافتراضي\n\n"
            "اضغط *✅ إنهاء* للإلغاء")

    # ── 📣 إذاعة جماعية ──
    elif act == "📣 إذاعة جماعية":
        set_state(uid, "broadcast")
        count = get_active_count()
        bot.reply_to(message,
            f"📣 *Broadcast Mode*\n\n"
            f"👥 سيتم الإرسال لـ `{count}` مستخدم\n\n"
            "أرسل الرسالة الآن\n"
            "(نص / صورة / ملف / فيديو)\n\n"
            "اضغط *✅ إنهاء* للإلغاء")

    # ── 🔍 بحث مستخدم ──
    elif act == "🔍 بحث مستخدم":
        set_state(uid, "search_user")
        bot.reply_to(message,
            "🔍 أرسل *User ID* للبحث عنه\n\n"
            "اضغط *✅ إنهاء* للإلغاء")

    # ── 🚫 بان مستخدم ──
    elif act == "🚫 بان مستخدم":
        set_state(uid, "ban_user")
        bot.reply_to(message,
            "🚫 أرسل *User ID* لحظره\n"
            "أو أرسل `unban ID` لفك الحظر\n\n"
            "مثال: `unban 123456789`\n\n"
            "اضغط *✅ إنهاء* للإلغاء")

    # ── 📋 تصدير المستخدمين ──
    elif act == "📋 تصدير المستخدمين":
        users = export_users_list()
        if not users:
            bot.reply_to(message, "⚠️ No users.")
            return

        chunk = "\n".join(users[:100])
        header = f"📋 *Users ({len(users)}):*\n\n"
        bot.reply_to(message, (header + chunk)[:4000])
        if len(users) > 100:
            bot.send_message(uid, f"... +{len(users)-100} more users")

    # ── 🏆 المُحيلين ──
    elif act == "🏆 المُحيلين":
        leaders = get_referral_leaderboard(10)
        if not leaders:
            bot.reply_to(message, "⚠️ No referrals yet.")
            return
        txt = "🏆 *Top Referrers:*\n━━━━━━━━━━━━━━━\n"
        for i, r in enumerate(leaders, 1):
            medal = "🥇🥈🥉"[i-1] if i <= 3 else f"{i}."
            txt += f"{medal} {r['name']} → `{r['count']}` refs\n"
        bot.reply_to(message, txt)

    # ── ⚙️ الإعدادات ──
    elif act == "⚙️ الإعدادات":
        bot.send_message(uid, "⚙️ *Settings:*",
            reply_markup=settings_markup())

    # ── 🔄 تصفير شامل ──
    elif act == "🔄 تصفير شامل":
        mk = types.ReplyKeyboardMarkup(resize_keyboard=True)
        mk.add("✅ تأكيد التصفير", "❌ إلغاء")
        bot.send_message(uid,
            "⚠️ *سيتم حذف:*\n"
            "• اللايكات\n• الملفات\n"
            "• سجل الرسائل\n• التحميلات\n\n"
            "❗ المستخدمين والإحالات *لن تُحذف*",
            reply_markup=mk)

    elif act == "✅ تأكيد التصفير":
        full_reset()
        bot.send_message(uid, "🔄 *Full Reset Done!*",
            reply_markup=main_admin_markup())

    elif act == "❌ إلغاء":
        clear_state(uid)
        bot.send_message(uid, "❌ Cancelled.",
            reply_markup=main_admin_markup())

    # ── ❌ إخفاء ──
    elif act == "❌ إخفاء":
        clear_state(uid)
        bot.send_message(uid,
            "🔒 Hidden. /admin to reopen.",
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
        bot.reply_to(message, "✅ تم إعادة النص للافتراضي.",
            reply_markup=main_admin_markup())
    else:
        set_setting("custom_post_text", message.text)
        clear_state(uid)
        bot.reply_to(message, "✅ تم حفظ النص الجديد!",
            reply_markup=main_admin_markup())


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
        bot.reply_to(message, "❌ أرسل رقم ID صحيح!",
            reply_markup=main_admin_markup())
        return

    info = search_user(target)
    if not info:
        bot.reply_to(message, "❌ مستخدم غير موجود.",
            reply_markup=main_admin_markup())
        return

    status = "🚫 Banned" if info.get("is_banned") else \
             ("⛔ Blocked" if info.get("is_blocked") else "✅ Active")

    joined = time.strftime("%Y-%m-%d %H:%M",
        time.localtime(info.get("joined_at", 0)))

    txt = (
        f"🔍 *User Info:*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Name: {info.get('first_name', '?')}\n"
        f"📛 Username: @{info.get('username', 'none')}\n"
        f"🆔 ID: `{target}`\n"
        f"📊 Status: {status}\n"
        f"📅 Joined: {joined}\n"
        f"❤️ Likes: `{info.get('like_count', 0)}`\n"
        f"📥 Downloads: `{info.get('download_count', 0)}`\n"
        f"🔗 Referrals: `{info.get('referral_count', 0)}`\n"
        f"━━━━━━━━━━━━━━━"
    )

    mk = types.InlineKeyboardMarkup()
    if info.get("is_banned"):
        mk.add(types.InlineKeyboardButton(
            "✅ فك الحظر", callback_data=f"unban_{target}"))
    else:
        mk.add(types.InlineKeyboardButton(
            "🚫 حظر", callback_data=f"ban_{target}"))

    bot.reply_to(message, txt, reply_markup=mk)


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
            bot.reply_to(message, f"✅ تم فك حظر `{target}`",
                reply_markup=main_admin_markup())
        else:
            target = int(text)
            if target in ADMIN_IDS:
                bot.reply_to(message, "❌ لا يمكن حظر أدمن!",
                    reply_markup=main_admin_markup())
                return
            ban_user(target)
            bot.reply_to(message, f"🚫 تم حظر `{target}`",
                reply_markup=main_admin_markup())
    except:
        bot.reply_to(message, "❌ صيغة خاطئة!",
            reply_markup=main_admin_markup())


# ══════════════════════════════════════════
# ⚙️ SETTINGS CALLBACKS
# ══════════════════════════════════════════

@bot.callback_query_handler(
    func=lambda c: c.data in [
        "toggle_maintenance", "toggle_subscription",
        "close_settings"
    ] or c.data.startswith("ban_") or c.data.startswith("unban_")
)
def handle_settings_cb(call):
    if not is_admin(call.from_user.id):
        return

    if call.data == "toggle_maintenance":
        current = get_setting("maintenance_mode", False)
        set_setting("maintenance_mode", not current)
        status = "🟢 مفعل" if not current else "🔴 مغلق"
        bot.answer_callback_query(call.id, f"🔧 الصيانة: {status}")
        safe_edit_markup(
            call.message.chat.id, call.message.message_id,
            settings_markup()
        )

    elif call.data == "toggle_subscription":
        current = get_setting("require_subscription", True)
        set_setting("require_subscription", not current)
        status = "🟢 مفعل" if not current else "🔴 مغلق"
        bot.answer_callback_query(call.id, f"📢 فحص الاشتراك: {status}")
        safe_edit_markup(
            call.message.chat.id, call.message.message_id,
            settings_markup()
        )

    elif call.data == "close_settings":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id, "✅")

    elif call.data.startswith("ban_"):
        target = int(call.data.replace("ban_", ""))
        ban_user(target)
        bot.answer_callback_query(call.id,
            f"🚫 تم حظر {target}", show_alert=True)

    elif call.data.startswith("unban_"):
        target = int(call.data.replace("unban_", ""))
        unban_user(target)
        bot.answer_callback_query(call.id,
            f"✅ تم فك حظر {target}", show_alert=True)


# ══════════════════════════════════════════
# 📣 BROADCAST
# ══════════════════════════════════════════

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and
                   get_state(m.from_user.id) == "broadcast" and
                   (m.text not in BTN_LIST if m.text else True),
    content_types=[
        "text", "photo", "document", "video",
        "audio", "sticker", "animation",
        "voice", "video_note"
    ]
)
def do_broadcast(message):
    uid = message.from_user.id
    clear_state(uid)

    users = get_all_users()
    if not users:
        bot.reply_to(message, "⚠️ No users!")
        return

    total = len(users)
    st = bot.reply_to(message,
        f"📣 *Broadcasting...*\n"
        f"👥 Target: `{total}`\n"
        f"⏳ `0/{total}` (0%)")

    ok = fail = block = 0
    start_time = time.time()

    for i, target_uid in enumerate(users, 1):
        try:
            bot.forward_message(
                target_uid, message.chat.id,
                message.message_id)
            ok += 1
            time.sleep(0.04)
        except telebot.apihelper.ApiTelegramException as e:
            err = str(e).lower()
            if any(x in err for x in ["blocked", "deactivated", "chat not found"]):
                mark_user_blocked(target_uid)
                block += 1
            else:
                fail += 1
        except:
            fail += 1

        if i % 25 == 0 or i == total:
            pct = int(i / total * 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            elapsed = int(time.time() - start_time)

            try:
                bot.edit_message_text(
                    f"📣 *Broadcasting...*\n"
                    f"[{bar}] {pct}%\n"
                    f"⏳ `{i}/{total}`\n"
                    f"✅ {ok} | 🚫 {block} | ❌ {fail}\n"
                    f"⏱️ {elapsed}s",
                    message.chat.id, st.message_id,
                    parse_mode="Markdown")
            except:
                pass

    elapsed = int(time.time() - start_time)
    try:
        bot.edit_message_text(
            f"📣 *Broadcast Complete!*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✅ Sent: `{ok}`\n"
            f"🚫 Blocked: `{block}`\n"
            f"❌ Failed: `{fail}`\n"
            f"📊 Total: `{total}`\n"
            f"⏱️ Time: `{elapsed}s`",
            message.chat.id, st.message_id,
            parse_mode="Markdown")
    except:
        bot.send_message(uid,
            f"✅ {ok} | 🚫 {block} | ❌ {fail}")


# ══════════════════════════════════════════
# 📂 FILE UPLOAD
# ══════════════════════════════════════════

@bot.message_handler(content_types=["document"])
def handle_doc(message):
    if not is_admin(message.from_user.id):
        return

    if get_state(message.from_user.id) != "uploading":
        bot.reply_to(message, "⚠️ اضغط 📤 أولاً لتفعيل وضع الرفع.")
        return

    fname = message.document.file_name or "file"
    add_config(message.document.file_id, fname)
    cnt = get_configs_count()

    bot.reply_to(message, f"✅ `{fname}`\n📂 Total: `{cnt}`")


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

        if check_maintenance(call, True):
            return

        if is_banned(uid):
            bot.answer_callback_query(call.id,
                "🚫 محظور!", show_alert=True)
            return

        name = dname(call.from_user)
        is_new = add_like(uid, mid, name)

        if not is_new:
            bot.answer_callback_query(call.id,
                "⚠️ سبق أن دعمت! ❤️", show_alert=True)
            return

        safe_edit_markup(
            call.message.chat.id, mid,
            channel_markup(mid)
        )

        bot.answer_callback_query(call.id, "✅ شكراً! ❤️")

    except Exception as e:
        print(f"Like Error: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ خطأ")
        except:
            pass


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

    if check_maintenance(call, True):
        return

    if is_banned(uid) and not is_admin(uid):
        bot.answer_callback_query(call.id,
            "🚫 محظور!", show_alert=True)
        return

    # أدمن
    if is_admin(uid):
        try:
            smart_send(uid, mid)
            bot.answer_callback_query(call.id, "👑 Admin")
        except Exception as e:
            bot.answer_callback_query(call.id,
                f"❌ {str(e)[:80]}", show_alert=True)
        return

    # فحص الاشتراك
    if get_setting("require_subscription", True):
        if not check_subscription(uid):
            bot.answer_callback_query(call.id,
                "⚠️ اشترك بالقناة أولاً!\nثم حاول مرة أخرى.",
                show_alert=True)
            return

    # فحص اللايك
    if not has_liked(uid, mid):
        bot.answer_callback_query(call.id,
            "⛔ اضغط ❤️ أولاً!", show_alert=True)
        return

    # إرسال
    try:
        smart_send(uid, mid)
        bot.answer_callback_query(call.id, "✅ تم!")

        safe_edit_markup(
            call.message.chat.id, mid,
            channel_markup(mid)
        )

    except telebot.apihelper.ApiTelegramException as e:
        err = str(e).lower()
        if any(x in err for x in ["blocked", "not found", "deactivated"]):
            bot.answer_callback_query(call.id,
                "❌ فعّل البوت أولاً! اضغط 🤖",
                show_alert=True)
        else:
            bot.answer_callback_query(call.id,
                "❌ خطأ، حاول لاحقاً", show_alert=True)
    except Exception as e:
        print(f"Delivery Error: {e}")
        bot.answer_callback_query(call.id,
            "❌ خطأ، حاول لاحقاً", show_alert=True)


def smart_send(user_id, post_id=None):
    # 1 حذف القديم
    old = get_message_history(user_id)
    for mid in old:
        try:
            bot.delete_message(user_id, mid)
        except:
            pass
    clear_message_history(user_id)

    # 2 جلب الملفات
    configs = get_all_configs()
    if not configs:
        m = bot.send_message(user_id, "⚠️ لا توجد ملفات حالياً.")
        save_message_history(user_id, [m.message_id])
        return

    # 3 إرسال الملفات فقط بدون رسائل إضافية
    ids = []

    for i, cfg in enumerate(configs, 1):
        try:
            caption = f"📄 {i}/{len(configs)}"
            if cfg.get("name"):
                caption += f" • `{cfg['name']}`"
            d = bot.send_document(user_id, cfg["file_id"],
                caption=caption, parse_mode="Markdown")
            ids.append(d.message_id)
        except Exception as e:
            print(f"Send error {user_id}: {e}")

    # 4 حفظ
    save_message_history(user_id, ids)
    record_download(user_id, post_id)


# ══════════════════════════════════════════
# 🌐 FLASK
# ══════════════════════════════════════════

app = Flask(__name__)


@app.route("/")
def home():
    try:
        s = get_stats()
        maint = "🔧 MAINTENANCE" if get_setting("maintenance_mode") else "✅ ONLINE"
        return f"""
        <html>
        <head>
            <title>VPN Bot V13</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Courier New', monospace;
                    background: linear-gradient(135deg, #0a0a1a, #1a1a3e);
                    color: #00ff88; padding: 40px;
                    min-height: 100vh;
                }}
                .card {{
                    background: rgba(0,0,0,0.4);
                    border: 1px solid #00ff88;
                    border-radius: 12px; padding: 25px;
                    max-width: 500px; margin: 0 auto;
                }}
                h1 {{ text-align: center; color: #fff; }}
                .stat {{ margin: 8px 0; font-size: 16px; }}
                .status {{ text-align: center; font-size: 20px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🤖 VPN Bot V13</h1>
                <div class="status">{maint}</div>
                <hr style="border-color: #00ff8844;">
                <div class="stat">👥 Users: {s['total_users']}</div>
                <div class="stat">✅ Active: {s['active_users']}</div>
                <div class="stat">📂 Configs: {s['configs']}</div>
                <div class="stat">❤️ Likers: {s['unique_likers']}</div>
                <div class="stat">📥 Downloads: {s['total_downloads']}</div>
                <div class="stat">🔗 Referrals: {s['total_referrals']}</div>
                <div class="stat">🆕 Today: {s['new_today']}</div>
            </div>
        </body>
        </html>
        """
    except:
        return "<h1>Bot Running</h1>"


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
# 🚀 MAIN (مع حل 409)
# ══════════════════════════════════════════

def clear_old_sessions():
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            bot.delete_webhook(drop_pending_updates=True)
            print(f"✅ Webhook cleared (attempt {attempt})")
            bot.get_updates(offset=-1, timeout=1)
            print("✅ Old session cleared!")
            return True
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                wait = attempt * 3
                print(f"⏳ 409 Conflict (attempt {attempt}/{max_retries})"
                      f" - Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"❌ API Error: {e}")
                time.sleep(3)
        except Exception as e:
            print(f"❌ Error: {e}")
            time.sleep(3)

    print("⚠️ Could not clear old session, trying anyway...")
    return False


if __name__ == "__main__":
    print("=" * 45)
    print("  🤖 VPN Bot V13 Ultimate Edition")
    print("=" * 45)

    print("🔧 Connecting to MongoDB...")
    if not init_db():
        print("❌ MongoDB connection failed!")
        exit(1)

    try:
        me = bot.get_me()
        BOT_USERNAME = me.username
        print(f"✅ Bot: @{BOT_USERNAME}")
    except Exception as e:
        print(f"❌ Cannot get bot info: {e}")
        exit(1)

    print(f"👑 Admins: {ADMIN_IDS}")
    print(f"📢 Channel: {CHANNEL_ID}")

    print("🧹 Clearing old sessions...")
    clear_old_sessions()

    print("⏳ Waiting 10s for old instance to stop...")
    time.sleep(10)

    print("🌐 Starting web server...")
    keep_alive()

    print("🚀 Bot started!\n")

    retry_count = 0

    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=20,
                long_polling_timeout=40,
                allowed_updates=["message", "callback_query"]
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                retry_count += 1
                wait = min(retry_count * 5, 60)
                print(f"⚠️ 409 #{retry_count} - Wait {wait}s...")

                if retry_count >= 20:
                    print("❌ Too many 409! Exiting.")
                    break

                time.sleep(wait)
                try:
                    bot.delete_webhook(drop_pending_updates=True)
                    time.sleep(2)
                    bot.get_updates(offset=-1, timeout=1)
                except:
                    pass
            else:
                print(f"❌ API Error: {e}")
                time.sleep(5)

        except KeyboardInterrupt:
            print("\n🛑 Stopped.")
            break

        except Exception as e:
            retry_count = 0
            print(f"❌ Error: {e}")
            traceback.print_exc()
            time.sleep(5)
            print("🔄 Restarting...")
        else:
            retry_count = 0

