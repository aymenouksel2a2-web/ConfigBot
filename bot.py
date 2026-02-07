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
admin_panel_msg = {}   # ← رسالة اللوحة الوحيدة لكل أدمن
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
    """حذف رسالة بأمان"""
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
# 📨 نظام الرسالة الواحدة للأدمن
# ══════════════════════════════════════════

def admin_respond(chat_id, uid, text, inline_markup=None):
    """تعديل رسالة اللوحة أو إرسال جديدة إذا فشل التعديل"""
    msg_id = admin_panel_msg.get(uid)

    if msg_id:
        try:
            bot.edit_message_text(
                text, chat_id, msg_id,
                parse_mode="Markdown",
                reply_markup=inline_markup
            )
            return
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" in str(e).lower():
                return
        except:
            pass

    # فشل التعديل → رسالة جديدة
    m = bot.send_message(chat_id, text,
        parse_mode="Markdown",
        reply_markup=inline_markup)
    admin_panel_msg[uid] = m.message_id


# ══════════════════════════════════════════
# 🎨 MARKUPS
# ══════════════════════════════════════════

def channel_markup(msg_id=None):
    likes = get_likes_count(msg_id) if msg_id else 0
    dl = get_post_downloads(msg_id) if msg_id else 0

    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.row(
        types.InlineKeyboardButton(f"❤️ تفاعل ({likes})", callback_data="do_like"),
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
        types.InlineKeyboardButton("✅ تأكيد الحذف", callback_data="confirm_reset"),
        types.InlineKeyboardButton("❌ إلغاء", callback_data="back_panel")
    )
    return mk

def panel_text(uid=None):
    s = get_stats()
    state = get_state(uid) if uid else None
    state_txt = f"\n📝 الحالة: `{state}`" if state else ""

    return (
        "👑 *لوحة التحكم V13*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"📂 الملفات: `{s['configs']}`\n"
        f"👥 المستخدمين: `{s['active_users']}` / `{s['total_users']}`\n"
        f"🚫 محظور: `{s['banned_users']}` | ⛔ بلوك: `{s['blocked_users']}`\n"
        f"❤️ متفاعلين: `{s['unique_likers']}`\n"
        f"📥 تحميلات: `{s['total_downloads']}`\n"
        f"🔗 إحالات: `{s['total_referrals']}`\n"
        f"🆕 اليوم: `{s['new_today']}`"
        f"{state_txt}\n"
        "━━━━━━━━━━━━━━━━━━━"
    )


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
                    f"🎉 شخص جديد انضم عبر رابط إحالتك!\n"
                    f"📊 إحالاتك: `{get_referral_count(referrer)}`")
            except:
                pass
        notify_admins(
            f"👤 *مستخدم جديد!*\n"
            f"• {dname(u)}\n"
            f"• ID: `{uid}`{ref_text}\n"
            f"📊 الإجمالي: `{get_users_count()}`"
        )


@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if is_admin(message.from_user.id):
        delete_msg(message.chat.id, message.message_id)
        show_panel(message.chat.id, message.from_user.id)


@bot.message_handler(commands=["myref"])
def cmd_myref(message):
    uid = message.from_user.id
    count = get_referral_count(uid)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    bot.send_message(uid,
        f"🔗 *رابط إحالتك:*\n`{link}`\n\n👥 إحالاتك: `{count}`")


def show_panel(chat_id, uid):
    """إرسال لوحة جديدة + حذف القديمة"""
    # حذف اللوحة القديمة
    old = admin_panel_msg.get(uid)
    if old:
        delete_msg(chat_id, old)

    m = bot.send_message(chat_id, panel_text(uid),
        parse_mode="Markdown",
        reply_markup=main_admin_markup())
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
    if not is_admin(message.from_user.id):
        return

    uid = message.from_user.id
    chat_id = message.chat.id
    act = message.text

    # ✅ حذف رسالة الزر فوراً
    delete_msg(chat_id, message.message_id)

    # ── 📤 رفع ملفات (جديد) ──
    if act == "📤 رفع ملفات":
        set_state(uid, "uploading")
        clear_configs()
        admin_respond(chat_id, uid,
            "📂 *وضع الرفع (جديد)*\n"
            "🗑️ تم مسح القديم\n"
            "🔢 العداد: `0`\n\n"
            "📎 أرسل الملفات الآن...",
            back_markup())

    # ── 📤 إضافة ملفات ──
    elif act == "📤 إضافة ملفات":
        set_state(uid, "uploading")
        admin_respond(chat_id, uid,
            f"📂 *وضع الرفع (إضافة)*\n"
            f"📁 الملفات الحالية: `{get_configs_count()}`\n\n"
            "📎 أرسل الملفات الإضافية...",
            back_markup())

    # ── ✅ إنهاء ──
    elif act == "✅ إنهاء":
        old_state = get_state(uid)
        clear_state(uid)
        admin_respond(chat_id, uid,
            f"✅ *تم الإنهاء!*\n"
            f"📂 إجمالي الملفات: `{get_configs_count()}`\n"
            f"📝 أُغلق: `{old_state or 'لا شيء'}`\n\n"
            f"{panel_text(uid)}",
            back_markup())

    # ── 🗑️ حذف الملفات ──
    elif act == "🗑️ حذف الملفات":
        clear_configs()
        admin_respond(chat_id, uid,
            "🗑️ *تم حذف جميع الملفات!*\n\n"
            f"{panel_text(uid)}",
            back_markup())

    # ── 📊 الإحصائيات ──
    elif act == "📊 الإحصائيات":
        s = get_stats()
        admin_respond(chat_id, uid,
            "📊 *الإحصائيات الكاملة*\n"
            "━━━━━━━━━━━━━━━\n"
            f"👥 الإجمالي: `{s['total_users']}` | النشطين: `{s['active_users']}`\n"
            f"⛔ بلوك: `{s['blocked_users']}` | 🚫 محظور: `{s['banned_users']}`\n"
            f"📂 الملفات: `{s['configs']}`\n"
            f"❤️ المتفاعلين: `{s['unique_likers']}`\n"
            f"📥 التحميلات: `{s['total_downloads']}` (اليوم: `{s['dl_today']}`)\n"
            f"🔗 الإحالات: `{s['total_referrals']}`\n"
            f"🆕 جدد اليوم: `{s['new_today']}`",
            back_markup())

    # ── 👥 المتفاعلين ──
    elif act == "👥 المتفاعلين":
        likers = get_all_likers()
        if not likers:
            admin_respond(chat_id, uid,
                "⚠️ لا يوجد متفاعلين بعد.", back_markup())
        else:
            names = list({u["name"] for u in likers})
            txt = f"👥 *المتفاعلين ({len(names)}):*\n"
            txt += "\n".join(f"  • {n}" for n in names[:40])
            if len(names) > 40:
                txt += f"\n... +{len(names)-40}"
            admin_respond(chat_id, uid, txt[:4000], back_markup())

    # ── 📢 نشر بالقناة ──
    elif act == "📢 نشر بالقناة":
        configs = get_all_configs()
        if not configs:
            admin_respond(chat_id, uid,
                "⚠️ لا توجد ملفات للنشر!", back_markup())
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
            admin_respond(chat_id, uid,
                f"✅ *تم النشر بنجاح!*\n"
                f"🆔 ID: `{sent.message_id}`\n\n"
                f"{panel_text(uid)}",
                back_markup())
        except Exception as e:
            admin_respond(chat_id, uid,
                f"❌ *خطأ:*\n`{e}`", back_markup())

    # ── ✏️ تخصيص البوست ──
    elif act == "✏️ تخصيص البوست":
        set_state(uid, "custom_post")
        current = get_setting("custom_post_text", "")
        preview = current[:200] if current else "(النص الافتراضي)"
        admin_respond(chat_id, uid,
            "✏️ *تخصيص نص البوست*\n\n"
            f"📝 الحالي:\n{preview}\n\n"
            "📨 أرسل النص الجديد\n"
            "أو أرسل `reset` للافتراضي",
            back_markup())

    # ── 📣 إذاعة جماعية ──
    elif act == "📣 إذاعة جماعية":
        set_state(uid, "broadcast")
        admin_respond(chat_id, uid,
            f"📣 *وضع الإذاعة*\n\n"
            f"👥 سيتم الإرسال لـ `{get_active_count()}` مستخدم\n\n"
            "📨 أرسل الرسالة الآن\n"
            "(نص / صورة / ملف / فيديو)",
            back_markup())

    # ── 🔍 بحث مستخدم ──
    elif act == "🔍 بحث مستخدم":
        set_state(uid, "search_user")
        admin_respond(chat_id, uid,
            "🔍 *بحث عن مستخدم*\n\n"
            "📨 أرسل *User ID* للبحث",
            back_markup())

    # ── 🚫 بان مستخدم ──
    elif act == "🚫 بان مستخدم":
        set_state(uid, "ban_user")
        admin_respond(chat_id, uid,
            "🚫 *حظر مستخدم*\n\n"
            "📨 أرسل *User ID* للحظر\n"
            "أو `unban ID` لفك الحظر\n\n"
            "مثال: `unban 123456789`",
            back_markup())

    # ── 📋 تصدير المستخدمين ──
    elif act == "📋 تصدير المستخدمين":
        users = export_users_list()
        if not users:
            admin_respond(chat_id, uid,
                "⚠️ لا يوجد مستخدمين.", back_markup())
            return
        chunk = "\n".join(users[:80])
        txt = f"📋 *المستخدمين ({len(users)}):*\n\n{chunk}"
        if len(users) > 80:
            txt += f"\n... +{len(users)-80}"
        admin_respond(chat_id, uid, txt[:4000], back_markup())

    # ── 🏆 المُحيلين ──
    elif act == "🏆 المُحيلين":
        leaders = get_referral_leaderboard(10)
        if not leaders:
            admin_respond(chat_id, uid,
                "⚠️ لا توجد إحالات بعد.", back_markup())
            return
        txt = "🏆 *أعلى المُحيلين:*\n━━━━━━━━━━━━━━━\n"
        for i, r in enumerate(leaders, 1):
            medal = "🥇🥈🥉"[i-1] if i <= 3 else f"{i}."
            txt += f"{medal} {r['name']} → `{r['count']}`\n"
        admin_respond(chat_id, uid, txt, back_markup())

    # ── ⚙️ الإعدادات ──
    elif act == "⚙️ الإعدادات":
        admin_respond(chat_id, uid,
            "⚙️ *إعدادات البوت:*\n\n"
            "اختر الإعداد لتغييره:",
            settings_markup())

    # ── 🔄 تصفير شامل ──
    elif act == "🔄 تصفير شامل":
        admin_respond(chat_id, uid,
            "⚠️ *تصفير شامل!*\n\n"
            "*سيتم حذف:*\n"
            "• اللايكات\n• الملفات\n"
            "• سجل الرسائل\n• التحميلات\n\n"
            "❗ المستخدمين والإحالات *لن تُحذف*",
            reset_markup())

    # ── ❌ إخفاء ──
    elif act == "❌ إخفاء":
        old = admin_panel_msg.get(uid)
        if old:
            delete_msg(chat_id, old)
            admin_panel_msg.pop(uid, None)
        clear_state(uid)
        m = bot.send_message(chat_id,
            "🔒 تم إخفاء اللوحة\n/admin لإعادة الفتح",
            reply_markup=types.ReplyKeyboardRemove())
        # حذف رسالة الإخفاء بعد ثانية
        time.sleep(0.5)
        delete_msg(chat_id, m.message_id)


# ══════════════════════════════════════════
# 🔙 INLINE CALLBACKS (رجوع + إعدادات + تصفير)
# ══════════════════════════════════════════

@bot.callback_query_handler(
    func=lambda c: c.data in [
        "back_panel", "toggle_maintenance",
        "toggle_subscription", "confirm_reset", "cancel_reset"
    ] or c.data.startswith("ban_") or c.data.startswith("unban_")
)
def handle_admin_callbacks(call):
    if not is_admin(call.from_user.id):
        return

    uid = call.from_user.id
    chat_id = call.message.chat.id

    # ── 🔙 رجوع للوحة ──
    if call.data == "back_panel":
        clear_state(uid)
        admin_respond(chat_id, uid, panel_text(uid))
        bot.answer_callback_query(call.id)

    # ── 🔧 الصيانة ──
    elif call.data == "toggle_maintenance":
        cur = get_setting("maintenance_mode", False)
        set_setting("maintenance_mode", not cur)
        bot.answer_callback_query(call.id,
            f"🔧 الصيانة: {'مفعل' if not cur else 'مغلق'}")
        admin_respond(chat_id, uid,
            "⚙️ *إعدادات البوت:*\n\nاختر الإعداد لتغييره:",
            settings_markup())

    # ── 📢 فحص الاشتراك ──
    elif call.data == "toggle_subscription":
        cur = get_setting("require_subscription", True)
        set_setting("require_subscription", not cur)
        bot.answer_callback_query(call.id,
            f"📢 الاشتراك: {'مفعل' if not cur else 'مغلق'}")
        admin_respond(chat_id, uid,
            "⚙️ *إعدادات البوت:*\n\nاختر الإعداد لتغييره:",
            settings_markup())

    # ── ✅ تأكيد التصفير ──
    elif call.data == "confirm_reset":
        full_reset()
        bot.answer_callback_query(call.id, "✅ تم التصفير!")
        admin_respond(chat_id, uid,
            "🔄 *تم التصفير الشامل!*\n\n" + panel_text(uid),
            back_markup())

    # ── ❌ إلغاء التصفير ──
    elif call.data == "cancel_reset":
        bot.answer_callback_query(call.id, "❌ تم الإلغاء")
        admin_respond(chat_id, uid, panel_text(uid))

    # ── 🚫 حظر ──
    elif call.data.startswith("ban_"):
        target = int(call.data.replace("ban_", ""))
        ban_user(target)
        bot.answer_callback_query(call.id, f"🚫 تم حظر {target}", show_alert=True)
        # تحديث معلومات المستخدم
        info = search_user(target)
        if info:
            show_user_info(chat_id, uid, target, info)

    # ── ✅ فك حظر ──
    elif call.data.startswith("unban_"):
        target = int(call.data.replace("unban_", ""))
        unban_user(target)
        bot.answer_callback_query(call.id, f"✅ تم فك حظر {target}", show_alert=True)
        info = search_user(target)
        if info:
            show_user_info(chat_id, uid, target, info)


def show_user_info(chat_id, uid, target, info):
    """عرض معلومات المستخدم في رسالة اللوحة"""
    status = "🚫 محظور" if info.get("is_banned") else \
             ("⛔ بلوك" if info.get("is_blocked") else "✅ نشط")
    joined = time.strftime("%Y-%m-%d %H:%M",
        time.localtime(info.get("joined_at", 0)))

    mk = types.InlineKeyboardMarkup()
    if info.get("is_banned"):
        mk.add(types.InlineKeyboardButton("✅ فك الحظر", callback_data=f"unban_{target}"))
    else:
        mk.add(types.InlineKeyboardButton("🚫 حظر", callback_data=f"ban_{target}"))
    mk.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_panel"))

    admin_respond(chat_id, uid,
        f"🔍 *معلومات المستخدم:*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 {info.get('first_name', '?')} | @{info.get('username', 'none')}\n"
        f"🆔 `{target}` | {status}\n"
        f"📅 {joined}\n"
        f"❤️ لايكات: `{info.get('like_count', 0)}` | "
        f"📥 تحميلات: `{info.get('download_count', 0)}` | "
        f"🔗 إحالات: `{info.get('referral_count', 0)}`",
        mk)


# ══════════════════════════════════════════
# 📝 STATE HANDLERS (إدخال نصي)
# ══════════════════════════════════════════

@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and
                   get_state(m.from_user.id) == "custom_post" and
                   m.text not in BTN_LIST,
    content_types=["text"]
)
def handle_custom_post(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    delete_msg(chat_id, message.message_id)

    if message.text.lower() == "reset":
        set_setting("custom_post_text", "")
        clear_state(uid)
        admin_respond(chat_id, uid,
            "✅ *تم إعادة النص للافتراضي!*\n\n" + panel_text(uid),
            back_markup())
    else:
        set_setting("custom_post_text", message.text)
        clear_state(uid)
        admin_respond(chat_id, uid,
            "✅ *تم حفظ النص الجديد!*\n\n" + panel_text(uid),
            back_markup())


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and
                   get_state(m.from_user.id) == "search_user" and
                   m.text not in BTN_LIST,
    content_types=["text"]
)
def handle_search(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    delete_msg(chat_id, message.message_id)
    clear_state(uid)

    try:
        target = int(message.text.strip())
    except:
        admin_respond(chat_id, uid,
            "❌ *أرسل رقم ID صحيح!*", back_markup())
        return

    info = search_user(target)
    if not info:
        admin_respond(chat_id, uid,
            f"❌ المستخدم `{target}` غير موجود.", back_markup())
        return

    show_user_info(chat_id, uid, target, info)


@bot.message_handler(
    func=lambda m: is_admin(m.from_user.id) and
                   get_state(m.from_user.id) == "ban_user" and
                   m.text not in BTN_LIST,
    content_types=["text"]
)
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
            admin_respond(chat_id, uid,
                f"✅ *تم فك حظر* `{target}`\n\n" + panel_text(uid),
                back_markup())
        else:
            target = int(text)
            if target in ADMIN_IDS:
                admin_respond(chat_id, uid,
                    "❌ لا يمكن حظر أدمن!", back_markup())
                return
            ban_user(target)
            admin_respond(chat_id, uid,
                f"🚫 *تم حظر* `{target}`\n\n" + panel_text(uid),
                back_markup())
    except:
        admin_respond(chat_id, uid,
            "❌ *صيغة خاطئة!*\nاستخدم: `ID` أو `unban ID`",
            back_markup())


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
    chat_id = message.chat.id
    clear_state(uid)

    users = get_all_users()
    if not users:
        delete_msg(chat_id, message.message_id)
        admin_respond(chat_id, uid,
            "⚠️ لا يوجد مستخدمين!", back_markup())
        return

    total = len(users)
    admin_respond(chat_id, uid,
        f"📣 *جاري الإرسال...*\n"
        f"👥 الهدف: `{total}`\n⏳ 0%")

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
            else:
                fail += 1
        except:
            fail += 1

        if i % 25 == 0 or i == total:
            pct = int(i/total*100)
            bar = "█"*(pct//5) + "░"*(20-pct//5)
            admin_respond(chat_id, uid,
                f"📣 *جاري الإرسال...*\n"
                f"[{bar}] {pct}%\n"
                f"⏳ `{i}/{total}`\n"
                f"✅ {ok} | 🚫 {block} | ❌ {fail}")

    elapsed = int(time.time() - t0)

    # حذف رسالة البث بعد الانتهاء
    delete_msg(chat_id, message.message_id)

    admin_respond(chat_id, uid,
        f"📣 *تم الإرسال!*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ نجح: `{ok}`\n"
        f"🚫 بلوك: `{block}`\n"
        f"❌ فشل: `{fail}`\n"
        f"⏱️ الوقت: `{elapsed}s`",
        back_markup())


# ══════════════════════════════════════════
# 📂 FILE UPLOAD
# ══════════════════════════════════════════

@bot.message_handler(content_types=["document"])
def handle_doc(message):
    if not is_admin(message.from_user.id):
        return

    uid = message.from_user.id
    chat_id = message.chat.id

    if get_state(uid) != "uploading":
        delete_msg(chat_id, message.message_id)
        admin_respond(chat_id, uid,
            "⚠️ اضغط 📤 أولاً لتفعيل وضع الرفع.",
            back_markup())
        return

    fname = message.document.file_name or "file"
    add_config(message.document.file_id, fname)

    # حذف رسالة الملف
    delete_msg(chat_id, message.message_id)

    cnt = get_configs_count()
    admin_respond(chat_id, uid,
        f"📂 *وضع الرفع*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ آخر ملف: `{fname}`\n"
        f"📊 الإجمالي: `{cnt}` ملف\n\n"
        "📎 أرسل المزيد أو اضغط ✅ إنهاء",
        back_markup())


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

    if is_admin(uid):
        try:
            smart_send(uid, mid)
            bot.answer_callback_query(call.id, "👑 Admin")
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ {str(e)[:80]}", show_alert=True)
        return

    if get_setting("require_subscription", True):
        if not check_subscription(uid):
            bot.answer_callback_query(call.id,
                "⚠️ اشترك بالقناة أولاً!", show_alert=True)
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
            bot.answer_callback_query(call.id,
                "❌ فعّل البوت أولاً! 🤖", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)
    except Exception as e:
        print(f"Delivery Error: {e}")
        bot.answer_callback_query(call.id, "❌ خطأ", show_alert=True)


def smart_send(user_id, post_id=None):
    """حذف ذكي + إرسال كألبوم"""
    old = get_message_history(user_id)
    for mid in old:
        try:
            bot.delete_message(user_id, mid)
        except:
            pass
    clear_message_history(user_id)

    configs = get_all_configs()
    if not configs:
        m = bot.send_message(user_id, "⚠️ لا توجد ملفات حالياً.")
        save_message_history(user_id, [m.message_id])
        return

    ids = []

    if len(configs) == 1:
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
        chunks = [configs[i:i+10] for i in range(0, len(configs), 10)]
        for chunk_idx, chunk in enumerate(chunks):
            media = []
            for i, cfg in enumerate(chunk):
                file_num = chunk_idx * 10 + i + 1
                caption = f"📄 {file_num}/{len(configs)}"
                if cfg.get("name"):
                    caption += f" • {cfg['name']}"
                media.append(InputMediaDocument(
                    media=cfg["file_id"], caption=caption))

            try:
                msgs = bot.send_media_group(user_id, media)
                ids.extend([m.message_id for m in msgs])
            except Exception as e:
                print(f"Album error: {e}")
                for cfg in chunk:
                    try:
                        d = bot.send_document(user_id, cfg["file_id"])
                        ids.append(d.message_id)
                    except:
                        pass

    save_message_history(user_id, ids)
    record_download(user_id, post_id)


# ══════════════════════════════════════════
# 🌐 FLASK
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
                print(f"⏳ 409 ({attempt}) - Wait {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(3)
        except:
            time.sleep(3)
    return False


if __name__ == "__main__":
    print("=" * 45)
    print("  🤖 VPN Bot V13 - Clean UI")
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

