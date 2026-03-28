import telebot
from telebot import types
from telebot.types import InputMediaDocument
from flask import Flask
from threading import Thread
import os
import time
import traceback
import unicodedata  
import logging # أضفنا مكتبة التسجيل لكتم إزعاج سيرفر الويب

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
# ⚙️ CONFIGURATION (إعدادات البيئة للقناتين والأدمنين)
# ══════════════════════════════════════════

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN")

# 🛑 إعدادات المدراء (2 أدمن)
ADMIN_ID_1 = os.environ.get("ADMIN_ID_1", "7846022798")
ADMIN_ID_2 = os.environ.get("ADMIN_ID_2", "")

ADMIN_IDS = set()
for aid in [ADMIN_ID_1, ADMIN_ID_2]:
    if aid and str(aid).strip():
        try: ADMIN_IDS.add(int(str(aid).strip()))
        except: pass

# 🛑 إعدادات القناة الأولى
CHANNEL_ID_1 = os.environ.get("CHANNEL_ID_1", "-1003858414969")
CHANNEL_USER_1 = os.environ.get("CHANNEL_USER_1", "@L_XT_IX_OG")
CHANNEL_URL_1 = os.environ.get("CHANNEL_URL_1", "https://t.me/L_XT_IX_OG")
CHANNEL_NAME_1 = os.environ.get("CHANNEL_NAME_1", "LX TIX")

# 🛑 إعدادات القناة الثانية
CHANNEL_ID_2 = os.environ.get("CHANNEL_ID_2", "-100123456789") 
CHANNEL_USER_2 = os.environ.get("CHANNEL_USER_2", "@O_C_X7")
CHANNEL_URL_2 = os.environ.get("CHANNEL_URL_2", "https://t.me/O_C_X7")
CHANNEL_NAME_2 = os.environ.get("CHANNEL_NAME_2", "OCX")

MANDATORY_CHANNELS = []
if CHANNEL_ID_1 and str(CHANNEL_ID_1).strip():
    MANDATORY_CHANNELS.append({"id": CHANNEL_ID_1, "username": CHANNEL_USER_1, "url": CHANNEL_URL_1, "name": CHANNEL_NAME_1})
if CHANNEL_ID_2 and str(CHANNEL_ID_2).strip():
    MANDATORY_CHANNELS.append({"id": CHANNEL_ID_2, "username": CHANNEL_USER_2, "url": CHANNEL_URL_2, "name": CHANNEL_NAME_2})

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
BOT_USERNAME = None

admin_states = {}
admin_panel_msg = {}
cooldowns = {}
COOLDOWN_SEC = 3
last_cleanup = time.time()

# 🛑 خريطة تتبع البوستات النشطة لفصل القنوات وإحصائياتها عن بعضها بدقة
ACTIVE_POSTS_MAP = {}


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

def check_cooldown(uid, action="general"):
    now = time.time()
    key = f"{uid}_{action}"
    if now - cooldowns.get(key, 0) < COOLDOWN_SEC:
        return False
    cooldowns[key] = now
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

def send_temp_msg(chat_id, text, delay=3):
    try:
        msg = bot.send_message(chat_id, text, parse_mode="Markdown")
        def delete_later():
            time.sleep(delay)
            try: bot.delete_message(chat_id, msg.message_id)
            except: pass
        Thread(target=delete_later).start()
    except:
        pass

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

def get_missing_channels(user_id):
    if not get_setting("require_subscription", True):
        return []
    missing = []
    for ch in MANDATORY_CHANNELS:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            if member.status in ["left", "kicked"]:
                missing.append(ch)
        except Exception:
            missing.append(ch)
    return missing

def check_maintenance(call_or_msg, is_callback=False):
    if get_setting("maintenance_mode", False):
        text = "🔧 البوت في وضع الصيانة\nيرجى المحاولة لاحقاً..."
        if is_callback:
            bot.answer_callback_query(call_or_msg.id, text, show_alert=True)
        else:
            send_temp_msg(call_or_msg.chat.id, text, 5)
        return True
    return False

def safe_edit_markup(chat_id, message_id, markup):
    try:
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)
        return True
    except:
        return False

def update_channel_post_markup(msg_id):
    chat_id = ACTIVE_POSTS_MAP.get(msg_id)
    if chat_id:
        safe_edit_markup(chat_id, msg_id, channel_markup(msg_id))
    else:
        for ch in MANDATORY_CHANNELS:
            safe_edit_markup(ch["id"], msg_id, channel_markup(msg_id))


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
    
    bot_user = BOT_USERNAME or "ReactGuardbot"
    receive_btn = types.InlineKeyboardButton(f"📥 استلم ({dl})", callback_data="get_file")
        
    mk.row(
        types.InlineKeyboardButton(f"❤️ تفاعل ({likes})", callback_data="do_like"),
        receive_btn)
    mk.add(types.InlineKeyboardButton(
        "🤖 فعّل البوت أولاً",
        url=f"https://t.me/{bot_user}?start=channel"))
    return mk

def main_admin_markup():
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    mk.row("📤 رفع ملفات", "📤 إضافة ملفات", "🗑️ حذف الملفات")
    mk.row("📢 نشر القناة 1️⃣", "📢 نشر القناة 2️⃣", "📢 نشر بالقناتين 🚀")
    mk.row("📊 الإحصائيات", "👥 المتفاعلين", "🏆 المُحيلين")
    mk.row("✏️ تخصيص البوست", "📣 إذاعة جماعية", "🔄 تصفير شامل")
    mk.row("🔍 بحث مستخدم", "🚫 بان مستخدم", "📋 تصدير")
    mk.row("⚙️ الإعدادات", "✅ إنهاء", "❌ إخفاء")
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

def build_join_keyboard(post_id=None):
    mk = types.InlineKeyboardMarkup(row_width=2)
    # 🛑 إظهار جميع القنوات الإجبارية دائماً وبجوار بعضهما البعض
    buttons = [types.InlineKeyboardButton(ch['name'], url=ch["url"]) for ch in MANDATORY_CHANNELS]
    
    if len(buttons) >= 2:
        mk.row(buttons[0], buttons[1])
    else:
        for btn in buttons:
            mk.add(btn)
            
    cb_data = f"check_sub_{post_id}" if post_id else "check_sub_none"
    mk.add(types.InlineKeyboardButton("✅ تحققت من اشتراكي", callback_data=cb_data))
    return mk

# ══════════════════════════════════════════
# 🚀 START
# ══════════════════════════════════════════

@bot.message_handler(commands=["start"])
def cmd_start(message):
    u = message.from_user
    uid = u.id

    try:
        bot.delete_message(message.chat.id, message.message_id)
    except:
        pass

    if is_banned(uid) and not is_admin(uid):
        send_temp_msg(uid, "🚫 تم حظرك.")
        return

    referrer = None
    get_file_msg_id = None
    args = message.text.split()
    
    if len(args) > 1:
        param = args[1]
        if param.startswith("ref_"):
            try:
                referrer = int(param.replace("ref_", ""))
                if referrer == uid: referrer = None
            except: pass
        elif param.startswith("get_"):
            try:
                get_file_msg_id = int(param.replace("get_", ""))
            except: pass

    is_new = add_user(uid, u.username, u.first_name, referrer)

    if get_file_msg_id:
        
        if ACTIVE_POSTS_MAP and get_file_msg_id not in ACTIVE_POSTS_MAP:
            send_temp_msg(uid, "🚫 هذا المنشور قديم! انتقل للجديد في القناة.", 5)
            return
            
        if not check_cooldown(uid, "get_start"):
            return
            
        if check_maintenance(message, is_callback=False):
            return

        missing = get_missing_channels(uid)
        if missing:
            text = (
                f"👋 أهلاً بك {u.first_name}!\n\n"
                "⚠️ يجب عليك الاشتراك في القنوات التالية أولاً لاستخدام البوت:\n\n"
                "🔔 بعد الاشتراك، اضغط على زر **✅ تحققت من اشتراكي** بالأسفل."
            )
            bot.send_message(uid, text, reply_markup=build_join_keyboard(get_file_msg_id), parse_mode="Markdown")
            if is_new:
                notify_admins(f"👤 *مستخدم جديد!*\n• {dname(u)}\n• ID: `{uid}`\n📊 الإجمالي: `{get_users_count()}`")
            return

        if not has_liked(uid, get_file_msg_id):
            send_temp_msg(uid, "⛔ لا يمكنك استلام الملفات لأنك لم تتفاعل مع المنشور!\n\nارجع للقناة واضغط على زر (❤️ تفاعل) أولاً.", 8)
            return

        wait_msg = bot.send_message(uid, "✅ جاري إرسال الملفات...")
        try:
            result = smart_send(uid, get_file_msg_id)
            if result:
                update_channel_post_markup(get_file_msg_id)
            else:
                send_temp_msg(uid, "⚠️ لا توجد ملفات حالياً!", 4)
        except Exception as e:
            print(f"Delivery Error: {e}")
            send_temp_msg(uid, "❌ حدث خطأ أثناء إرسال الملفات.", 4)
            
        try:
            bot.delete_message(uid, wait_msg.message_id)
        except:
            pass
            
        return

    if is_admin(uid):
        show_panel(message.chat.id, uid)
        return

    missing = get_missing_channels(uid)
    if missing:
        text = (
            f"👋 أهلاً بك {u.first_name}!\n\n"
            "⚠️ يجب عليك الاشتراك في القنوات التالية أولاً لاستخدام البوت:\n\n"
            "🔔 بعد الاشتراك، اضغط على زر **✅ تحققت من اشتراكي** بالأسفل."
        )
        bot.send_message(uid, text, reply_markup=build_join_keyboard(), parse_mode="Markdown")
        if is_new:
            ref_text = f"\n🔗 أحاله: `{referrer}`" if referrer else ""
            if referrer:
                try:
                    bot.send_message(referrer, f"🎉 شخص جديد عبر إحالتك!\n📊 إحالاتك: `{get_referral_count(referrer)}`")
                except: pass
            notify_admins(f"👤 *مستخدم جديد!*\n• {dname(u)}\n• ID: `{uid}`{ref_text}\n📊 الإجمالي: `{get_users_count()}`")
        return

    send_temp_msg(uid, "✅ تم تفعيل البوت، ارجع للقناة واستلم ملفاتك.", 5)

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
    "📤 رفع ملفات", "📤 إضافة ملفات", "🗑️ حذف الملفات",
    "📢 نشر القناة 1️⃣", "📢 نشر القناة 2️⃣", "📢 نشر بالقناتين 🚀",
    "📊 الإحصائيات", "👥 المتفاعلين", "🏆 المُحيلين",
    "✏️ تخصيص البوست", "📣 إذاعة جماعية", "🔄 تصفير شامل",
    "🔍 بحث مستخدم", "🚫 بان مستخدم", "📋 تصدير",
    "⚙️ الإعدادات", "✅ إنهاء", "❌ إخفاء"
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

    elif act == "📢 نشر القناة 1️⃣":
        configs = get_all_configs()
        if not configs:
            admin_respond(chat_id, uid, "⚠️ لا توجد ملفات!", back_markup())
            return
        set_state(uid, "waiting_for_duration_1")
        admin_respond(chat_id, uid, "⏳ *كم مدة الكونفيج للقناة الأولى؟*\n\nأرسل المدة الآن (مثال: `5` أو `4:30` أو `6`):", back_markup())

    elif act == "📢 نشر القناة 2️⃣":
        configs = get_all_configs()
        if not configs:
            admin_respond(chat_id, uid, "⚠️ لا توجد ملفات!", back_markup())
            return
        set_state(uid, "waiting_for_duration_2")
        admin_respond(chat_id, uid, "⏳ *كم مدة الكونفيج للقناة الثانية؟*\n\nأرسل المدة الآن (مثال: `5` أو `4:30` أو `6`):", back_markup())

    elif act == "📢 نشر بالقناتين 🚀":
        configs = get_all_configs()
        if not configs:
            admin_respond(chat_id, uid, "⚠️ لا توجد ملفات!", back_markup())
            return
        set_state(uid, "waiting_for_duration_all")
        admin_respond(chat_id, uid, "⏳ *كم مدة الكونفيج للقناتين؟*\n\nأرسل المدة الآن (مثال: `5` أو `4:30` أو `6`):", back_markup())

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

    elif act == "📋 تصدير":
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

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_sub_"))
def handle_check_sub(call):
    uid = call.from_user.id
    post_id_str = call.data.replace("check_sub_", "")
    
    missing = get_missing_channels(uid)
    if missing:
        try:
            bot.answer_callback_query(call.id, "❌ لم تشترك في جميع القنوات!", show_alert=True)
        except: pass
    else:
        try:
            bot.delete_message(uid, call.message.message_id)
        except: pass
        
        try: bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح!", show_alert=False)
        except: pass
        
        if post_id_str != "none":
            try:
                post_id = int(post_id_str)
            except:
                return

            if ACTIVE_POSTS_MAP and post_id not in ACTIVE_POSTS_MAP:
                send_temp_msg(uid, "🚫 هذا المنشور قديم! انتقل للجديد في القناة.", 5)
                return

            if not has_liked(uid, post_id):
                send_temp_msg(uid, "⛔ لا يمكنك استلام الملفات لأنك لم تتفاعل مع المنشور!\n\nارجع للقناة واضغط على زر (❤️ تفاعل) أولاً.", 8)
                return
            
            wait_msg = bot.send_message(uid, "✅ جاري إرسال الملفات...")
            try:
                result = smart_send(uid, post_id)
                if result:
                    update_channel_post_markup(post_id)
                else:
                    send_temp_msg(uid, "⚠️ لا توجد ملفات حالياً!", 4)
            except Exception as e:
                send_temp_msg(uid, "❌ حدث خطأ أثناء إرسال الملفات.", 4)
                
            try:
                bot.delete_message(uid, wait_msg.message_id)
            except:
                pass
        else:
            send_temp_msg(uid, "✅ تم تفعيل البوت، ارجع للقناة واستلم ملفاتك.", 5)


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
    func=lambda m: is_admin(m.from_user.id) and str(get_state(m.from_user.id)).startswith("waiting_for_duration"),
    content_types=["text"])
def handle_duration_input(message):
    uid = message.from_user.id
    chat_id = message.chat.id
    state = get_state(uid)
    delete_msg(chat_id, message.message_id)
    
    duration = message.text.strip()
    set_setting("current_config_duration", duration)
    clear_state(uid)

    configs = get_all_configs()
    custom = get_setting("custom_post_text", "")
    text = custom if custom else (
        "⚡️ *تم تجديد الكونفيجات!*\n\n"
        f"📂 عدد الملفات: `{len(configs)}`\n"
        "🚀 سرعة عالية | ⏳ محدد المدة\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📌 *طريقة الاستلام:*\n\n"
        "1️⃣ فعّل البوت بالضغط على 🤖\n"
        "2️⃣ ادعمنا بضغطة ❤️\n"
        "3️⃣ اضغط 📥 لاستلام الملفات\n"
        "━━━━━━━━━━━━━━━\n"
        "⚠️ سارع قبل انتهاء الصلاحية!")
        
    success_msg = f"✅ *تم النشر بنجاح!*\n(المدة المضبوطة: `{duration}` ساعات)\n\n"
    
    targets = []
    if state == "waiting_for_duration_1":
        targets = [MANDATORY_CHANNELS[0]]
    elif state == "waiting_for_duration_2":
        targets = [MANDATORY_CHANNELS[1]]
    else:
        targets = MANDATORY_CHANNELS
    
    for ch in targets:
        try:
            sent = bot.send_message(ch["id"], text, parse_mode="Markdown")
            bot.edit_message_reply_markup(ch["id"], sent.message_id, reply_markup=channel_markup(sent.message_id))
            add_post(sent.message_id, text)
            
            old_msg_ids = [k for k, v in ACTIVE_POSTS_MAP.items() if v == ch["id"]]
            for old_id in old_msg_ids:
                del ACTIVE_POSTS_MAP[old_id]
                
            ACTIVE_POSTS_MAP[sent.message_id] = ch["id"]
            success_msg += f"📢 {ch['name']}: نشر تم (ID: `{sent.message_id}`)\n"
        except Exception as e:
            success_msg += f"❌ خطأ في {ch['name']}: `{e}`\n"

    admin_respond(chat_id, uid, success_msg + f"\n{panel_text(uid)}", back_markup())


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

        user_info = search_user(uid)
        if not user_info:
            bot.answer_callback_query(call.id, "🤖 يرجى تفعيل البوت أولاً بالضغط على زر (فعّل البوت أولاً) بالأسفل 👇", show_alert=True)
            return

        missing = get_missing_channels(uid)
        if missing:
            bot.answer_callback_query(call.id, "🤖 يرجى تفعيل البوت والاشتراك في القنوات أولاً بالضغط على زر (فعّل البوت أولاً) بالأسفل 👇", show_alert=True)
            return

        if ACTIVE_POSTS_MAP and mid not in ACTIVE_POSTS_MAP:
            bot.answer_callback_query(call.id, "🚫 هذا المنشور قديم! انتقل للجديد.", show_alert=True)
            return

        cleanup_memory()
        if not check_cooldown(uid, "like"):
            bot.answer_callback_query(call.id)
            return
        if check_maintenance(call, True): return
        if is_banned(uid):
            bot.answer_callback_query(call.id, "🚫 محظور!", show_alert=True)
            return
            
        is_new = add_like(uid, mid, dname(call.from_user))
        if not is_new:
            bot.answer_callback_query(call.id, "⚠️ سبق أن دعمت! ❤️", show_alert=True)
            return
            
        update_channel_post_markup(mid)
        bot.answer_callback_query(call.id, "✅ شكراً! ❤️")
    except Exception as e:
        print(f"Like Error: {e}")
        try: bot.answer_callback_query(call.id, "❌ خطأ")
        except: pass


# ══════════════════════════════════════════
# 📥 DELIVERY (ألبوم + حذف ذكي + عداد حي)
# ══════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: c.data == "get_file")
def handle_delivery(call):
    uid = call.from_user.id
    mid = call.message.message_id

    user_info = search_user(uid)
    if not user_info:
        bot.answer_callback_query(call.id, "🤖 يرجى تفعيل البوت أولاً بالضغط على زر (فعّل البوت أولاً) بالأسفل 👇", show_alert=True)
        return

    if ACTIVE_POSTS_MAP and mid not in ACTIVE_POSTS_MAP:
        bot.answer_callback_query(call.id, "🚫 هذا المنشور قديم! انتقل للجديد.", show_alert=True)
        return

    if not check_cooldown(uid, "get_cb"):
        bot.answer_callback_query(call.id)
        return
    if check_maintenance(call, True): return
    if is_banned(uid) and not is_admin(uid):
        bot.answer_callback_query(call.id, "🚫 محظور!", show_alert=True)
        return

    missing = get_missing_channels(uid)
    if missing:
        bot_user = BOT_USERNAME or "ReactGuardbot"
        redirect_url = f"https://t.me/{bot_user}?start=get_{mid}"
        try:
            bot.answer_callback_query(call.id, url=redirect_url)
        except:
            bot.answer_callback_query(call.id, "⚠️ يرجى تفعيل البوت والاشتراك في القنوات أولاً!", show_alert=True)
        return

    if not has_liked(uid, mid):
        bot.answer_callback_query(call.id, "⛔ لا يمكنك استلام الملفات لأنك لم تتفاعل مع المنشور!\n\nارجع للقناة واضغط على زر (❤️ تفاعل) أولاً.", show_alert=True)
        return

    bot_user = BOT_USERNAME or "ReactGuardbot"
    redirect_url = f"https://t.me/{bot_user}?start=get_{mid}"
    
    try:
        bot.answer_callback_query(call.id, url=redirect_url)
    except Exception as e:
        print(f"Redirect Error: {e}")
        bot.answer_callback_query(call.id, "✅ تم تأكيد تفاعلك! اذهب للبوت لتجد ملفاتك.", show_alert=True)


def smart_send(user_id, post_id=None):
    """حذف ذكي + إرسال في مجموعات (ألبومات) مجمعة حسب الامتداد"""

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
        return False

    ids = []
    
    current_duration = get_setting("current_config_duration", "5")
    
    grouped_configs = {}
    for cfg in configs:
        file_name = cfg.get("name", "") or ""
        name_lower = unicodedata.normalize('NFKC', file_name).lower()
        cfg["norm_name"] = name_lower 
        
        ext = name_lower.split('.')[-1] if '.' in name_lower else "other"
        if ext not in grouped_configs:
            grouped_configs[ext] = []
        grouped_configs[ext].append(cfg)

    # 3️⃣ إرسال الملفات المجمعة
    for ext, cfgs in grouped_configs.items():
        media_group = []
        
        for cfg in cfgs:
            name_lower = cfg["norm_name"]
            caption_html = ""
            
            if "yt" in name_lower or "يوتيوب" in name_lower:
                caption_html = "<blockquote>كونفيج كسر يوتيوب</blockquote>"
            else:
                caption_html = "<blockquote>كونفيج بدون عروض اوريدو + جيزي</blockquote>\n"
                
                if name_lower.endswith(".dark"):
                    caption_html += "<blockquote>خاص بتطبيق DARK TUNNEL</blockquote>\n"
                elif name_lower.endswith(".ehi"):
                    caption_html += "<blockquote>خاص بتطبيق HTTP INJECTOR</blockquote>\n"
                
                caption_html += f"<blockquote>المدة: {current_duration} ساعات</blockquote>"

            media_group.append(InputMediaDocument(
                media=cfg["file_id"],
                caption=caption_html,
                parse_mode="HTML"
            ))
        
        if len(media_group) == 1:
            try:
                d = bot.send_document(
                    user_id,
                    media_group[0].media,
                    caption=media_group[0].caption,
                    parse_mode="HTML"
                )
                ids.append(d.message_id)
                time.sleep(0.3)
            except Exception as e:
                print(f"Single file error: {e}")
        elif len(media_group) > 1:
            chunks = [media_group[i:i+10] for i in range(0, len(media_group), 10)]
            for chunk in chunks:
                try:
                    msgs = bot.send_media_group(user_id, chunk)
                    ids.extend([m.message_id for m in msgs])
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Media group error: {e}")
                    for item in chunk:
                        try:
                            d = bot.send_document(
                                user_id,
                                item.media,
                                caption=item.caption,
                                parse_mode="HTML"
                            )
                            ids.append(d.message_id)
                            time.sleep(0.3)
                        except: pass

    # 4️⃣ حفظ
    if ids:
        save_message_history(user_id, ids)
        record_download(user_id, post_id)
        return True
    return False


# ══════════════════════════════════════════
# 🌐 FLASK & SERVER SETUP
# ══════════════════════════════════════════

# 🛑 إخفاء سجلات Flask المزعجة للتركيز على أخطاء البوت فقط
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

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
# 🚀 MAIN
# ══════════════════════════════════════════

def force_clear_session():
    print("🧹 Step 1: Remove webhook...")
    for i in range(3):
        try:
            bot.remove_webhook()
            break
        except:
            time.sleep(2)

    print("🧹 Step 2: Wait for old instance...")
    time.sleep(15)

    print("🧹 Step 3: Clear updates...")
    for attempt in range(10):
        try:
            bot.get_updates(offset=-1, timeout=1)
            print(f"   ✅ Cleared! (attempt {attempt+1})")
            return True
        except telebot.apihelper.ApiTelegramException as e:
            if "409" in str(e):
                print(f"   ⏳ 409 (attempt {attempt+1}) - wait 5s...")
                time.sleep(5)
            else:
                time.sleep(3)
        except:
            time.sleep(3)
    return False


if __name__ == "__main__":
    print("=" * 45)
    print("  🤖 VPN Bot V13 Final (Dual Channels & Watchdog)")
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
    print(f"📢 Channels: {[c['username'] for c in MANDATORY_CHANNELS]}")

    print("🧹 Clearing sessions...")
    force_clear_session()

    print("🌐 Web server...")
    keep_alive()

    print("🚀 Started!\n")

    consecutive_409 = 0

    # 🛑 تم تعديل حلقة التشغيل لمعالجة تداخل Render (409) بدلاً من الانهيار
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
                print(f"⚠️ 409 #{consecutive_409} (Multiple instances overlap during deployment) - wait {wait}s...")
                if consecutive_409 >= 30:
                    print("❌ Too many 409! Exiting to trigger restart...")
                    os._exit(1)
                time.sleep(wait)
            else:
                print(f"❌ API Error: {e}")
                time.sleep(5)
                consecutive_409 = 0
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            break
        except Exception as e:
            consecutive_409 = 0
            print(f"❌ FATAL ERROR: {e}")
            traceback.print_exc()
            print("🔄 Force restarting the application via Render...")
            time.sleep(2)
            os._exit(1)
        else:
            print("⚠️ Polling stopped unexpectedly. Force restarting...")
            os._exit(1)
