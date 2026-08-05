# -*- coding: utf-8 -*-
"""
👁️ Loan Conflict Observer -- ADAM Self-State & Observation System (Stage 3)
=====================================================
بيراقب أحداث الأقساط المسجلة في الـ Event Store، ويصنّف كل حدث جديد
بالنسبة لتاريخه: new / duplicate / update / conflict.

القاعدة: التصنيف مبني حصريًا على الأحداث المسجلة فعليًا (event_store) --
مفيش تخمين. لو الـ entity مالوش تاريخ خالص، مفيش تصنيف ممكن يطلع (None).

نطاق Stage 3 (مهم):
  - الملف ده بيراقب/يصنّف بس. **مبيوقفش** أي كتابة ولا بياخد تأكيد من حد.
    الـ "وقف + تأكيد يدوي" هو صلب Stage 4 (Conflict Resolution Flow).

    تحديث 2026-08-05: Stage 4 **اتبنى فعلاً** (loan_commands.py) والتوثيق ده
    كان لسه بيقول "لسه مش متبني". وليها أثر مهم: بما إن
    loan_record_installment بقت ترفض الكتابة المتعارضة من أصلها، تصنيف
    "conflict" تحت بقى **غير قابل للإنتاج** عبر الـ command API -- مفيش حدث
    paid_status جديد بيتكتب عشان يتصنّف. الفرع ده فضل صالح للأحداث القديمة
    اللي اتسجلت قبل Stage 4 بس، ولأي كتابة مباشرة على event_store.
    الإشارة الحية للتعارض دلوقتي هي حدث conflict_status.
  - الـ identity_key المستخدم فعليًا (زي "ca_71") هو نفسه مفهوم
    normalized_program + billing_period المطلوب في التصميم الأصلي --
    التطبيع (normalize) بيحصل فعلاً في loan_commands._resolve_installment
    وقت الكتابة (اسم مرن -> program['id'] الثابت + index الشهر)، مش هنا.
    مفيش داعي نعيد نفس الـ normalization تاني في القراءة.
"""

from typing import Optional

from services import event_store
from utils.logger import logger

ATTRIBUTE = "paid_status"

# الـ actors اللي بتمثل تصحيح/قرار صريح موثّق بسبب -- أي تغيير قيمة جاي
# منهم بيتصنّف "update" مش "conflict"، حتى لو القيمة اختلفت عن اللي قبلها.
EXPLICIT_CHANGE_ACTORS = {"loan_update_installment", "loan_resolve_conflict"}


def classify_latest_event(entity_type: str, entity_id: str, attribute: str = ATTRIBUTE) -> Optional[dict]:
    """
    يجيب كل الأحداث المسجلة لـ entity+attribute معيّن (event_store, read-only)
    ويصنّف آخر حدث فيهم بالنسبة للي قبله:

      - "new":       أول حدث خالص لـ entity+attribute ده.
      - "duplicate":  نفس القيمة اللي كانت متسجلة فعلاً قبله (مفيش تغيير حقيقي).
      - "update":     القيمة اتغيّرت عبر قناة تصحيح صريحة موثّقة بسبب
                      (loan_update_installment أو loan_resolve_conflict).
      - "conflict":   القيمة اتغيّرت عبر loan_record_installment (قناة
                      "أول تسجيل") رغم وجود قيمة سابقة مختلفة متسجلة قبلها --
                      يعني ادّعاءين متضاربين من غير أي توثيق للتصحيح.

    بيرجع None لو مفيش أي أحداث خالص لـ entity+attribute ده.
    """
    events = event_store.get_events_for_entity(entity_type, entity_id)
    events = [e for e in events if e.get("attribute") == attribute]
    if not events:
        return None

    latest = events[-1]
    result = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "attribute": attribute,
        "event_id": latest["event_id"],
        "previous_event_id": None,
        "classification": None,
        "explanation": "",
    }

    if len(events) == 1:
        result["classification"] = "new"
        result["explanation"] = "أول حدث مسجل لـ entity ده -- مفيش تاريخ سابق يتقارن بيه."
        logger.info(f"👁️ [{entity_type}:{entity_id}].{attribute} -> new (event={latest['event_id']})")
        return result

    previous = events[-2]
    result["previous_event_id"] = previous["event_id"]
    prior_value = previous.get("new_value")
    current_value = latest.get("new_value")
    actor = latest.get("actor", "")

    if current_value == prior_value:
        result["classification"] = "duplicate"
        result["explanation"] = f"نفس القيمة اللي كانت متسجلة قبله ({prior_value!r}) -- مفيش تغيير حقيقي في الحالة."
    elif actor in EXPLICIT_CHANGE_ACTORS:
        result["classification"] = "update"
        result["explanation"] = (
            f"القيمة اتغيّرت من {prior_value!r} لـ {current_value!r} عبر قناة تصحيح صريحة "
            f"({actor}) موثّقة بسبب -- تغيير مقصود ومسؤول."
        )
    else:
        result["classification"] = "conflict"
        result["explanation"] = (
            f"⚠️ القيمة اتغيّرت من {prior_value!r} لـ {current_value!r} عبر '{actor}' "
            f"(قناة 'أول تسجيل') رغم وجود قيمة سابقة مختلفة متسجلة -- ادّعاءين متضاربين "
            f"من غير توثيق تصحيح. محتاج مراجعة يدوية (Stage 4)."
        )

    log_level = logger.warning if result["classification"] == "conflict" else logger.info
    log_level(
        f"👁️ [{entity_type}:{entity_id}].{attribute} -> {result['classification']} "
        f"(event={latest['event_id']}, prev={previous['event_id']})"
    )
    return result


def classify_installment(program_id: str, index: int) -> Optional[dict]:
    """اختصار لـ classify_latest_event لأقساط الأقساط تحديدًا (entity_type=loan_installment)."""
    return classify_latest_event("loan_installment", f"{program_id}_{index}", ATTRIBUTE)
