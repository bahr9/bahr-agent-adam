# -*- coding: utf-8 -*-
"""
💰 قاعدة أسعار بحر (الفجوة 3 -- بعد فحص 2026-08-04)

الفحص المبدئي على سجل المصاريف الحقيقي قال بوضوح: 18 عملية كلها شخصي
ومكتب، صفر أسعار خامات أو تشطيب. يعني المصدر الوحيد الموثوق لأسعار
السوق هو أحمد نفسه -- بيمليها لآدم وبتتخزن هنا كمرجع تسعير دائم
للاستشارات، بدل تخمين الموديل أو أرقام إنترنت لا تخص السوق المصري.

نفس فلسفة ملف المشروع: منطق pure قابل للاختبار من غير Firestore،
والتخزين قشرة رفيعة. كل سعر معاه وحدته وتاريخه، ولما السعر يتحدث
القيمة القديمة بتتحفظ في history -- تضخم الأسعار في مصر بيخلي "امتى"
جزء من السعر نفسه.
"""

import hashlib

from utils.logger import logger
from utils.time_utils import now_cairo


# ============================================================
# منطق pure (بدون I/O)
# ============================================================

def normalize_item(name):
    """توحيد اسم البند للمقارنة: حالة الأحرف والمسافات الزيادة."""
    return " ".join(str(name or "").split()).casefold()


def price_id_for_item(name):
    """id حتمي من اسم البند -- نفس البند يوصل لنفس السجل دايمًا."""
    digest = hashlib.sha1(normalize_item(name).encode("utf-8")).hexdigest()[:12]
    return "price-" + digest


def search_items(query, existing_items):
    """بنود بيطابقها الطلب (احتواء في الاتجاهين، زي حل أسماء المشاريع).

    طلب فاضي = كل البنود (عرض القاعدة كاملة).
    """
    q = normalize_item(query)
    if not q:
        return list(existing_items)
    return [
        item for item in existing_items
        if (lambda n: n and (n in q or q in n))(normalize_item(item))
    ]


def format_price_entries(entries):
    """يحوّل سجلات الأسعار لعرض عربي مقروء، بالوحدة وتاريخ آخر تحديث."""
    if not entries:
        return "قاعدة الأسعار لسه فاضية."
    lines = ["💰 قاعدة أسعار بحر:"]
    for entry in sorted(entries, key=lambda e: normalize_item(e.get("item", ""))):
        line = "  - " + entry.get("item", "؟") + ": " + str(entry.get("price", "؟"))
        unit = entry.get("unit", "")
        if unit:
            line += " / " + unit
        updated = str(entry.get("updated_at", ""))[:10]
        if updated:
            line += "  (آخر تحديث " + updated + ")"
        note = entry.get("note", "")
        if note:
            line += " -- " + note
        lines.append(line)
    return "\n".join(lines)


# ============================================================
# التخزين (Firestore) -- قشرة رفيعة
# ============================================================

def _collection():
    from services.firebase_service import firestore_db
    from config import PRICE_BASE_COLLECTION

    if firestore_db is None:
        raise RuntimeError("Firestore مش متصل")
    return firestore_db.collection(PRICE_BASE_COLLECTION)


def _all_docs():
    try:
        return [doc.to_dict() or {} for doc in _collection().stream()]
    except Exception as e:
        logger.error("❌ خطأ في قراءة قاعدة الأسعار: " + str(e))
        return []


def save_price(item, price, unit="", note=""):
    """يسجل أو يحدّث سعر بند. التحديث بيحفظ السعر القديم في history."""
    item = str(item or "").strip()
    if not item or not str(price or "").strip():
        return "اسم البند والسعر مطلوبين."

    ref = _collection().document(price_id_for_item(item))
    snapshot = ref.get()
    doc = snapshot.to_dict() if snapshot.exists else {"item": item, "history": []}

    old_price = doc.get("price")
    if old_price is not None and str(old_price) != str(price).strip():
        doc.setdefault("history", []).append(
            {"price": old_price, "recorded_at": doc.get("updated_at", "")}
        )

    doc.update({
        "price": str(price).strip(),
        "unit": str(unit or "").strip(),
        "note": str(note or "").strip(),
        "source": "ahmed",
        "updated_at": str(now_cairo()),
    })
    ref.set(doc)
    logger.info("💰 سعر اتسجل: " + item + " = " + str(price))
    result = "اتسجل في قاعدة الأسعار: " + item + " = " + str(price).strip()
    if str(unit or "").strip():
        result += " / " + str(unit).strip()
    if old_price is not None and str(old_price) != str(price).strip():
        result += " (السعر القديم " + str(old_price) + " اتحفظ في التاريخ)"
    return result


def get_prices(query=""):
    """يجيب أسعار بنود بتطابق الطلب -- أو القاعدة كلها لو الطلب فاضي."""
    docs = _all_docs()
    by_item = {d.get("item", ""): d for d in docs if d.get("item")}
    matched = search_items(query, list(by_item))
    if not matched and str(query or "").strip():
        listing = "، ".join(sorted(by_item)) if by_item else "القاعدة لسه فاضية"
        return (
            "البند ده مش في قاعدة أسعارك. الموجود حاليًا: " + listing
            + " -- لو عندك سعره قولهولي أسجله."
        )
    return format_price_entries([by_item[i] for i in matched])
