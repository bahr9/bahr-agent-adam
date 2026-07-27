# -*- coding: utf-8 -*-
"""
🩺 Self-Diagnosis -- ADAM Self-State & Observation System (Architecture v2)
=====================================================
Domain جديد يستخدم نفس بنية Truth→Meaning الموجودة فعليًا، لكن موضوعه حالة
آدم أثناء التفكير (reasoning) نفسه -- مش الأقساط. نفس الفصل المعتمد
(CONSTITUTION.md، إجابة السؤال 5) بيتطبّق هنا حرفيًا:

  - أحداث خام (raw reasoning events) -- ملاحظة وتطبيع وقائعي بحت، بلا حكم
    على الأهمية. مسجَّلة في Event Store (entity_type="self_diagnosis")
    عند حدود التنفيذ الحتمية (deterministic execution boundary) اللي
    الحدث بيتلاحظ عندها مباشرة -- مش مربوطة بملف واحد بعينه. حاليًا
    الحدود دي موجودة في مكانين: services/companionship_layer.py (رفض
    Claim Validator/fallback) وservices/verified_expression.py (عدم
    تطابق Verbatim Match Validator) -- نفس مبدأ Stage 4 ("الضمانة تسافر
    مع الدالة نفسها بغض النظر مين بينادي عليها").
  - استنتاجات تشخيصية (diagnostic conclusions) -- مشتقة من الأحداث الخام
    دي، ولازم ترجع لها evidence_event_ids حقيقية دايمًا. الملف ده يوفّرها.

نطاق حالي (ضيق عمدًا، زي tracking_stability -- Stage 5.1 بالظبط):
  - fallback_activation -- عدد مرات تفعيل الـfallback (فشل التحقق مرتين
    متتاليتين) في آخر 30 يوم، عبر كل الأبعاد (compute_fallback_count).
  - validator_rejection -- استنتاج تشخيصي مجمّع بالنوع (deterministic/
    heuristic، نفس تصنيف claim_validator.py) في آخر 30 يوم، عبر كل الأبعاد
    (compute_validator_rejection_diagnosis). محايد بالتصميم -- عدد رفض
    مرتفع مش مفسَّر هنا كـ"تفكير سيء" أو "عدم استقرار الموديل" (قرار صريح
    من أحمد 2026-07-24)، مجرد رصد وقائعي.
  - verbatim_mismatch -- كل مرة الـVerbatim Match Validator (verify_and_finalize
    في services/verified_expression.py) بيلاقي إن تعبير Self-State معتمد
    مش موجود بالحرف في الرد النهائي، فبيصححه. الحدث الخام مسجَّل، مفيش
    استنتاج تشخيصي منه لسه -- يُضاف لاحقًا لو ظهر احتياج فعلي، مش الآن
    (نفس نمط validator_rejection وقت ما كان لسه غير مشخَّص).
  - tool_relevant_but_skipped -- مؤجَّل رسميًا (قرار أحمد 2026-07-24)، مش
    "خطوة تالية" عادية زي ما كان متصوَّر الأول. اتفحص صراحة قبل أي كود
    وطلع غير قابل للرصد حاليًا بالكامل، مش مجرد نقص تتبع بسيط:
      1. services/claude_service.py::TOOLS (أكتر من 40 أداة) بترسل كاملة
         مع كل رسالة بدون أي فلترة حسب الموضوع -- تعريف "الأداة كانت متاحة
         ومتنادتش" trivial وصحيح على ~39 أداة في كل رسالة تقريبًا، صفر قيمة
         تشخيصية.
      2. التعريف المفيد فعليًا ("الموديل شاف أداة معينة relevant وقرر ميستخدمهاش")
         محتاج مسار reasoning ملحوظ -- وده مش موجود: الـ thinking blocks (لما
         تتفعل) بتتقرا وبعدين تتجاهل صراحة في claude_service.py، صفر تسجيل.
      3. البديل التاني (heuristic خارجي يحدد "السؤال ده كان لازم يستخدم فيه
         أداة X") هيكرر بالظبط نفس فخ قايمة مرادفات "محلولة/محسومة" في
         claim_validator.py -- قايمة patterns هتفضل ناقصة وهتكبر بلا نهاية.

    القرار المتفَّق عليه: نفس مبدأ Evidence Log بتاع قرار Level A/B
    (EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md) -- مفيش instrumentation
    لسيناريو فشل افتراضي (hypothetical) قبل ما يبقى فيه دليل تنفيذي حقيقي
    إنه مشكلة متكررة فعليًا في الإنتاج. أي حل (self-report مُهيكَل من
    الموديل، أو أي آلية عقد جديدة) هيوسّع المعمارية المجمّدة الحالية،
    فمش هيتبنى من غير مناقشة صريحة ودليل إنتاجي يبرره -- مش دلوقتي.

قيد بنيوي موثّق (حد معماري حالي، مش خطأ محتاج إصلاح الآن): الأحداث الخام
الحالية (validator_rejection، fallback_activation) مفيهاش correlation ID
يربط المحاولة الأولى والتانية وتفعيل الـfallback من نفس عملية توليد واحدة
(نفس استدعاء generate_message). ده مش عائق على أي عدّ بسيط (زي count أو
by_type فوق)، لكنه هيبقى لازم قبل أي استنتاج مستقبلي من نوع "نسبة نجاح
إعادة المحاولة" (retry recovery rate) -- محتاج نعرف بالظبط إن محاولة 2
نجحت/فشلت *لنفس* محاولة 1 المرفوضة، مش مجرد عدّ إجمالي. مش هيتضاف دلوقتي
استباقيًا (طلب أحمد صراحة) -- هيتضاف فقط لما استنتاج فعلي يحتاجه.
"""

from datetime import datetime, timedelta

from services import event_store
from utils.time_utils import now_cairo

ENTITY_TYPE = "self_diagnosis"
FALLBACK_WINDOW_DAYS = 30


def compute_fallback_count(window_days: int = FALLBACK_WINDOW_DAYS) -> dict:
    """
    عدد مرات تفعيل fallback (فشل التحقق مرتين متتاليتين في Companionship)
    في آخر N يوم، عبر كل الأبعاد. نفس شكل tracking_stability بالظبط --
    count + evidence_event_ids + explanation، بدون تخمين ولا تفسير سلبي.

    الاسم مُصحَّح عمدًا (كان compute_fallback_rate): ده عدّاد داخل نافذة
    زمنية، مش rate حقيقي -- "rate" يحتاج مقام (زي إجمالي محاولات التوليد)
    مش متوفر لسه. "count" هو الوصف الدقيق لما بترجعه الدالة فعليًا.
    """
    events = event_store.get_events_by_type_and_attribute(ENTITY_TYPE, "fallback_activation")
    cutoff = now_cairo() - timedelta(days=window_days)
    recent = [e for e in events if datetime.fromisoformat(e["occurred_at"]) >= cutoff]

    count = len(recent)
    return {
        "count": count,
        "evidence_event_ids": [e["event_id"] for e in recent],
        "explanation": (
            f"{count} مرة اتفعّل فيها fallback في آخر {window_days} يوم -- ملاحظة موضوعية عن تكرار الحاجة للشبكة الأخيرة"
            if count else f"مفيش أي تفعيل fallback في آخر {window_days} يوم"
        ),
    }


def compute_verbatim_mismatch_diagnosis(window_days: int = FALLBACK_WINDOW_DAYS) -> dict:
    """
    عدد مرات اكتشاف الـVerbatim Match Validator (verify_and_finalize في
    services/verified_expression.py) لعدم تطابق حرفي بين تعبير Self-State
    معتمد والرد النهائي، في آخر N يوم، عبر كل المصادر (الأقساط وSelf State
    Core سوا -- الحدث نفسه بمصدر واحد بغض النظر عن الـdimension). نفس شكل
    compute_fallback_count بالظبط -- count + evidence_event_ids + تفسير
    محايد. هذا يقفل الفجوة الموثّقة صراحة في docstring الملف ("مفيش استنتاج
    تشخيصي منه لسه -- يُضاف لاحقًا لو ظهر احتياج فعلي") -- Self State Core
    هو الاحتياج الفعلي ده، ولا كتابة جديدة اتضافت هنا -- الأحداث بتتسجل
    فعلًا من قبل (verified_expression._record_verbatim_mismatch_diagnosis).
    """
    events = event_store.get_events_by_type_and_attribute(ENTITY_TYPE, "verbatim_mismatch")
    cutoff = now_cairo() - timedelta(days=window_days)
    recent = [e for e in events if datetime.fromisoformat(e["occurred_at"]) >= cutoff]

    count = len(recent)
    return {
        "count": count,
        "evidence_event_ids": [e["event_id"] for e in recent],
        "explanation": (
            f"{count} مرة اترصد فيها عدم تطابق حرفي بين تعبير معتمد والرد النهائي في آخر {window_days} يوم -- الـVerbatim Match Validator صححها فورًا"
            if count else f"مفيش أي عدم تطابق حرفي في آخر {window_days} يوم"
        ),
    }


def compute_validator_rejection_diagnosis(window_days: int = FALLBACK_WINDOW_DAYS) -> dict:
    """
    استنتاج تشخيصي عن رفض claim_validator لمحاولات توليد Companionship، عبر
    كل الأبعاد، في آخر N يوم. يرجع count (عدد أحداث الرفض)، by_type (توزيع
    الأخطاء حسب نوعها -- deterministic/heuristic، نفس تصنيف claim_validator.py
    بالظبط، عدّ على مستوى الخطأ الفردي مش الحدث)، evidence_event_ids، وتفسير
    محايد.

    محايد بالتصميم عمدًا (طلب أحمد صراحة 2026-07-24): عدد رفض مرتفع ممكن
    يرجع لأسباب مختلفة كتير (تنويع أسلوبي طبيعي، فحص heuristic ضيق جدًا،
    Slot جديد لسه الموديل بيتعلم استخدامه...) -- الدالة دي بترصد الواقعة
    فقط، وممنوع تستنتج منها "تفكير سيء" أو "عدم استقرار الموديل".

    قيد بنيوي موثّق (انظر docstring الملف): مفيش correlation ID يربط محاولة
    1 ومحاولة 2 من نفس التوليد -- الـcount هنا عدّ إجمالي مستقل لكل محاولة،
    مش مربوط بمحاولات بعض. كافي للاستنتاج الحالي، مش كافي لأي "نسبة نجاح
    إعادة محاولة" مستقبلية.
    """
    events = event_store.get_events_by_type_and_attribute(ENTITY_TYPE, "validator_rejection")
    cutoff = now_cairo() - timedelta(days=window_days)
    recent = [e for e in events if datetime.fromisoformat(e["occurred_at"]) >= cutoff]

    by_type = {}
    for e in recent:
        for error in e["new_value"]:
            by_type[error["type"]] = by_type.get(error["type"], 0) + 1

    count = len(recent)
    breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(by_type.items()))
    return {
        "count": count,
        "by_type": by_type,
        "evidence_event_ids": [e["event_id"] for e in recent],
        "explanation": (
            f"{count} محاولة توليد اترفضت من claim_validator في آخر {window_days} يوم"
            + (f" ({breakdown})" if breakdown else "")
            + " -- ملاحظة وقائعية بحتة، بدون أي حكم على سبب الرفض"
            if count else f"مفيش أي رفض من claim_validator في آخر {window_days} يوم"
        ),
    }
