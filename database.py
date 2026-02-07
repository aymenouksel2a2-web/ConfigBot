import time
import os
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "YOUR_MONGODB_URI")

client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client["vpn_bot_v13"]

users_col     = db["users"]
likes_col     = db["likes"]
configs_col   = db["configs"]
history_col   = db["message_history"]
posts_col     = db["posts"]
settings_col  = db["settings"]
referrals_col = db["referrals"]
downloads_col = db["downloads"]


def init_db():
    try:
        users_col.create_index("user_id", unique=True)
        likes_col.create_index([("user_id", 1), ("message_id", 1)], unique=True)
        configs_col.create_index("order")
        history_col.create_index("user_id")
        posts_col.create_index("message_id", unique=True)
        referrals_col.create_index("referred_id", unique=True)
        referrals_col.create_index("referrer_id")
        downloads_col.create_index([("user_id", 1), ("post_id", 1)])

        defaults = {
            "maintenance_mode": False,
            "require_subscription": True,
            "custom_post_text": "",
            "total_downloads": 0
        }
        for key, val in defaults.items():
            settings_col.update_one(
                {"key": key},
                {"$setOnInsert": {"key": key, "value": val}},
                upsert=True
            )
        print("✅ MongoDB Connected!")
        return True
    except Exception as e:
        print(f"❌ MongoDB Error: {e}")
        return False


def get_setting(key, default=None):
    doc = settings_col.find_one({"key": key})
    return doc["value"] if doc else default

def set_setting(key, value):
    settings_col.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value}},
        upsert=True
    )


def add_user(user_id, username=None, first_name=None, referrer_id=None):
    result = users_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "username": username,
                "first_name": first_name,
                "last_active": time.time()
            },
            "$setOnInsert": {
                "user_id": user_id,
                "joined_at": time.time(),
                "is_blocked": False,
                "is_banned": False,
                "download_count": 0,
                "referrer": referrer_id
            }
        },
        upsert=True
    )
    is_new = result.upserted_id is not None
    if is_new and referrer_id:
        try:
            referrals_col.insert_one({
                "referrer_id": referrer_id,
                "referred_id": user_id,
                "referred_name": username or first_name,
                "at": time.time()
            })
        except:
            pass
    return is_new

def get_all_users():
    docs = users_col.find(
        {"is_blocked": {"$ne": True}, "is_banned": {"$ne": True}},
        {"user_id": 1}
    )
    return [d["user_id"] for d in docs]

def get_users_count():
    return users_col.count_documents({})

def get_active_count():
    return users_col.count_documents({
        "is_blocked": {"$ne": True},
        "is_banned": {"$ne": True}
    })

def mark_user_blocked(user_id):
    users_col.update_one({"user_id": user_id}, {"$set": {"is_blocked": True}})

def ban_user(user_id):
    users_col.update_one({"user_id": user_id}, {"$set": {"is_banned": True}}, upsert=True)

def unban_user(user_id):
    users_col.update_one({"user_id": user_id}, {"$set": {"is_banned": False}})

def is_banned(user_id):
    doc = users_col.find_one({"user_id": user_id})
    return doc.get("is_banned", False) if doc else False

def search_user(user_id):
    doc = users_col.find_one({"user_id": user_id})
    if not doc:
        return None
    doc["referral_count"] = referrals_col.count_documents({"referrer_id": user_id})
    doc["like_count"] = likes_col.count_documents({"user_id": user_id})
    doc["download_count"] = downloads_col.count_documents({"user_id": user_id})
    return doc

def export_users_list():
    docs = users_col.find({}).sort("joined_at", -1)
    lines = []
    for d in docs:
        status = "🚫" if d.get("is_banned") else ("⛔" if d.get("is_blocked") else "✅")
        name = d.get("username", d.get("first_name", "?"))
        lines.append(f"{status} {d['user_id']} | {name}")
    return lines


def get_referral_count(user_id):
    return referrals_col.count_documents({"referrer_id": user_id})

def get_referral_leaderboard(limit=10):
    pipeline = [
        {"$group": {"_id": "$referrer_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ]
    results = list(referrals_col.aggregate(pipeline))
    for r in results:
        user = users_col.find_one({"user_id": r["_id"]})
        r["name"] = user.get("username") or user.get("first_name", "?") if user else "?"
    return results


def add_like(user_id, message_id, username):
    try:
        likes_col.insert_one({
            "user_id": user_id,
            "message_id": message_id,
            "username": username,
            "liked_at": time.time()
        })
        return True
    except:
        return False

def has_liked(user_id, message_id):
    return likes_col.find_one({"user_id": user_id, "message_id": message_id}) is not None

def get_likes_count(message_id):
    if message_id is None:
        return 0
    return likes_col.count_documents({"message_id": message_id})

def get_all_likers():
    pipeline = [{"$group": {"_id": "$user_id", "name": {"$first": "$username"}}}]
    return [{"id": r["_id"], "name": r["name"]} for r in likes_col.aggregate(pipeline)]

def clear_likes():
    likes_col.delete_many({})


def add_config(file_id, file_name=None):
    count = configs_col.count_documents({})
    configs_col.insert_one({
        "file_id": file_id,
        "file_name": file_name,
        "order": count + 1,
        "added_at": time.time()
    })

def get_all_configs():
    docs = configs_col.find({}).sort("order", 1)
    return [{"file_id": d["file_id"], "name": d.get("file_name")} for d in docs]

def get_configs_count():
    return configs_col.count_documents({})

def clear_configs():
    configs_col.delete_many({})


def record_download(user_id, post_id=None):
    downloads_col.insert_one({"user_id": user_id, "post_id": post_id, "at": time.time()})
    settings_col.update_one({"key": "total_downloads"}, {"$inc": {"value": 1}}, upsert=True)
    users_col.update_one({"user_id": user_id}, {"$inc": {"download_count": 1}})

def get_total_downloads():
    return get_setting("total_downloads", 0)

def get_post_downloads(post_id):
    if post_id is None:
        return 0
    return downloads_col.count_documents({"post_id": post_id})


def save_message_history(user_id, msg_ids):
    history_col.delete_many({"user_id": user_id})
    if msg_ids:
        history_col.insert_many([
            {"user_id": user_id, "msg_id": mid, "sent_at": time.time()}
            for mid in msg_ids
        ])

def get_message_history(user_id):
    docs = history_col.find({"user_id": user_id})
    return [d["msg_id"] for d in docs]

def clear_message_history(user_id):
    history_col.delete_many({"user_id": user_id})


def add_post(message_id, text=None):
    try:
        posts_col.insert_one({
            "message_id": message_id,
            "text": text,
            "posted_at": time.time()
        })
    except:
        pass

def get_last_post():
    return posts_col.find_one(sort=[("posted_at", -1)])


def full_reset():
    likes_col.delete_many({})
    configs_col.delete_many({})
    posts_col.delete_many({})
    downloads_col.delete_many({})
    set_setting("total_downloads", 0)


def get_stats():
    total   = users_col.count_documents({})
    blocked = users_col.count_documents({"is_blocked": True})
    banned  = users_col.count_documents({"is_banned": True})
    active  = max(0, total - blocked - banned)
    configs = configs_col.count_documents({})
    total_dl = get_setting("total_downloads", 0)
    total_refs = referrals_col.count_documents({})

    pipeline = [{"$group": {"_id": "$user_id"}}]
    unique_likers = len(list(likes_col.aggregate(pipeline)))

    day_ago = time.time() - 86400
    new_today = users_col.count_documents({"joined_at": {"$gte": day_ago}})
    dl_today = downloads_col.count_documents({"at": {"$gte": day_ago}})

    return {
        "total_users": total,
        "active_users": active,
        "blocked_users": blocked,
        "banned_users": banned,
        "configs": configs,
        "unique_likers": unique_likers,
        "total_downloads": total_dl,
        "total_referrals": total_refs,
        "new_today": new_today,
        "dl_today": dl_today
    }
