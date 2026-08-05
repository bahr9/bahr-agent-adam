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

# أسماء الـ Collections المطلوب حمايتها.
#
# توسعة أوديت 2026-08-05: الليستة القديمة كانت 5 collections بس، ومكانش
# فيها ولا واحدة من البيانات المالية -- لا الأقساط ولا المصاريف ولا مشاريع
# Bahr OS ولا سجل الأحداث (adam_events) اللي نظام Self-State كله قايم عليه.
# يعني أي فقد من ناحية Firestore مكانش ليه أي مسار استرجاع.
#
# المستبعَد عن قصد: بيانات القياس والتشخيص اللي بتتولد تلقائي وبتكبر بسرعة
# (tool_health_checks, tool_failures_log, alert_state, state_snapshots)
# -- دي معلومات تشغيلية بتتبني من تاني، مش بيانات شغل.
COLLECTIONS = [
    # ذاكرة آدم والمحادثات
    "user_memory",
    "memory_notes",
    "conversations",
    "adam_human_model",
    "bahr_graph_nodes",

    # بيانات مالية -- الأهم على الإطلاق
    "loans",
    "expenses",
    "decision_ledger",
    "price_base",

    # سجل الأحداث الثابت (Event Store)
    "adam_events",

    # مشاريع وعملاء
    "projects",
    "project_files",
    "site_projects",
    "bahrSites",
    "clients",
    "client_followups",

    # مهام وتذكيرات
    "reminders",
    "recurring_reminders",
    "office_tasks",
    "personal_tasks",
    "ideas",

    # عين الخبير
    "eye_expert_config",
    "ain_al_khabeer_logs",
]

# ============================================================
# المجموعات الفرعية -- كانت خارج النسخ الاحتياطي تمامًا
# ============================================================
# 🔴 اكتشاف 2026-08-05 (من تحليل فرونت Bahr OS): فيه تلات مجموعات فرعية
# تحت كل مستند مشروع، والنسخ الاحتياطي **عمره ما أخد منها حاجة**:
#
#     projects/{code}/invoices/{phase}      -- كل الفواتير
#     projects/{code}/siteReports/{date}    -- كل تقارير الموقع
#     projects/{code}/purchases/{id}        -- كل أوامر الشراء
#
# السبب إن `.stream()` على مجموعة أب مابيرجّعش المجموعات الفرعية بتاعتها.
# فالنسخة كانت بتخلص وتقول "تم بنجاح ✅" وهي مش شايلة السجل المالي للشغل.
# ودي نفس فئة العطل اللي اتصلحت الصبح: نجاح شكله سليم وهو ناقص.

SUBCOLLECTIONS = {
    "projects": ["invoices", "siteReports", "purchases"],
}

# جداول Supabase المطلوب حمايتها (Pilot: Firestore -> Supabase).
#
# مهم: مصدر الحقيقة للتذكيرات المتكررة بقى Supabase -- نسخة Firestore مجرد
# mirror للفترة التجريبية. طول ما الـ dual-write شغال الاتنين متطابقين، لكن
# أول ما الـ pilot يخلص والـ mirror يتشال، النسخ من Firestore هيفضل يقول
# "تم بنجاح ✅" وهو بياخد داتا بايتة. فبناخد الأصل من Supabase من دلوقتي.
#
# القاعدة لأي جدول بيتهاجر بعد كده: ضيفه هنا **قبل** ما تشيل الـ dual-write.
SUPABASE_TABLES = [
    "recurring_reminders",
]


# ============================================================
# Firestore Export
# ============================================================

def export_collection(collection_name: str):
    """
    يصدّر collection كاملة من Firestore كـ list of dicts.
    بيستخدم firestore_db الـ global من firebase_service.

    بيرجع list عند النجاح (ممكن تكون فاضية لو الـ collection نفسها فاضية)،
    أو None لو الاتصال أو القراءة فشلت.

    التفرقة دي مهمة (أوديت 2026-08-05): قبل كده الحالتين كانوا بيرجعوا []،
    فلو Firebase وقع الـ backup كان بيرفع ملف فاضي **فوق النسخة الكويسة**
    ويقول "تم بنجاح ✅" -- شبكة الأمان كانت بتفشل بالظبط في اللحظة اللي
    محتاجينها فيها.
    """
    try:
        from services.firebase_service import firestore_db

        if firestore_db is None:
            logger.error(f"❌ Firestore مش متصل — تعذّر تصدير {collection_name}")
            return None

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
        return None


def export_subcollection(parent: str, child: str):
    """
    يصدّر مجموعة فرعية عبر كل مستندات الأب.

    نفس عقد export_collection: list عند النجاح، None عند الفشل.
    كل سجل بياخد `_parent_id` عشان الرابط بالمشروع مايضيعش في النسخة.
    """
    try:
        from services.firebase_service import firestore_db

        if firestore_db is None:
            logger.error(f"❌ Firestore مش متصل — تعذّر تصدير {parent}/{child}")
            return None

        data = []
        for parent_doc in firestore_db.collection(parent).stream():
            for doc in parent_doc.reference.collection(child).stream():
                item = doc.to_dict() or {}
                item["_doc_id"] = doc.id
                item["_parent_id"] = parent_doc.id
                data.append(item)

        logger.info(f"📦 Exported {parent}/{child}: {len(data)} docs")
        return data

    except Exception as e:
        logger.error(f"❌ Export failed ({parent}/{child}): {e}")
        return None


def export_supabase_table(table_name: str):
    """
    يصدّر جدول كامل من Supabase كـ list of dicts.

    نفس عقد export_collection: list عند النجاح، None عند الفشل.
    """
    try:
        from services import supabase_service

        if supabase_service.supabase_client is None:
            logger.error(f"❌ Supabase مش متصل — تعذّر تصدير {table_name}")
            return None

        resp = supabase_service.supabase_client.table(table_name).select("*").execute()
        data = resp.data or []

        logger.info(f"📦 Exported [Supabase] {table_name}: {len(data)} rows")
        return data

    except Exception as e:
        logger.error(f"❌ Export failed [Supabase] ({table_name}): {e}")
        return None


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

    # كل وحدة نسخ = (اسم للعرض، مسار الملف، دالة التصدير)
    jobs = [
        (name, f"backups/{date_str}/{name}.json", lambda n=name: export_collection(n))
        for name in COLLECTIONS
    ] + [
        (f"{parent}/{child}",
         f"backups/{date_str}/{parent}__{child}.json",
         lambda p=parent, c=child: export_subcollection(p, c))
        for parent, children in SUBCOLLECTIONS.items()
        for child in children
    ] + [
        (f"supabase:{table}",
         f"backups/{date_str}/supabase/{table}.json",
         lambda t=table: export_supabase_table(t))
        for table in SUPABASE_TABLES
    ]

    for label, filename, export in jobs:

        # 1. Export من المصدر
        data = export()

        # فشل قراءة = وقفة. ممنوع نرفع ملف فاضي فوق نسخة كويسة موجودة.
        if data is None:
            logger.error(f"⛔ {label}: التصدير فشل — مش هنرفع حاجة فوق النسخة القديمة")
            results[label] = {
                "success": False,
                "count":   0,
                "file":    None,
                "error":   "export failed",
            }
            continue

        # 2. تحويل لـ JSON
        content = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str          # يتعامل مع Timestamps وأي object غير قابل للـ serialize
        )

        # 3. رفع على GitHub
        success = upload_to_github(filename, content)

        results[label] = {
            "success": success,
            "count":   len(data),
            "file":    filename
        }

    # ============================================================
    # Telegram Notification
    # ============================================================

    success_count = sum(1 for r in results.values() if r["success"])
    total         = len(results)

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
