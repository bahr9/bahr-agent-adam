# -*- coding: utf-8 -*-
"""
📒 Event Store -- ADAM Self-State & Observation System (Stage 1 + 2)
=====================================================
سجل أحداث ثابت (Append-Only) لكل تغيير حقيقي في بيانات ADAM.

القانون الحاكم لكل المشروع:
  "لا يجوز لآدم أن يعبّر عن حالة داخلية ما لم تكن مبنية على دليل قابل للرصد."

الحدث (Event) هنا هو أصغر وحدة "دليل". أي حالة داخلية مستقبلية (Self-State v0.1+)
لازم ترجع لحدث أو أكتر مسجل هنا (evidence_event_ids)، مش لتخمين.

قواعد صارمة:
  - كل حدث لازم يكون له entity (type + id) و attribute -- إجبارية، بيرفض
    الحفظ لو أي واحدة فيهم فاضية.
  - الـ Store ده Append-Only: مفيش update_event ولا delete_event في الـ API.
    أي تصحيح لاحق = حدث جديد يشاور على القديم، مش تعديل فوقه.
  - أي Command API بيكتب domain data (زي services/loan_commands.py) لازم
    يستخدم record_event_with_write مش record_event لوحدها -- عشان تسجيل
    الحدث والكتابة الفعلية يحصلوا سوا ذريًا (Firestore batch)، بلا احتمال
    إن واحد يحصل من غير التاني.
"""

import uuid
from typing import Optional

from utils.time_utils import now_cairo
from utils.logger import logger
from config import EVENTS_COLLECTION


class InvalidEventError(ValueError):
    """بترفع لو حدث اتبعت بدون الحقول الإجبارية (entity_type / entity_id / attribute)."""
    pass


def _build_event(
    entity_type: str,
    entity_id: str,
    attribute: str,
    new_value=None,
    previous_value=None,
    source: str = "unknown",
    actor: str = "",
    chat_id=None,
    raw_context: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    بناء dict الحدث + التحقق من الحقول الإجبارية (entity_type/entity_id/attribute)
    -- من غير كتابة فعلية. مستخدمة داخليًا من record_event و record_event_with_write
    عشان قاعدة التحقق تفضل مكان واحد.
    """
    if not entity_type or not str(entity_type).strip():
        raise InvalidEventError("entity_type إجباري ومينفعش يبقى فاضي")
    if not entity_id or not str(entity_id).strip():
        raise InvalidEventError("entity_id إجباري ومينفعش يبقى فاضي")
    if not attribute or not str(attribute).strip():
        raise InvalidEventError("attribute إجباري ومينفعش يبقى فاضي")

    entity_type = str(entity_type).strip()
    entity_id = str(entity_id).strip()
    attribute = str(attribute).strip()

    return {
        "event_id": str(uuid.uuid4()),
        "entity": {"type": entity_type, "id": entity_id},
        "entity_key": f"{entity_type}:{entity_id}",  # حقل مشتق -- للاستعلام الفعّال فقط، مش جزء من العقد الدلالي
        "type_attribute_key": f"{entity_type}:{attribute}",  # حقل مشتق -- للاستعلام عبر كل entities من نفس النوع/الصفة (Stage 5)
        "attribute": attribute,
        "previous_value": previous_value,
        "new_value": new_value,
        "source": source,
        "actor": actor,
        "chat_id": chat_id,
        "raw_context": raw_context or {},
        "metadata": metadata or {},
        "occurred_at": now_cairo().isoformat(),
    }


def record_event(
    entity_type: str,
    entity_id: str,
    attribute: str,
    new_value=None,
    previous_value=None,
    source: str = "unknown",
    actor: str = "",
    chat_id=None,
    raw_context: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> str:
    """
    تسجيل حدث جديد في الـ Event Store (كتابة واحدة، بدون كتابة domain مصاحبة).
    بيرجع event_id (uuid4).

    entity_type / entity_id / attribute: إجبارية -- الحفظ بيترفض تمامًا لو
    أي واحدة فيهم فاضية أو مفقودة (InvalidEventError)، عشان أي حدث يبقى
    قابل للربط بكيان محدد وصفة محددة من غير غموض.

    لو الحدث بيصاحب كتابة فعلية في مكان تاني (زي حالة دفع قسط)، استخدم
    record_event_with_write بدل الدالة دي عشان الاتنين يحصلوا سوا أو ولا
    واحد فيهم -- منعًا لحالة "الحدث اتسجل بس الكتابة فشلت" أو العكس.
    """
    event = _build_event(
        entity_type, entity_id, attribute, new_value, previous_value,
        source, actor, chat_id, raw_context, metadata,
    )

    # كتابة مزدوجة (هجرة 2026-08-06): Supabase هو مصدر القراية دلوقتي،
    # وFirestore mirror. القانون الحاكم ("مفيش تعبير من غير دليل") بيتحقق
    # لو **أي** واحد فيهم نجح -- بنرمي بس لو الاتنين فشلوا مع بعض.
    from services import supabase_store
    sb_ok = supabase_store.insert_event(event)

    fs_ok = False
    fs_error = None
    from services.firebase_service import firestore_db
    if firestore_db is not None:
        try:
            firestore_db.collection(EVENTS_COLLECTION).document(event["event_id"]).set(event)
            fs_ok = True
        except Exception as e:
            fs_error = e
            logger.warning(f"⚠️ mirror الحدث لـ Firestore فشل (Supabase شايله): {str(e)[:80]}")

    if not sb_ok and not fs_ok:
        logger.error(f"❌ تسجيل الحدث فشل في المخزنين: {fs_error}")
        raise RuntimeError("تعذر تسجيل الحدث في أي مخزن -- Supabase وFirestore الاتنين فشلوا")

    logger.info(
        f"📒 event recorded: [{event['entity_key']}].{attribute} "
        f"({previous_value!r} -> {new_value!r}) id={event['event_id']}"
        + ("" if fs_ok and sb_ok else f" [sb={sb_ok} fs={fs_ok}]")
    )
    return event["event_id"]


def record_event_with_write(
    entity_type: str,
    entity_id: str,
    attribute: str,
    domain_collection: str,
    domain_document: str,
    domain_data: dict,
    new_value=None,
    previous_value=None,
    domain_merge: bool = True,
    source: str = "unknown",
    actor: str = "",
    chat_id=None,
    raw_context: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> str:
    """
    زي record_event بالظبط، لكن بتضمن الـ Atomicity: تسجيل الحدث + كتابة الـ
    domain document الفعلي بيحصلوا في commit واحد ذري (Firestore batch) --
    إما الاتنين بيحصلوا مع بعض أو ولا واحد فيهم بيحصل.

    ده بيقفل الثغرة اللي ممكن تحصل لو استخدمنا كتابتين منفصلتين: الحدث يتسجل
    والكتابة الفعلية تفشل (أو العكس) -- الحالتين بيبطلوا الضمانة الأساسية
    "مفيش كتابة من غير حدث موثّق". أي Command API جديد (أقساط دلوقتي،
    مصاريف/مشاريع لاحقًا) لازم يستخدم الدالة دي مش كتابتين منفصلتين.

    entity_type / entity_id / attribute: نفس قواعد record_event (إجبارية).
    """
    event = _build_event(
        entity_type, entity_id, attribute, new_value, previous_value,
        source, actor, chat_id, raw_context, metadata,
    )

    from services.firebase_service import firestore_db
    if firestore_db is None:
        logger.error("❌ مينفعش نسجل event -- Firestore مش متصل")
        raise RuntimeError("Firestore غير متصل -- تعذر تسجيل الحدث")

    try:
        batch = firestore_db.batch()

        event_ref = firestore_db.collection(EVENTS_COLLECTION).document(event["event_id"])
        batch.set(event_ref, event)

        domain_ref = firestore_db.collection(domain_collection).document(domain_document)
        if domain_merge:
            batch.set(domain_ref, domain_data, merge=True)
        else:
            batch.set(domain_ref, domain_data)

        batch.commit()

        # mirror لـ Supabase (هجرة 2026-08-06): الـ batch بتاع Firestore هو
        # الالتزام الذري الأساسي لسه (حدث + كتابة domain سوا). Supabase بياخد
        # نسخة الحدث هنا، وكتابة الـ domain بيتولاها المنادي (loan_commands)
        # لأنه صاحب معرفة الشكل. فشل الـ mirror بيتسجل بصوت عالي -- مش بيكسر.
        # الإنذار بيدق **بس** لما Supabase يكون متصل وترفض الكتابة. مش متصل
        # أصلاً = مفيش قراء بيقروا منه = مفيش انحراف = الإنذار كذب.
        from services import supabase_store as _sb_store
        if not _sb_store.insert_event(event):
            if _sb_store.is_configured():
                logger.error(
                    f"❌ mirror حدث الالتزام الذري لـ Supabase فشل -- القراء هيشوفوا "
                    f"نسخة أقدم لحد ما يتصلح: {event['event_id']}"
                )
            else:
                logger.debug(
                    f"mirror الحدث اتخطى -- Supabase مش متصل: {event['event_id']}"
                )

        logger.info(
            f"📒 event+write atomic commit: [{event['entity_key']}].{attribute} "
            f"({previous_value!r} -> {new_value!r}) id={event['event_id']} "
            f"domain={domain_collection}/{domain_document}"
        )
        return event["event_id"]
    except Exception as e:
        logger.error(f"❌ خطأ في الـ atomic commit (event+write): {e}")
        raise


def _supabase_first_events(fetch):
    """None من Supabase = مش قادر -- fallback للمسار القديم."""
    result = fetch()
    return result


def get_event(event_id: str) -> Optional[dict]:
    from services import supabase_store
    sb = supabase_store.get_event(event_id)
    if sb is not None:
        return None if sb.get("__missing__") else sb
    """جلب حدث واحد بالـ ID -- read-only. بيُستخدم للتحقق من evidence_event_ids لاحقًا."""
    from services.firebase_service import firestore_db
    if firestore_db is None or not event_id:
        return None
    try:
        doc = firestore_db.collection(EVENTS_COLLECTION).document(event_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logger.error(f"❌ خطأ في جلب الحدث {event_id}: {e}")
        return None


def _query_latest_events(field: str, value: str, limit: int) -> list:
    """أحدث `limit` حدث مطابق للفلتر، مرجّعين مرتبين تصاعديًا (الأقدم أولاً).

    ليه ده مهم (أوديت 2026-08-05): من غير order_by، Firestore بيرجع
    المستندات بترتيب الـ document id -- وإحنا بنستخدم UUID، يعني الترتيب
    عشوائي فعليًا. الـ limit كان بيقص عينة عشوائية **قبل** ترتيب بايثون،
    فـ "آخر حدث" مكانش آخر حدث. ده كان بيكسر تصنيف تعارض الأقساط وتقرير
    دورة حياة الأدوات وعدّادات التشخيص كلها بصمت.

    الاستعلام المرتّب محتاج composite index على (الحقل + occurred_at). لو
    الـ index لسه متعملش، بنرجع للاستعلام القديم مع تحذير واضح -- أحسن من
    إننا نرمي ونرجع فاضي (اللي كان هيفتح حارس التعارض).
    """
    from services.firebase_service import firestore_db
    from google.cloud.firestore_v1.base_query import FieldFilter
    from google.cloud.firestore_v1 import Query

    base = (
        firestore_db.collection(EVENTS_COLLECTION)
        .where(filter=FieldFilter(field, "==", value))
    )

    try:
        events = [
            d.to_dict() for d in
            base.order_by("occurred_at", direction=Query.DESCENDING).limit(limit).stream()
        ]
    except Exception as e:
        logger.warning(
            f"⚠️ استعلام مرتّب فشل على {field} (غالبًا composite index ناقص "
            f"على {field} + occurred_at) -- رجعت لاستعلام غير مرتّب: {e}"
        )
        events = [d.to_dict() for d in base.limit(limit).stream()]

    events.sort(key=lambda e: e.get("occurred_at", ""))
    return events


def get_events_for_entity(entity_type: str, entity_id: str, limit: int = 200) -> list:
    from services import supabase_store
    sb = supabase_store.get_events_for_entity(entity_type, entity_id, limit)
    if sb is not None:
        return sb
    """
    كل الأحداث المسجلة لـ entity معيّن، مرتبة زمنيًا (الأقدم أولاً).
    read-only. هتُستخدم في المرحلة 3 (Loan Conflict Observer) عشان تجيب
    كل الأحداث الخاصة بنفس identity_key وتصنّفها (new/duplicate/update/conflict).
    """
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []

    entity_key = f"{entity_type}:{entity_id}"
    try:
        return _query_latest_events("entity_key", entity_key, limit)
    except Exception as e:
        logger.error(f"❌ خطأ في جلب أحداث {entity_key}: {e}")
        return []


def get_events_by_type_and_attribute(entity_type: str, attribute: str, limit: int = 500) -> list:
    from services import supabase_store
    sb = supabase_store.get_events_by_type_and_attribute(entity_type, attribute, limit)
    if sb is not None:
        return sb
    """
    كل الأحداث من نوع entity + attribute معيّنين، عبر كل الـ entities (مش
    entity واحد زي get_events_for_entity) -- مرتبة زمنيًا. read-only.
    هتُستخدم من State Derivation Engine (Stage 5) عشان يجمع كل أحداث
    conflict_status مثلًا عبر كل الأقساط دفعة واحدة، بدل ما يلف على كل
    entity لوحده.
    """
    from services.firebase_service import firestore_db
    if firestore_db is None:
        return []

    key = f"{entity_type}:{attribute}"
    try:
        return _query_latest_events("type_attribute_key", key, limit)
    except Exception as e:
        logger.error(f"❌ خطأ في جلب أحداث {key}: {e}")
        return []
