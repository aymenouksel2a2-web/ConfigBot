import time
from pymongo import MongoClient
import os

# ══════════════════════════════════════════
# 🗄️ MongoDB Atlas Connection
# ══════════════════════════════════════════

MONGO_URI = os.environ.get("MONGO_URI", "YOUR_MONGODB_URI_HERE")

client = MongoClient(MONGO_URI)
db = client["vpn_bot"]  # اسم قاعدة البيانات

# ─── Collections (جداول) ───
users_col    = db["users"]
likes_col    = db["likes"]
configs_col  = db["configs"]
history_col  = db["message_history"]
posts_col    = db["posts"]


def init_db():
    """إنشاء الفهارس لتسريع البحث"""
    try:
        users_col.create_index("user_id", unique=True)
        likes_col.create_index([("user_id", 1), ("message_id", 1)], unique=True)
        configs_col.create_index("order")
        history_col.create_index("user_id")
        posts_col.create_index("message_id", unique=True)
        print("✅ MongoDB Connected & Indexes Created!")
    except Exception as e:
        print(f"❌ MongoDB Init Error: {e}")


# ══════════════════════════════════════════
# 👥 USERS (المستخدمين)
# ══════════════════════════════════════════

def add_user(user_id, username=None, first_name=None):
    """إضافة مستخدم جديد أو تحديث بياناته"""
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "is_blocked": False
        },
        "$setOnInsert": {
            "joined_at": time.time()
        }},
        upsert=True
    )


def get_all_users():
    """جلب كل المستخدمين غير المحظورين"""
    docs = users_col.find(
        {"is_blocked": {"$ne": True}},
        {"user_id": 1}
    )
    return [doc["user_id"] for doc in docs]


def get_users_count():
    """عدد المستخدمين الكلي"""
    return users_col.count_documents({})


def mark_user_blocked(user_id):
    """تسجيل أن المستخدم حظر البوت"""
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"is_blocked": True}}
    )


# ══════════════════════════════════════════
# ❤️ LIKES (التفاعلات)
# ══════════════════════════════════════════

def add_like(user_id, message_id, username):
    """تسجيل لايك - يرجع True إذا جديد"""
    try:
        likes_col.insert_one({
            "user_id": user_id,
            "message_id": message_id,
            "username": username,
            "liked_at": time.time()
        })
        return True
    except Exception:
        # duplicate = سبق أن عمل لايك
        return False


def has_liked(user_id, message_id):
    """هل المستخدم عمل لايك على هذا البوست؟"""
    doc = likes_col.find_one({
        "user_id": user_id,
        "message_id": message_id
    })
    return doc is not None


def get_likes_count(message_id):
    """عدد اللايكات على بوست معين"""
    if message_id is None:
        return 0
    return likes_col.count_documents({"message_id": message_id})


def get_all_likers():
    """جلب كل المتفاعلين بدون تكرار"""
    pipeline = [
        {"$group": {
            "_id": "$user_id",
            "name": {"$first": "$username"}
        }}
    ]
    results = likes_col.aggregate(pipeline)
    return [{"id": r["_id"], "name": r["name"]} for r in results]


def clear_likes():
    """حذف كل اللايكات"""
    likes_col.delete_many({})


# ══════════════════════════════════════════
# 📂 CONFIGS (الملفات)
# ══════════════════════════════════════════

def add_config(file_id):
    """إضافة ملف كونفيج"""
    count = configs_col.count_documents({})
    configs_col.insert_one({
        "file_id": file_id,
        "order": count + 1,
        "added_at": time.time()
    })


def get_all_configs():
    """جلب كل الملفات مرتبة"""
    docs = configs_col.find({}).sort("order", 1)
    return [doc["file_id"] for doc in docs]


def get_configs_count():
    """عدد الملفات"""
    return configs_col.count_documents({})


def clear_configs():
    """حذف كل الملفات"""
    configs_col.delete_many({})


# ══════════════════════════════════════════
# 📨 MESSAGE HISTORY (سجل الرسائل للحذف الذكي)
# ══════════════════════════════════════════

def save_message_history(user_id, msg_ids):
    """حفظ أرقام الرسائل المرسلة لمستخدم"""
    # حذف القديم
    history_col.delete_many({"user_id": user_id})
    # حفظ الجديد
    if msg_ids:
        docs = [
            {"user_id": user_id, "msg_id": mid, "sent_at": time.time()}
            for mid in msg_ids
        ]
        history_col.insert_many(docs)


def get_message_history(user_id):
    """جلب أرقام الرسائل المحفوظة لمستخدم"""
    docs = history_col.find({"user_id": user_id})
    return [doc["msg_id"] for doc in docs]


def clear_message_history(user_id):
    """حذف سجل رسائل مستخدم"""
    history_col.delete_many({"user_id": user_id})


# ══════════════════════════════════════════
# 📢 POSTS (البوستات)
# ══════════════════════════════════════════

def add_post(message_id):
    """تسجيل بوست منشور"""
    try:
        posts_col.insert_one({
            "message_id": message_id,
            "posted_at": time.time()
        })
    except Exception:
        pass


# ══════════════════════════════════════════
# 🔄 RESET & STATS
# ══════════════════════════════════════════

def full_reset():
    """إعادة تعيين كل البيانات ماعدا المستخدمين"""
    likes_col.delete_many({})
    configs_col.delete_many({})
    history_col.delete_many({})
    posts_col.delete_many({})


def get_stats():
    """إحصائيات شاملة"""
    total = users_col.count_documents({})
    blocked = users_col.count_documents({"is_blocked": True})
    active = total - blocked
    configs = configs_col.count_documents({})

    # عدد المتفاعلين الفريدين
    pipeline = [{"$group": {"_id": "$user_id"}}]
    unique_likers = len(list(likes_col.aggregate(pipeline)))

    return {
        "total_users": total,
        "active_users": active,
        "blocked_users": blocked,
        "configs": configs,
        "unique_likers": unique_likers
    }
