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
            
