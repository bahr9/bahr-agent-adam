# -*- coding: utf-8 -*-
"""
🧾 Loan Command API -- ADAM Self-State & Observation System (Stage 2 + 3 + 4 + 5)
=====================================================
الطبقة الوحيدة المسموح لها تكتب/تعدّل حالة دفع الأقساط.

القاعدة: أي كتابة لازم تسجل حدثها في الـ Event Store كخطوة إجبارية غير
قابلة للتخطي *جوه نفس الدالة* (عبر event_store.record_event_with_write) --
مش سطر منفصل حر في مكان الاستدعاء (_execute_tool). الضمانة بالشكل ده بتسافر
مع العملية نفسها بغض النظر مين وفين بينادي عليها مستقبلًا.

بعد كل كتابة، _commit() بتنادي loan_conflict_observer.classify_installment
(Stage 3) وتسجّل ملحوظة لو التصنيف طلع conflict -- ده شبكة أمان لحالة
الـ race condition النادرة (كتابتين متزامنتين عدّوا الفحص المسبق سوا)، مش
المسار الأساسي لمنع التعارض.

المسار الأساسي (Stage 4 -- Conflict Resolution Flow): loan_record_installment
بتفحص *قبل* أي كتابة لو القيمة الجديدة بتعارض آخر قيمة متسجلة فعليًا. لو
فيه تعارض -- **بتوقف تمامًا ومبتكتبش خالص** (مفيش حدث، مفيش كتابة)، وترجع
رسالة توضيح للموديل يعرضها على أحمد. الكتابة الفعلية في حالة التعارض ما
بتحصلش غير عبر loan_resolve_conflict بسبب صريح موثّق (تأكيد يدوي حقيقي).

Stage 5 (Self-State): حتى الرفض نفسه بيسجّل حدث خفيف منفصل تمامًا
(attribute="conflict_status", قيم "pending"/"resolved") -- عشان الـ State
Derivation Engine يقدر يشتق unresolved_conflict من دليل حقيقي، مش من فراغ.
ده على مسار (attribute) مختلف تمامًا عن paid_status، فمفيش تشابك مع Stage 3.

أداة loan_mark_paid القديمة اتشالت نهائيًا من TOOLS/_execute_tool في
claude_service.py. مفيش مسار كتابة تاني لحالة الأقساط غير الثلاث دوال هنا.

الفرق بين الثلاث دوال:
  - loan_record_installment: الاستخدام العادي -- تسجيل حالة دفع (أول مرة).
                              بتوقف تلقائيًا لو فيه تعارض (Stage 4).
  - loan_update_installment: تصحيح قيمة كانت متسجلة قبل كده -- محتاج سبب،
                              مبتوقفش (السبب نفسه هو التأكيد).
  - loan_resolve_conflict:    تطبيق قرار يدوي من أحمد لحل تعارض -- محتاج
                              سبب، مبتوقفش (ده المسار المخصص لحل التعارض).
"""

from services import loan_service, event_store
from config import LOANS_COLLECTION

_LOANS_DOC_ID = "paid_status"
ENTITY_TYPE = "loan_installment"


def _last_conflict_status(identity_key):
    """آخر قيمة متسجلة لـ attribute='conflict_status' لنفس الـ entity، أو None لو مفيش."""
    events = [
        e for e in event_store.get_events_for_entity(ENTITY_TYPE, identity_key)
        if e.get("attribute") == "conflict_status"
    ]
    return events[-1].get("new_value") if events else None


def _resolve_installment(program_name, month_key):
    """يرجع ((program, index, inst), None) عند النجاح، أو (None, رسالة_خطأ) عند الفشل."""
    program = loan_service._find_program(program_name)
    if not program:
        available = ", ".join(p["name"] for p in loan_service.PROGRAMS)
        return None, f"مش لاقي برنامج اسمه '{program_name}'. البرامج المتاحة: {available}"

    target_month = month_key or loan_service.get_current_month_key()
    for i, inst in enumerate(program["installments"]):
        if inst["date"] == target_month:
            return (program, i, inst), None

    return None, f"مفيش قسط لبرنامج {program['name']} في تاريخ {target_month}"


def _commit(program, index, inst, paid, source, actor, chat_id, raw_context, metadata=None):
    """الكتابة الفعلية الوحيدة -- حدث + كتابة domain في commit واحد ذري."""
    identity_key = f"{program['id']}_{index}"
    previous_value = loan_service.is_paid(program["id"], index)

    event_id = event_store.record_event_with_write(
        entity_type=ENTITY_TYPE,
        entity_id=identity_key,
        attribute="paid_status",
        new_value=paid,
        previous_value=previous_value,
        domain_collection=LOANS_COLLECTION,
        domain_document=_LOANS_DOC_ID,
        # لازم dict متداخل حقيقي {"paid": {key: value}} مش مفتاح نصي بنقطة
        # {"paid.key": value} -- .set(merge=True) بيعامل المفتاح اللي فيه نقطة
        # كاسم حرفي لحقل، مش كـ path متداخل (ده بس سلوك .update()، مش .set()).
        # الـ merge=True مع dict متداخل فعليًا بيعمل deep-merge صح من غير ما
        # يمسح باقي مفاتيح paid.* التانية.
        domain_data={"paid": {identity_key: paid}},
        source=source,
        actor=actor,
        chat_id=chat_id,
        raw_context=raw_context,
        metadata=metadata,
    )

    status = "مدفوع" if paid else "غير مدفوع"
    msg = f"تم تحديث قسط {program['name']} لشهر {inst['date']} ({inst['amount']} جنيه) → {status}"

    # مراقبة/تصنيف بعد الكتابة (Stage 3) -- مجرد إشارة/لوج، مبيوقفش ولا بياخد
    # تأكيد من حد (ده صلب Stage 4 اللي لسه مش متبني). الكتابة نفسها اتمت فعلاً.
    from services import loan_conflict_observer
    classification = loan_conflict_observer.classify_installment(program["id"], index)
    if classification and classification["classification"] == "conflict":
        msg += "\n⚠️ ملحوظة: القيمة دي بتعارض قيمة سابقة متسجلة لنفس القسط من غير توثيق تصحيح."

    return True, msg, event_id


def loan_record_installment(program_name, month_key=None, paid=True, chat_id=None):
    """
    الاستخدام العادي: تسجيل حالة دفع قسط.

    Stage 4 (Conflict Resolution Flow): قبل أي كتابة، بتتفحص القيمة المطلوبة
    مقابل آخر قيمة متسجلة فعليًا لنفس القسط. لو فيه قيمة سابقة مختلفة
    (يعني ادّعاءين متضاربين) -- **بتوقف ومبتكتبش خالص**، ومترجعش غير رسالة
    توضيح للتعارض. مفيش حدث بيتسجل، مفيش كتابة بتحصل. الكتابة الفعلية في
    الحالة دي مش بتحصل غير عبر loan_resolve_conflict بسبب صريح موثّق.
    """
    resolved, err = _resolve_installment(program_name, month_key)
    if err:
        return False, err, None
    program, index, inst = resolved
    identity_key = f"{program['id']}_{index}"

    prior_events = [
        e for e in event_store.get_events_for_entity(ENTITY_TYPE, identity_key)
        if e.get("attribute") == "paid_status"
    ]
    if prior_events:
        last_value = prior_events[-1].get("new_value")
        if last_value != paid:
            status_prev = "مدفوع" if last_value else "غير مدفوع"
            status_new = "مدفوع" if paid else "غير مدفوع"
            msg = (
                f"⚠️ تعارض: قسط {program['name']} لشهر {inst['date']} متسجل حاليًا "
                f"'{status_prev}'، والطلب الجديد بيقول '{status_new}'. "
                "مش هكتب أي حاجة من غير تأكيد يدوي صريح من أحمد -- اعرض عليه "
                "التعارض ده وسيبه يقرر، وبعدين استخدم loan_resolve_conflict "
                "بسبب واضح يوثّق قراره."
            )
            # Stage 5 (Self-State) -- الرفض نفسه دليل حقيقي لازم يتسجل، وإلا
            # مفيش أي أثر إن التعارض ده حصل أصلاً. attribute منفصل تمامًا
            # (conflict_status) عن paid_status -- مفيش كتابة domain مصاحبة،
            # مجرد حدث/إشارة (event لوحده، مش record_event_with_write).
            event_store.record_event(
                entity_type=ENTITY_TYPE,
                entity_id=identity_key,
                attribute="conflict_status",
                previous_value=_last_conflict_status(identity_key),
                new_value="pending",
                source="system",
                actor="loan_record_installment",
                chat_id=chat_id,
                raw_context={"program_name": program_name, "month_key": month_key, "requested_paid": paid, "current_value": last_value},
            )
            return False, msg, None

    return _commit(
        program, index, inst, paid,
        source="llm_tool", actor="loan_record_installment", chat_id=chat_id,
        raw_context={"program_name": program_name, "month_key": month_key, "paid": paid},
    )


def loan_update_installment(program_name, month_key=None, paid=True, reason="", chat_id=None):
    """تصحيح قيمة كانت متسجلة قبل كده -- سبب صريح إجباري."""
    if not reason or not reason.strip():
        return False, "محتاج سبب صريح للتعديل (reason) -- مينفعش تعديل قيمة متسجلة من غير توثيق السبب", None

    resolved, err = _resolve_installment(program_name, month_key)
    if err:
        return False, err, None
    program, index, inst = resolved

    ok, msg, event_id = _commit(
        program, index, inst, paid,
        source="llm_tool", actor="loan_update_installment", chat_id=chat_id,
        raw_context={"program_name": program_name, "month_key": month_key, "paid": paid, "reason": reason},
        metadata={"reason": reason, "is_correction": True},
    )
    if ok:
        msg += f" (تصحيح، السبب: {reason})"
    return ok, msg, event_id


def loan_resolve_conflict(program_name, month_key, paid, reason, chat_id=None):
    """
    تطبيق قرار يدوي من أحمد لحل تعارض بين ادعاءين متضاربين عن نفس القسط.
    دي الطريقة الوحيدة لتغيير قيمة كانت متسجلة قبلها بقيمة مختلفة *بعد* ما
    loan_record_installment توقفت ورفضت تكتب (Stage 4). السبب هنا هو نفسه
    توثيق "التأكيد اليدوي" اللي أحمد وافق عليه -- مفيش تأكيد تاني مطلوب.
    بتتعلّم بعلامة مميزة (source="manual_resolution") في الـ Event Store
    عشان الـ Observer يصنّفها "update" مش "conflict".
    """
    if not reason or not reason.strip():
        return False, "قرار حل التعارض لازم يوثّق السبب -- مينفعش من غير reason", None

    resolved, err = _resolve_installment(program_name, month_key)
    if err:
        return False, err, None
    program, index, inst = resolved

    identity_key = f"{program['id']}_{index}"

    ok, msg, event_id = _commit(
        program, index, inst, paid,
        source="manual_resolution", actor="loan_resolve_conflict", chat_id=chat_id,
        raw_context={"program_name": program_name, "month_key": month_key, "paid": paid, "reason": reason},
        metadata={"reason": reason, "resolved_by": "ahmed"},
    )
    if ok:
        # Stage 5 -- تسجيل "الحل" كدليل صريح يقفل أي conflict_status="pending"
        # سابق لنفس الـ entity. من غيره، الـ Derivation Engine هيفضل شايف
        # تعارض معلّق حتى بعد ما اتحل فعليًا.
        event_store.record_event(
            entity_type=ENTITY_TYPE,
            entity_id=identity_key,
            attribute="conflict_status",
            previous_value=_last_conflict_status(identity_key),
            new_value="resolved",
            source="manual_resolution",
            actor="loan_resolve_conflict",
            chat_id=chat_id,
            raw_context={"program_name": program_name, "month_key": month_key, "paid": paid, "reason": reason},
            metadata={"reason": reason, "resolved_by": "ahmed"},
        )
        msg = "✅ تم حل التعارض يدويًا: " + msg + f" (السبب: {reason})"
    return ok, msg, event_id
