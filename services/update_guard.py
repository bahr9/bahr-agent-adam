# -*- coding: utf-8 -*-
"""
🛡️ حارس الوجود قبل التحديث (أوديت 2026-08-04)

المشكلة اللي بيقفلها: أدوات التحديث بتاخد معرّف المستند من الموديل
وبتكتب بـ `.set(data, merge=True)`. في Firestore ده **بينشئ** المستند لو
مش موجود -- فمعرّف ناقص أو متهيّأ بيولّد مشروع/عميل وهمي بصمت، وبيظهر
بعدين في القوايم كإنه حقيقي.

الدليل وقت الأوديت: مستند في client_followups اسمه 'محمد علي' (مش على
نمط CLT-) فيه حقول تحديث بس -- شبح اتولد من محاولة تحديث بمعرّف غلط.

نفس حارس Bahr OS بالظبط (الكود الموجود = فتح، مش كتابة): افحص الوجود
الأول، ولو مش موجود ارفض واعرض المعرّفات المتاحة بدل ما تنشئ.
"""

_MAX_LISTED = 10


def missing_document_message(kind, requested_id, available_ids):
    """رسالة رفض واضحة لما المعرّف مش موجود -- مع البدائل المتاحة.

    بترجع نص جاهز للموديل (مش بترفع استثناء) عشان الرد يوصل لأحمد زي
    باقي نتايج الأدوات.
    """
    ids = [str(i) for i in (available_ids or []) if str(i).strip()]
    head = "❌ " + kind + " بالمعرّف '" + str(requested_id) + "' مش موجود -- وممنوع أنشئ واحد جديد بالغلط."
    if not ids:
        return head + " ومفيش أي " + kind + " متسجل حاليًا."
    shown = ids[:_MAX_LISTED]
    listing = "، ".join(shown)
    if len(ids) > _MAX_LISTED:
        listing += " ... وغيرهم (" + str(len(ids)) + " إجمالًا)"
    return head + " المتاح: " + listing


def document_exists(collection_name, doc_id):
    """هل المستند ده موجود فعلًا؟ (False لو Firestore مش متصل أو خطأ)."""
    from services.firebase_service import firestore_db

    if firestore_db is None or not str(doc_id or "").strip():
        return False
    try:
        return firestore_db.collection(collection_name).document(str(doc_id)).get().exists
    except Exception:
        return False


def list_document_ids(collection_name, limit=50):
    """معرّفات المستندات الموجودة -- للعرض في رسالة الرفض."""
    from services.firebase_service import firestore_db

    if firestore_db is None:
        return []
    try:
        return [d.id for d in firestore_db.collection(collection_name).limit(limit).stream()]
    except Exception:
        return []
