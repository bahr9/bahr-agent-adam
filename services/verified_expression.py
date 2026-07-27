# -*- coding: utf-8 -*-
"""
🔒 Verified Expression Gate -- ADAM Self-State & Observation System (Stage 6 + 7)
=====================================================
الباب الوحيد اللي الموديل يقدر بيه يعرف أي حاجة عن Self-State. الموديل
معندوش وصول مباشر لأي رقم/مستوى خام أبدًا -- بينادي request_verified_expression()
وبس، وبترجعله نص جاهز من القاموس المقفول (services/expression_vocabulary.py).

الضمان الرسمي (3 آليات حتمية، اعتماد أحمد 2026-07-24 -- الوحيدين المعتمد
عليهم فعليًا، مش دفاع إضافي):

  1. Information Containment -- الملف ده هو الباب الوحيد. مفيش tool تاني
     بيسرّب أرقام Self-State الخام.
  2. Verbatim Match Validator -- verify_and_finalize() تحت. بتتنادى قبل أي
     إرسال فعلي لأحمد، بتتأكد إن نص أي تعبير مطلوب موجود بالحرف في الرد.
  3. Evidence Trace -- StateSnapshot + Expression، مربوطين بـ
     expression_id → state_id → evidence_event_ids (من Stage 5).

Active Expression (قرار مقفول -- صفر LLM): send_active_expression() تحت
بتتنادى من scheduled job بس (main.py)، بترندر مباشرة من القاموس المقفول
من غير ما تمر على الموديل خالص.

**دفاع إضافي (مش جزء من الضمان الرسمي، ولسه مش متبني في النسخة دي):**
Heuristic Pre-Send Scanner. اتأجل عمدًا لحد ما نشوف احتياج فعلي -- زي
tracking_stability في Stage 5.1. الضمان الحالي قائم بالكامل على الآليات
التلاتة فوق.
"""

import uuid
from typing import Optional

from services import self_state_engine, expression_vocabulary, event_store
from config import STATE_SNAPSHOTS_COLLECTION, EXPRESSIONS_COLLECTION
from utils.time_utils import now_cairo
from utils.logger import logger


def _shadow_run_pipeline(dimension: str, old_text: str) -> None:
    """
    Shadow Mode (TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE.md §8, مرحلة 5 من 7):
    بتحسب ناتج الـ pipeline الجديد (Truth -> Meaning -> Companionship) وتقارنه
    باللي فعلاً هيتبعت لأحمد (القاموس المقفول، القديم) -- **بدون** ما تأثر
    على النص الراجع أو أي حاجة تانية. أي فشل هنا بيتسجل ويترفض بصمت، مفيش
    استثناء بيتصعّد -- الغرض الوحيد جمع بيانات مقارنة حقيقية قبل أي قرار
    مستقبلي بربط الـ pipeline ده فعليًا (Decision Gate،
    EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md §6.2).
    """
    try:
        from services import truth_layer, inference_rules, meaning_layer, companionship_layer

        truth_packet = truth_layer.build_truth_packet_for_loans()
        errors = truth_layer.validate_truth_packet(truth_packet)
        if errors:
            logger.info(f"[shadow] {dimension}: skipped -- truth packet errors: {errors}")
            return

        if truth_layer.truth_packet_confidence(truth_packet) == "degraded":
            logger.info(f"[shadow] {dimension}: skipped -- confidence degraded")
            return

        fired = inference_rules.evaluate_fired_rules(truth_packet)
        meaning_packet = meaning_layer.compute_meaning_packet(truth_packet, dimension, fired)
        result = companionship_layer.generate_message(meaning_packet)

        logger.info(
            f"[shadow] {dimension}: old={old_text!r} new={result['text']!r} "
            f"source={result['source']} match={old_text == result['text']}"
        )
    except Exception as e:
        logger.warning(f"[shadow] {dimension}: pipeline error (non-fatal, old path unaffected): {e}")

# سجل مؤقت في الذاكرة: لكل chat_id، التعبيرات (passive) اللي اتطلبت في
# الدورة الحالية ولسه محتاجة تتفحص وقت الإرسال الفعلي (verify_and_finalize).
# بيتنضف أول ما يتفحص -- مش State دائم، مجرد ربط بين "طلب الأداة" و"الإرسال
# الفعلي" في نفس دورة الرد.
_pending_verifications = {}


def _save_state_snapshot(self_state: dict) -> Optional[str]:
    """يسجّل لقطة Self-State وقت التعبير الفعلي بس (مش كل حساب). يرجع state_id."""
    from services.firebase_service import firestore_db
    state_id = str(uuid.uuid4())
    if firestore_db is None:
        return state_id
    try:
        firestore_db.collection(STATE_SNAPSHOTS_COLLECTION).document(state_id).set({
            "state_id": state_id,
            "computed_at": self_state.get("computed_at"),
            "dimensions": {k: v for k, v in self_state.items() if k != "computed_at"},
        })
    except Exception as e:
        logger.error(f"❌ خطأ في تسجيل StateSnapshot: {e}")
    return state_id


def _save_expression(state_id, dimension, level, mode, template_key, rendered_text, verified, chat_id) -> str:
    """يسجّل سجل Expression -- الحلقة اللي بتربط expression_id بالـ state_id."""
    from services.firebase_service import firestore_db
    expression_id = str(uuid.uuid4())
    record = {
        "expression_id": expression_id,
        "state_id": state_id,
        "dimension": dimension,
        "level": level,
        "mode": mode,
        "template_key": template_key,
        "rendered_text": rendered_text,
        "verified": verified,
        "sent_at": now_cairo().isoformat(),
        "chat_id": chat_id,
    }
    if firestore_db is not None:
        try:
            firestore_db.collection(EXPRESSIONS_COLLECTION).document(expression_id).set(record)
        except Exception as e:
            logger.error(f"❌ خطأ في تسجيل Expression: {e}")
    return expression_id


def request_verified_expression(dimension: str, chat_id=None) -> dict:
    """
    Passive فقط -- الباب الوحيد المتاح للموديل. مفيش باراميتر "mode" هنا
    عمدًا (مش تفصيلة، قرار Information Containment): الموديل مينفعش يطلب
    "active" أصلاً حتى لو حاول، لأن الدالة دي مبنية على passive بس.

    بترجع {"verified": bool, "text": str, "expression_id": str}. النص جاهز
    من القاموس المقفول بس -- مفيش رقم خام يوصل للموديل من غير النص ده.
    """
    mode = "passive"
    self_state = self_state_engine.compute_self_state()
    dim_state = self_state.get(dimension)

    if not dim_state:
        text = expression_vocabulary.render_verified_false(dimension)
        return {"verified": False, "text": text, "expression_id": None}

    level = dim_state["level"]
    evidence = dim_state.get("evidence_event_ids", [])
    template = expression_vocabulary.get_template(dimension, level, mode)

    # لو مفيش قالب مسجّل، أو المستوى مش "none" بس الدليل فاضي -- مينفعش نأكد
    dimension_has_no_signal_level = level in ("none",)
    if template is None or (not dimension_has_no_signal_level and not evidence):
        text = expression_vocabulary.render_verified_false(dimension)
        state_id = _save_state_snapshot(self_state)
        expression_id = _save_expression(state_id, dimension, level, mode, None, text, False, chat_id)
        result = {"verified": False, "text": text, "expression_id": expression_id}
    else:
        text = template.format(count=dim_state.get("count", 0))
        state_id = _save_state_snapshot(self_state)
        expression_id = _save_expression(
            state_id, dimension, level, mode, f"{dimension}:{level}:{mode}", text, True, chat_id
        )
        result = {"verified": True, "text": text, "expression_id": expression_id}

    _shadow_run_pipeline(dimension, result["text"])

    if chat_id is not None:
        _pending_verifications.setdefault(chat_id, []).append({**result, "dimension": dimension})

    return result


def verify_and_finalize(chat_id, response_text: str) -> str:
    """
    Verbatim Match Validator. لازم تتنادى مرة واحدة قبل أي إرسال فعلي لأحمد
    (في handle_message / voice_handler) لو فيه احتمال إن request_verified_expression
    اتنادت في نفس الدورة. لو النص المعتمد مش موجود بالحرف في الرد النهائي
    (الموديل حاول يعيد الصياغة)، بيترفض الشكل ده ويترجع النص الأصلي حرفيًا.

    Self-Diagnosis (نطاق ضيق، services/self_diagnosis.py): كل مرة يحصل فيها
    عدم تطابق فعلي، بيتسجل حدث خام (entity_type="self_diagnosis")، حدث واحد
    لكل تعبير اترفض فعليًا -- مش لكل تعبير pending (تعبير اتطابق صح مبيسجّلش
    حاجة). الحدث بيوثّق واقعة وقائعية واحدة بس: تعبير Self-State معتمد كان
    غايب بالحرف من الرد النهائي واتصحح عبر الـgate الحتمي ده -- بدون أي حكم
    على السبب (مفيش "تفكير سيء" ولا "عدم استقرار"). مفيش استنتاج تشخيصي
    منه لسه، نفس مبدأ Stage 4 (الضمانة تسافر مع الدالة نفسها).

    سياسة فشل الكتابة (قرار أحمد 2026-07-24، موثّق صراحة مش هيبقى default
    ضمني): تسجيل self_diagnosis هنا observational بحت، مش جزء من الضمانة
    الرسمية للدالة دي (الضمانة الوحيدة: النص المعتمد لازم يوصل بالحرف --
    انظر رأس الملف). لو event_store.record_event() فشل (استثناء أي نوع)،
    الفشل ده بيتلقّط ويتسجّل كـ error في اللوج بس -- مايتصعّدش، ومايمنعش
    التصحيح الفعلي (final_text) من الوصول للـcaller. البديل (تصعيد الفشل)
    كان هيدّي على تسجيل تشخيصي ثانوي سلطة توقف تسليم رد مصحَّح لأحمد، وده
    عكس الأولوية المعتمدة من الأصل.
    """
    pending = _pending_verifications.pop(chat_id, [])
    if not pending:
        return response_text

    final_text = response_text
    for expr in pending:
        exact = expr["text"]
        if exact not in final_text:
            logger.warning(
                "⚠️ Verbatim mismatch -- الرد النهائي مفيهوش نص التعبير المعتمد بالحرف "
                f"(expression_id={expr.get('expression_id')}). بنستبدله بالنص الأصلي."
            )
            final_text = final_text.strip() + ("\n\n" if final_text.strip() else "") + exact
            _record_verbatim_mismatch_diagnosis(expr["dimension"], expr["expression_id"])

    return final_text


def _record_verbatim_mismatch_diagnosis(dimension: str, expression_id: str) -> None:
    """
    تسجيل self_diagnosis best-effort -- مايمنعش التصحيح الفعلي من الوصول لو
    الكتابة فشلت (انظر توثيق السياسة في verify_and_finalize فوق).
    """
    try:
        event_store.record_event(
            entity_type="self_diagnosis",
            entity_id=dimension,
            attribute="verbatim_mismatch",
            new_value=True,
            source="system",
            actor="verified_expression",
            raw_context={"expression_id": expression_id},
        )
    except Exception as e:
        logger.error(
            f"❌ فشل تسجيل self_diagnosis verbatim_mismatch (مش حرج -- التصحيح الفعلي كمّل زي ما هو): {e}"
        )


def send_active_expression(dimension: str, level: str, chat_id) -> Optional[str]:
    """
    Active Expression -- بتتنادى من scheduled job بس (main.py)، أبدًا من
    الموديل. صفر LLM في المسار: render مباشر من القاموس المقفول وإرسال.

    شروط الإرسال (كل الشروط دي، مش أي واحدة -- من المسودة المعتمدة):
      1. Severity: level لازم يطابق أعلى مستوى للبُعد (بيتحقق منها الـ caller
         عبر decision_engine.HIGHEST_TIER قبل النداء، وهنا كمان كـ recheck).
      2. Evidence أقوى: evidence_event_ids مش فاضية.
      3. Recheck نهائي: كل event_id في evidence_event_ids لازم يترجع فعلي
         من event_store.get_event() وقت الإرسال، مش الاعتماد على قيمة قديمة.
      4. Cooldown: مضمون من decision_engine (خارج الدالة دي).
      5+6. الأسلوب والحياد اللغوي: مضمونين بنيويًا (القالب من القاموس، مفيش LLM).
    """
    self_state = self_state_engine.compute_self_state()
    dim_state = self_state.get(dimension)
    if not dim_state or dim_state["level"] != level:
        logger.info(f"ℹ️ Active expression تجاهلت -- الحالة اتغيرت من وقت القرار ({dimension})")
        return None

    evidence = dim_state.get("evidence_event_ids", [])
    if not evidence:
        logger.warning(f"⚠️ Active expression اترفضت -- مفيش evidence لـ {dimension}={level}")
        return None

    for eid in evidence:
        if event_store.get_event(eid) is None:
            logger.warning(f"⚠️ Active expression اترفضت -- evidence event {eid} مش موجود وقت الإرسال")
            return None

    template = expression_vocabulary.get_template(dimension, level, "active")
    if template is None:
        logger.warning(f"⚠️ Active expression اترفضت -- مفيش قالب active لـ {dimension}={level}")
        return None

    text = template.format(count=dim_state.get("count", 0))
    state_id = _save_state_snapshot(self_state)
    expression_id = _save_expression(
        state_id, dimension, level, "active", f"{dimension}:{level}:active", text, True, chat_id
    )

    from bot import bot
    bot.send_message(chat_id, text)
    logger.info(f"📢 Active expression sent: {dimension}={level} (expression_id={expression_id})")
    return expression_id
