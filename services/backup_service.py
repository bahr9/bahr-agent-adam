# -*- coding: utf-8 -*-
"""
💾 ADAM Backup Service
========================
يعمل backup لكل Firestore collections
ويرفعها على GitHub Private Repo كـ JSON files
ويبعت Telegram notification بالنتيجة

Collections المحمية:
    - user_memory
    - memory_notes
    - conversations
    - adam_human_model
    - bahr_graph_nodes
"""

import os
import json
import base64
import requests
from utils.logger import logger
from utils.time_utils import now_cairo

# ============================================================
# Config من Environment Variables
# ============================================================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO  = os.getenv("GITHUB_REPO")   # bahr9/adam-backups
GITHUB_API   = "https://api.github.com"

# أسماء الـ Collections المطلوب حمايتها
COLLECTIONS = [
    "user_memory",
    "memory_notes",
    "conversations",
    "adam_human_model",
    "bahr_graph_nodes"
]


# ============================================================
# Firestore Export
# ============================================================

def export_collection(collection_name: str) -> list:
    """
    يصدّر collection كاملة من Firestore كـ list of dicts.
    بيستخدم firestore_db الـ global من firebase_service.
    """
    try:
        from services.firebase_service import firestore_db

        if firestore_db is None:
            logger.error(f"❌ Firestore مش متصل — تعذّر تصدير {collection_name}")
            return []

        docs = firestore_db.collection(collection_name).stream()
        data = []
        for doc in docs:
            item = doc.to_dict()
            item["_doc_id"] = doc.id
            data.append(item)

        logger.info(f"📦 Exported {collection_name}: {len(data)} docs")
        return data

    except Exception as e:
        logger.error(f"❌ Export failed ({collection_name}): {e}")
        return []


# ============================================================
# GitHub Upload
# ============================================================

def upload_to_github(filename: str, content: str) -> bool:
    """
    يرفع ملف على GitHub.
    - لو الملف موجود: يحدّثه (PUT مع SHA)
    - لو مش موجود: ينشئه (PUT بدون SHA)
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logger.error("❌ GITHUB_TOKEN أو GITHUB_REPO مش موجودين في Environment")
        return False

    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{filename}"

        # هل الملف موجود؟ (عشان نجيب الـ SHA)
        sha = None
        check = requests.get(url, headers=headers, timeout=15)
        if check.status_code == 200:
            sha = check.json().get("sha")

        # تحويل المحتوى لـ base64
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        payload = {
            "message": f"backup: {filename} — {now_cairo().strftime('%Y-%m-%d %H:%M')}",
            "content": encoded
        }
        if sha:
            payload["sha"] = sha

        response = requests.put(url, headers=headers, json=payload, timeout=30)

        if response.status_code in [200, 201]:
            logger.info(f"✅ Uploaded: {filename}")
            return True
        else:
            logger.error(f"❌ Upload failed ({filename}): {response.status_code} — {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"❌ GitHub timeout ({filename})")
        return False
    except Exception as e:
        logger.error(f"❌ GitHub error ({filename}): {e}")
        return False


# ============================================================
# Main Backup Job
# ============================================================

def run_backup(bot=None, chat_id=None) -> dict:
    """
    الـ Job الرئيسي — بيتشغل من APScheduler كل يوم 02:00 AM.

    الخطوات:
        1. Export كل collection من Firestore
        2. رفع كل collection كـ JSON على GitHub
        3. إرسال Telegram notification بالنتيجة

    Returns:
        dict: نتيجة الـ backup لكل collection
    """
    logger.info("💾 ═══════════════════════════════")
    logger.info("💾 ADAM Backup — Started")
    logger.info("💾 ═══════════════════════════════")

    now        = now_cairo()
    date_str   = now.strftime("%Y-%m-%d")
    time_str   = now.strftime("%H:%M")
    results    = {}

    for collection in COLLECTIONS:

        # 1. Export من Firestore
        data = export_collection(collection)

        # 2. تحويل لـ JSON
        content = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str          # يتعامل مع Timestamps وأي object غير قابل للـ serialize
        )

        # 3. رفع على GitHub — المسار: backups/YYYY-MM-DD/collection.json
        filename = f"backups/{date_str}/{collection}.json"
        success  = upload_to_github(filename, content)

        results[collection] = {
            "success": success,
            "count":   len(data),
            "file":    filename
        }

    # ============================================================
    # Telegram Notification
    # ============================================================

    success_count = sum(1 for r in results.values() if r["success"])
    total         = len(COLLECTIONS)

    if bot and chat_id:
        try:
            if success_count == total:
                # ✅ كل حاجة تمام
                lines = [
                    f"  • {col}: {r['count']} docs"
                    for col, r in results.items()
                ]
                message = (
                    f"💾 Backup ✅ — تم بنجاح\n"
                    f"📅 {date_str}  🕐 {time_str}\n\n"
                    f"Collections:\n" + "\n".join(lines) +
                    f"\n\n📁 github.com/{GITHUB_REPO}"
                )
            else:
                # ⚠️ في مشكلة
                failed  = [col for col, r in results.items() if not r["success"]]
                success_list = [col for col, r in results.items() if r["success"]]
                message = (
                    f"💾 Backup ⚠️ — ناقص\n"
                    f"📅 {date_str}  🕐 {time_str}\n\n"
                    f"✅ نجح ({success_count}/{total}):\n" +
                    "\n".join(f"  • {c}" for c in success_list) +
                    f"\n\n❌ فشل:\n" +
                    "\n".join(f"  • {c}" for c in failed) +
                    f"\n\n⚠️ راجع الـ logs على Railway"
                )

            bot.send_message(chat_id, message)
            logger.info(f"✅ Telegram notification sent")

        except Exception as e:
            logger.error(f"❌ Telegram notification failed: {e}")

    logger.info(f"💾 Backup done: {success_count}/{total} collections")
    logger.info("💾 ═══════════════════════════════")

    return results
