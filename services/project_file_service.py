# -*- coding: utf-8 -*-
"""
📁 ملف المشروع المستمر (الفجوة 1 -- قرار أحمد 2026-08-04)

"ملف مشروع" منظم لكل عميل: فراغات، أبعاد، قرارات (ستايل/ألوان/خامات)،
ميزانية -- بحقول مش نص حر، وبيترجع تلقائيًا أول ما اسم المشروع يتقال
تاني ولو بعد أسابيع. ده اللي بيفرّق بين "غريب ذكي كل جلسة" و"استشاري
فاكر مشروعك".

الـ schema والدروس منقولين من مشروع HOPE المؤرشف (Archiducer، ADR 0006):
- id حتمي من الاسم (نفس الاسم = نفس الملف دايمًا، عبر أي جلسة).
- حل الاسم بالتطابق الجزئي، والغموض بيتسأل عنه صراحة بدل التخمين
  (درس HOPE: التخمين في هوية المشروع أخطر من سؤال توضيحي).
- كل حقيقة معاها مصدرها ووقتها (provenance) -- المصدر هنا دايمًا أحمد
  نفسه لأن الأداة بتتنده من محادثته.

منطق الحل والتنسيق pure functions قابلة للاختبار من غير Firestore --
التخزين نفسه قشرة رفيعة بنفس نمط باقي خدمات آدم.
"""

import hashlib

from utils.logger import logger
from utils.time_utils import now_cairo

# الفئات المسموحة -- بنية حقول مش نص حر (طلب أحمد الصريح).
CATEGORIES = ("فراغات", "أبعاد", "قرارات", "ميزانية", "عميل", "ملاحظات")


# ============================================================
# منطق pure (بدون I/O) -- قابل للاختبار مباشرة
# ============================================================

def normalize_name(name):
    """توحيد اسم المشروع للمقارنة: حالة الأحرف والمسافات الزيادة."""
    return " ".join(str(name or "").split()).casefold()


def project_id_for_name(name):
    """id حتمي من الاسم -- نفس الاسم يوصل لنفس الملف من أي جلسة."""
    digest = hashlib.sha1(normalize_name(name).encode("utf-8")).hexdigest()[:12]
    return "proj-" + digest


def resolve_project_name(query, existing_names):
    """يحل اسم مشروع مطلوب مقابل الأسماء الموجودة.

    بيرجع (status, matches):
      - ("exact", [name])      تطابق كامل بعد التوحيد
      - ("resolved", [name])   تطابق جزئي وحيد (الاسم جوه الطلب أو العكس)
      - ("ambiguous", names)   أكتر من مرشح -- اسأل، متخمنش
      - ("none", [])           مفيش
    """
    q = normalize_name(query)
    if not q:
        return "none", []

    normalized = {name: normalize_name(name) for name in existing_names}
    exact = [name for name, n in normalized.items() if n == q]
    if exact:
        return "exact", exact[:1]

    partial = [
        name for name, n in normalized.items()
        if (n and (n in q or q in n))
    ]
    if len(partial) == 1:
        return "resolved", partial
    if len(partial) > 1:
        return "ambiguous", sorted(partial)
    return "none", []


def format_project_file(doc):
    """يحوّل مستند الملف لعرض عربي مقروء، فئة فئة."""
    lines = ["📁 ملف مشروع: " + doc.get("display_name", "بدون اسم")]
    facts = doc.get("facts", {})
    for category in CATEGORIES:
        entries = facts.get(category) or {}
        if not entries:
            continue
        lines.append("")
        lines.append("● " + category + ":")
        for key in sorted(entries):
            entry = entries[key]
            value = entry.get("value", "") if isinstance(entry, dict) else str(entry)
            lines.append("  - " + key + ": " + value)
    if len(lines) == 1:
        lines.append("(الملف موجود لكن لسه مفيهوش حقائق مسجلة)")
    return "\n".join(lines)


# ============================================================
# التخزين (Firestore) -- قشرة رفيعة
# ============================================================

def _collection():
    from services.firebase_service import firestore_db
    from config import PROJECT_FILES_COLLECTION

    if firestore_db is None:
        raise RuntimeError("Firestore مش متصل")
    return firestore_db.collection(PROJECT_FILES_COLLECTION)


def list_project_names():
    """كل أسماء المشاريع الموجودة (للحل والاقتراح)."""
    try:
        return [
            (doc.to_dict() or {}).get("display_name", doc.id)
            for doc in _collection().stream()
        ]
    except Exception as e:
        logger.error("❌ خطأ في قراءة أسماء المشاريع: " + str(e))
        return []


def save_project_fact(project_name, category, key, value):
    """يسجل حقيقة في ملف المشروع (وينشئ الملف لو أول مرة).

    بيرجع نص نتيجة جاهز للموديل.
    """
    if category not in CATEGORIES:
        return "الفئة لازم تكون واحدة من: " + "، ".join(CATEGORIES)
    if not str(project_name or "").strip() or not str(key or "").strip():
        return "اسم المشروع واسم الحقيقة مطلوبين."

    # لو الاسم المطلوب بيطابق مشروع موجود جزئيًا، سجّل فيه هو --
    # مش تنشئ ملف تاني لنفس المشروع باسم أطول/أقصر.
    status, matches = resolve_project_name(project_name, list_project_names())
    if status == "ambiguous":
        return (
            "فيه أكتر من مشروع ممكن تقصده: "
            + "، ".join(matches)
            + " -- قول الاسم كامل عشان أسجل في الملف الصح."
        )
    resolved_name = matches[0] if status in ("exact", "resolved") else str(project_name).strip()

    doc_id = project_id_for_name(resolved_name)
    ref = _collection().document(doc_id)
    snapshot = ref.get()
    doc = snapshot.to_dict() if snapshot.exists else {
        "display_name": resolved_name,
        "created_at": str(now_cairo()),
        "facts": {},
    }
    facts = doc.setdefault("facts", {})
    facts.setdefault(category, {})[str(key).strip()] = {
        "value": str(value).strip(),
        "source": "ahmed",
        "updated_at": str(now_cairo()),
    }
    doc["updated_at"] = str(now_cairo())
    ref.set(doc)
    logger.info("📁 حقيقة اتسجلت في مشروع " + resolved_name + ": " + str(key))
    return "اتسجلت في ملف مشروع " + resolved_name + ": " + str(key) + " = " + str(value)


def get_project_file(project_name):
    """يجيب ملف المشروع بالاسم (بتطابق جزئي). بيرجع نص جاهز للموديل."""
    names = list_project_names()
    status, matches = resolve_project_name(project_name, names)

    if status == "ambiguous":
        return (
            "فيه أكتر من مشروع بالاسم ده: "
            + "، ".join(matches)
            + " -- أنهي واحد تقصد؟"
        )
    if status == "none":
        if names:
            return (
                "مفيش ملف مشروع بالاسم ده. المشاريع الموجودة: "
                + "، ".join(sorted(names))
            )
        return "مفيش أي ملفات مشاريع متسجلة لسه."

    doc_id = project_id_for_name(matches[0])
    snapshot = _collection().document(doc_id).get()
    if not snapshot.exists:
        return "مفيش ملف مشروع بالاسم ده."
    return format_project_file(snapshot.to_dict() or {})
