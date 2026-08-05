# -*- coding: utf-8 -*-
"""
📦 التصدير الكامل قبل الهجرة -- Firestore -> ملفات JSON محلية

الهدف: نسخة **مؤكدة ١٠٠٪** من كل مجموعة قبل أي لمسة كود هجرة.
الأولوية اكتمال وسلامة النسخة، مش السرعة.

الاستخدام:
    python migration_export.py              # تصدير (بيكمّل من حيث وقف)
    python migration_export.py --verify     # تحقق من نسخة موجودة بس
    python migration_export.py --fresh      # يبدأ مجلد جديد من الصفر

مبادئ التصميم:
  - **مايكتبش فوق نسخة كويسة**: لو تصدير مجموعة فشل، الملف القديم بيفضل.
  - **قابل للاستئناف**: لو الكوتا خلصت في النص، شغّله تاني وهيكمّل الناقص بس.
  - **بيعدّ القراءات**: كل مستند = قراءة، والعدّاد بيتسجل في الـ manifest.
  - **التحقق منفصل عن التصدير**: التصدير ماينفعش يعلن نجاحه بنفسه.

ملحوظة كوتا: التصدير الكامل تكلفته تقريبًا عدد المستندات الكلي (~6 آلاف
قراءة وقت الكتابة). الباقة المجانية 50 ألف/يوم، فده ~12%.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


# ============================================================
# قايمة المجموعات -- المرجع الوحيد
# ============================================================
# 30 مجموعة حية، مستخرجة من الكود (config.py + الثوابت الجوه
# firebase_service.py + الأسماء الحرفية). depaProjects مستبعدة -- ميتة
# تمامًا، الثابت بتاعها مش متنادى ولا مرة.
#
# الميتة (clients, office_tasks, site_projects, recurring_tasks) **بتتصدّر
# برضه** -- أرشيف، مش هتتعمل ليها جداول. لو فيها بيانات قديمة عايزينها
# محفوظة قبل ما نسيب Firestore.

COLLECTIONS = [
    # ذاكرة ومحادثات
    "user_memory",
    "memory_notes",
    "conversations",
    "adam_human_model",
    "bahr_graph_nodes",

    # مالية
    "loans",
    "expenses",
    "decision_ledger",
    "price_base",

    # سجل الأحداث
    "adam_events",

    # مشاريع وعملاء
    "projects",
    "project_files",
    "bahrSites",
    "client_followups",

    # مهام وتذكيرات
    "reminders",
    "recurring_reminders",
    "personal_tasks",
    "ideas",
    "agent_tasks",

    # عين الخبير
    "eye_expert_config",
    "ain_al_khabeer_logs",

    # حالة ذاتية وتشخيص
    "adam_self_state",
    "adam_state_snapshots",
    "adam_expressions",
    "tool_health_checks",
    "tool_failures_log",
    "tool_health_alert_state",
    "project_status_alert_state",
    "system_flags",

    # ميتة -- أرشيف بس، مش هتتعمل ليها جداول
    "clients",
    "office_tasks",
    "site_projects",
    "recurring_tasks",

    # مجموعات فرونت Bahr OS -- آدم مش عارفها خالص (اكتشاف 2026-08-05)
    "users",           # users/{uid}.projects[] -- فهرس عضوية المستخدم في المشاريع
    "notifications",   # طلبات الشراء -- بتتكتب ومحدش بيقراها
]


# ============================================================
# المجموعات الفرعية (subcollections)
# ============================================================
# 🔴 اكتشاف حرج (2026-08-05): تحليل فرونت Bahr OS كشف إن فيه تلات
# مجموعات فرعية تحت كل مستند مشروع، وآدم مش عارفها خالص:
#
#     projects/{code}/invoices/{phase}
#     projects/{code}/siteReports/{YYYY-MM-DD}
#     projects/{code}/purchases/{autoId}
#
# دي **كل فاتورة وكل تقرير موقع وكل أمر شراء في الشغل**.
#
# و`.stream()` على مجموعة أب **مابيرجّعش** المجموعات الفرعية -- فالنسخة
# من غير الجزء ده كانت هتبان مكتملة وهي ناقصة أخطر البيانات. ولو مشينا
# على Firestore واعتمدنا عليها، الاكتشاف كان هيحصل بعد فوات الأوان.
#
# نفس الثغرة موجودة في services/backup_service.py -- النسخ الاحتياطي
# اليومي كمان مابياخدش المجموعات الفرعية دي.

SUBCOLLECTIONS = {
    "projects": ["invoices", "siteReports", "purchases"],
}

EXPORT_ROOT = "exports"
MANIFEST_NAME = "manifest.json"


# ============================================================
# أدوات
# ============================================================

def log(message):
    print(message, flush=True)


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def latest_export_dir():
    """أحدث مجلد تصدير موجود، أو None."""
    if not os.path.isdir(EXPORT_ROOT):
        return None
    dirs = sorted(
        d for d in os.listdir(EXPORT_ROOT)
        if os.path.isdir(os.path.join(EXPORT_ROOT, d))
    )
    return os.path.join(EXPORT_ROOT, dirs[-1]) if dirs else None


def load_manifest(export_dir):
    path = os.path.join(export_dir, MANIFEST_NAME)
    if not os.path.exists(path):
        return {"started_at": utc_stamp(), "collections": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(export_dir, manifest):
    manifest["updated_at"] = utc_stamp()
    path = os.path.join(export_dir, MANIFEST_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ============================================================
# التصدير
# ============================================================

def _write_json(export_dir, name, docs):
    """كتابة ذرية: ملف مؤقت ثم إعادة تسمية -- انقطاع في النص مايسيبش
    ملف نص نص مكان ملف كويس."""
    payload = json.dumps(docs, ensure_ascii=False, indent=2, default=str)
    final_path = os.path.join(export_dir, f"{name}.json")
    tmp_path = final_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp_path, final_path)
    return len(payload.encode("utf-8"))


def export_subcollection(firestore_db, parent, child, export_dir):
    """يصدّر مجموعة فرعية عبر **كل** مستندات الأب في ملف واحد.

    كل سجل بياخد `_parent_id` عشان نعرف تحت أنهي مشروع كان.
    """
    docs = []
    for parent_doc in firestore_db.collection(parent).stream():
        for snapshot in parent_doc.reference.collection(child).stream():
            record = snapshot.to_dict() or {}
            record["_doc_id"] = snapshot.id
            record["_parent_id"] = parent_doc.id
            record["_parent_collection"] = parent
            docs.append(record)

    name = f"{parent}__{child}"
    size = _write_json(export_dir, name, docs)
    return {
        "status": "success",
        "documents": len(docs),
        "bytes": size,
        "file": f"{name}.json",
        "kind": "subcollection",
        "exported_at": utc_stamp(),
    }


def export_collection(firestore_db, name, export_dir):
    """يصدّر مجموعة واحدة.

    بيرجع dict بالنتيجة، أو بيرمي استثناء لو القراءة فشلت -- المنادي
    هو اللي بيقرر يكمّل ولا يقف. **ممنوع نبلع الفشل هنا**: تصدير
    "ناجح" وهو ناقص أسوأ من تصدير فشل بصوت عالي.
    """
    docs = []
    for snapshot in firestore_db.collection(name).stream():
        record = snapshot.to_dict() or {}
        record["_doc_id"] = snapshot.id
        docs.append(record)

    payload = json.dumps(docs, ensure_ascii=False, indent=2, default=str)

    # كتابة ذرية: ملف مؤقت ثم إعادة تسمية -- عشان انقطاع في النص
    # مايسيبش ملف نص نص مكان ملف كويس
    final_path = os.path.join(export_dir, f"{name}.json")
    tmp_path = final_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(payload)
    os.replace(tmp_path, final_path)

    return {
        "status": "success",
        "documents": len(docs),
        "bytes": len(payload.encode("utf-8")),
        "file": f"{name}.json",
        "exported_at": utc_stamp(),
    }


def export_units():
    """كل وحدات التصدير: مجموعات أب + مجموعات فرعية."""
    units = [(name, None) for name in COLLECTIONS]
    for parent, children in SUBCOLLECTIONS.items():
        for child in children:
            units.append((parent, child))
    return units


def unit_name(parent, child):
    return parent if child is None else f"{parent}__{child}"


def run_export(fresh=False):
    from services.firebase_service import init_firebase
    import services.firebase_service as fs

    if not init_firebase():
        log("❌ فشل الاتصال بـ Firebase -- وقفنا قبل أي كتابة")
        return 1

    os.makedirs(EXPORT_ROOT, exist_ok=True)

    export_dir = None if fresh else latest_export_dir()
    if export_dir is None:
        export_dir = os.path.join(EXPORT_ROOT, utc_stamp())
        os.makedirs(export_dir, exist_ok=True)
        log(f"📁 مجلد تصدير جديد: {export_dir}")
    else:
        log(f"📁 بكمّل في: {export_dir}")

    manifest = load_manifest(export_dir)
    done = manifest["collections"]

    total_docs = 0
    failed = []
    skipped = []

    log("")
    log(f"{'المجموعة':<32} {'الحالة':<10} {'مستندات':>9}  {'حجم':>10}")
    log("-" * 68)

    for parent, child in export_units():
        name = unit_name(parent, child)
        previous = done.get(name)
        if previous and previous.get("status") == "success" and not fresh:
            skipped.append(name)
            total_docs += previous["documents"]
            log(f"{name:<32} {'موجود':<10} {previous['documents']:>9}  {previous['bytes']:>9,}b")
            continue

        try:
            if child is None:
                result = export_collection(fs.firestore_db, name, export_dir)
            else:
                result = export_subcollection(fs.firestore_db, parent, child, export_dir)
            done[name] = result
            total_docs += result["documents"]
            log(f"{name:<32} {'✅':<10} {result['documents']:>9}  {result['bytes']:>9,}b")
        except Exception as e:
            # مابنسجلش نجاح، ومابنمسحش أي ملف قديم موجود
            done[name] = {
                "status": "failed",
                "error": str(e)[:200],
                "attempted_at": utc_stamp(),
            }
            failed.append(name)
            log(f"{name:<32} {'❌':<10}  {str(e)[:32]}")

        save_manifest(export_dir, manifest)

    log("-" * 68)
    log(f"{'الإجمالي':<32} {'':<10} {total_docs:>9}")
    log("")

    if skipped:
        log(f"⏭️  اتخطّت (متصدّرة قبل كده): {len(skipped)}")
    if failed:
        log(f"❌ فشلت {len(failed)} مجموعة: {', '.join(failed)}")
        log("   شغّل السكريبت تاني -- هيحاول على اللي فشل بس.")
        return 1

    log("✅ كل المجموعات اتصدّرت. شغّل --verify قبل ما تعتبرها مؤكدة.")
    return 0


# ============================================================
# التحقق -- منفصل عن التصدير عن قصد
# ============================================================

def run_verify(export_dir=None):
    """يتأكد من سلامة النسخة. مايلمسش Firestore خالص."""
    export_dir = export_dir or latest_export_dir()
    if export_dir is None:
        log("❌ مفيش أي مجلد تصدير")
        return 1

    log(f"🔍 بتحقق من: {export_dir}")
    manifest = load_manifest(export_dir)
    recorded = manifest.get("collections", {})

    problems = []
    warnings = []
    total_docs = 0

    log("")
    log(f"{'المجموعة':<32} {'مستندات':>9}  {'الحالة'}")
    log("-" * 68)

    for parent, child in export_units():
        name = unit_name(parent, child)
        entry = recorded.get(name)
        path = os.path.join(export_dir, f"{name}.json")

        if entry is None:
            problems.append(f"{name}: مش موجود في الـ manifest خالص")
            log(f"{name:<32} {'-':>9}  ❌ ناقص")
            continue

        if entry.get("status") != "success":
            problems.append(f"{name}: التصدير فشل -- {entry.get('error', '?')[:60]}")
            log(f"{name:<32} {'-':>9}  ❌ فشل")
            continue

        if not os.path.exists(path):
            problems.append(f"{name}: مسجّل ناجح بس الملف مش موجود")
            log(f"{name:<32} {'-':>9}  ❌ ملف مفقود")
            continue

        # JSON صالح؟
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            problems.append(f"{name}: JSON مش صالح -- {e}")
            log(f"{name:<32} {'-':>9}  ❌ JSON باظ")
            continue

        if not isinstance(data, list):
            problems.append(f"{name}: المفروض list، لقيت {type(data).__name__}")
            log(f"{name:<32} {'-':>9}  ❌ شكل غلط")
            continue

        # العدد مطابق للمسجّل؟
        if len(data) != entry["documents"]:
            problems.append(
                f"{name}: الملف فيه {len(data)} والـ manifest بيقول {entry['documents']}"
            )
            log(f"{name:<32} {len(data):>9}  ❌ عدد مختلف")
            continue

        # كل مستند لازم يكون فيه _doc_id -- من غيره مش هنعرف نرجّعه
        missing_ids = sum(1 for d in data if not d.get("_doc_id"))
        if missing_ids:
            problems.append(f"{name}: {missing_ids} مستند من غير _doc_id")
            log(f"{name:<32} {len(data):>9}  ❌ معرّفات ناقصة")
            continue

        # معرّفات مكررة = فقد بيانات عند الاستيراد
        ids = [d["_doc_id"] for d in data]
        if len(set(ids)) != len(ids):
            problems.append(f"{name}: فيه معرّفات مكررة")
            log(f"{name:<32} {len(data):>9}  ❌ تكرار")
            continue

        total_docs += len(data)

        if len(data) == 0:
            warnings.append(f"{name}: فاضية -- اتأكد إن ده صح مش عطل قراءة")
            log(f"{name:<32} {0:>9}  ⚠️  فاضية")
        else:
            log(f"{name:<32} {len(data):>9}  ✅")

    log("-" * 68)
    log(f"{'الإجمالي':<32} {total_docs:>9}")
    log("")

    if warnings:
        log("⚠️  تنبيهات:")
        for w in warnings:
            log(f"   - {w}")
        log("")

    if problems:
        log(f"❌ النسخة **مش** مؤكدة -- {len(problems)} مشكلة:")
        for p in problems:
            log(f"   - {p}")
        return 1

    log(f"✅ النسخة مؤكدة: {len(export_units())} وحدة، {total_docs:,} مستند، JSON كله صالح.")
    log(f"   المجلد: {export_dir}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="التصدير الكامل قبل هجرة Supabase")
    parser.add_argument("--verify", action="store_true", help="تحقق من نسخة موجودة، من غير أي قراءة من Firestore")
    parser.add_argument("--fresh", action="store_true", help="ابدأ مجلد جديد بدل ما تكمّل")
    args = parser.parse_args()

    if args.verify:
        return run_verify()
    return run_export(fresh=args.fresh)


if __name__ == "__main__":
    sys.exit(main())
