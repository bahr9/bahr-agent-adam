# -*- coding: utf-8 -*-
"""
🪞 Self State Core -- ADAM Self-State & Observation System (Milestone: Self State Core)
=====================================================
أول شريحة من "آدم يعرف حالته الداخلية هو نفسه" -- مش الأقساط، مش أي مجال
تاني. خمس حقول بس، معتمدين حصريًا من غير أي حقل مُختلَق: Health Status,
Internal Warnings, Confidence, Current Mode, Diagnosis Summary.

**ممنوع صراحة في النطاق ده (قرار معتمد):** Current Goal, Current Task,
Active Session, Current Focus, Execution Progress, Blocked Operations,
Available Capabilities -- كل دول محتاجين بنية تحتية (Capabilities Registry،
Execution Tracker، Session/Task Model) مش موجودة في الكودبيز خالص. أي حقل
منهم هنا هيبقى حالة مُختلَقة (fabricated state)، وده بالظبط اللي المهمة دي
معمولة عشان تمنعه.

نفس فلسفة self_diagnosis.py/self_state_engine.py بالحرف:
  - صفر LLM هنا -- قواعد Python صريحة بس.
  - صفر تخزين -- كل حاجة بتتحسب "on the fly" من الأحداث + الحالة الحالية.
  - كل ادّعاء evidence-backed (evidence_event_ids أو تفسير صريح لغياب الدليل).
  - "Unknown" حالة شرعية من الدرجة الأولى -- لازم تفضل unknown لو الدليل
    مش موجود، مش تتحول افتراضيًا لـ "healthy"/"normal".

**التحقق (قرار معتمد -- Option A):** النص الكامل المُجمَّع (render_report)
بيتسجل كـ pending verification عبر verified_expression.register_pending_verification
-- بالظبط نفس آلية الأقساط (verify_and_finalize بيفرض تطابقه بالحرف في الرد
النهائي). صفر آلية تحقق موازية.

**تصحيح دلالي صغير (معتمد 2026-07-27، بعد مراجعة تشخيصية على بيانات حقيقية):**
(1) health_status/diagnosis_summary/confidence/current_mode كلهم دلوقتي معاهم
evidence_event_ids ظاهرة على مستوى الحقل نفسه، مش بس متداخلة جوه internal_warnings.
(2) كل عنصر في internal_warnings معاه "category" صريحة ("domain" أو "runtime")
-- توضيح للفصل المعماري الموجود أصلًا (health_status لسه مايشوفش self_state
خالص، زي ما هو من الأول)، صفر تغيير في العتبات أو في نص render_report.

**تكامل Tool Health (معتمد -- Runtime Capabilities & Tool Health V1):**
تحذيرات صحة الأدوات (services/tool_health_engine.py) بتتضاف لـ internal_warnings
بس (category="runtime")، وبتأثر على current_mode بنفس القاعدة الموجودة أصلًا
(أي warnings غير فاضية → attention_needed) -- **صفر تغيير في compute_current_mode
نفسها**. القراءة دي best-effort بحتة ومعزولة تمامًا عن آلية computation_errors/
confidence الحالية: فشلها (أو حتى غيابها) **لا** يُحتسب كخطأ في Self State
Core نفسها، ولا يُغيّر قيمة confidence -- عشان توسيع تعريف "الثقة" ده كان
هيعني إعادة تصميم لمعنى Confidence المعتمد بالفعل (ممنوع صراحة في نطاق
هذه المرحلة). **قرار تأجيل مقصود وموثّق:** health_status نفسها **لا** تتأثر
بـ Tool Health خالص -- تعريفها المعتمد يبقى مقصورًا على موثوقية خط أنابيب
التعبير (fallback/rejection/mismatch) بس. توسيعها لتشمل صحة الأدوات
العامة قرار حوكمة منفصل، غير مطروح هنا، ومُسجَّل صراحة في
RUNTIME_TOOL_HEALTH_V1.md كقرار تأجيل مقصود -- مش نسيان.
"""

from services import event_store, self_diagnosis, self_state_engine
from utils.time_utils import now_cairo
from utils.logger import logger

# ============================================================
# عتبات Version 1 -- مؤقتة، موثّقة صراحة (معتمدة 2026-07-27، مش حقيقة معمارية دائمة)
# أي تعديل مستقبلي لازم مراجعة وتوثيق صريح، مش تغيير صامت.
# ============================================================
FALLBACK_WATCH_THRESHOLD = 1        # >= 1 fallback في 30 يوم -> WATCH (لو مفيش DEGRADED)
REJECTION_DEGRADED_THRESHOLD = 3    # >= 3 رفض في 30 يوم -> DEGRADED
MISMATCH_DEGRADED_THRESHOLD = 1     # >= 1 عدم تطابق حرفي في 30 يوم -> DEGRADED

HEALTH_STATUS_LABELS = {
    "HEALTHY": "مستقرة",
    "WATCH": "تحت المراقبة",
    "DEGRADED": "متدهورة",
    "UNKNOWN": "مش معروفة",
}

MODE_LABELS = {
    "normal": "طبيعي",
    "attention_needed": "محتاج انتباه",
    "degraded": "متدهور",
    "unknown": "مش معروف",
}

CONFIDENCE_LABELS = {
    "full": "كامل",
    "degraded": "جزئي",
    "unknown": "مش معروف",
}


def _safe_call(fn, *args, **kwargs):
    """يرجع (نتيجة, خطأ). خطأ=None يعني نجح. صفر استثناء بيتسرب برّه الدالة دي."""
    try:
        return fn(*args, **kwargs), None
    except Exception as e:
        return None, str(e)


def _union_evidence(items: list) -> list:
    """يجمع evidence_event_ids من قايمة dicts (عدّادات أو تحذيرات) بدون تكرار، بترتيب ثابت."""
    ids = []
    for item in items:
        ids.extend(item.get("evidence_event_ids", []))
    return list(dict.fromkeys(ids))


def compute_health_status(fallback: dict, rejection: dict, mismatch: dict, diagnosis_ok: bool) -> dict:
    """
    HEALTHY | WATCH | DEGRADED | UNKNOWN -- عتبات Version 1 (قرار معتمد 2026-07-27):
      UNKNOWN  : الدليل (fallback/rejection/mismatch) ماقدرش يتقرا.
      DEGRADED : rejection.count >= 3 أو mismatch.count >= 1 (في آخر 30 يوم).
      WATCH    : fallback.count >= 1، ومفيش شرط DEGRADED متحقق.
      HEALTHY  : الثلاثة صفر، والدليل اتقرا صح.
    """
    if not diagnosis_ok:
        return {
            "status": "UNKNOWN",
            "explanation": "مش قادر أتأكد من صحة نظام التعبير دلوقتي -- فشلت قراءة أحداث التشخيص.",
        }

    if rejection["count"] >= REJECTION_DEGRADED_THRESHOLD or mismatch["count"] >= MISMATCH_DEGRADED_THRESHOLD:
        return {
            "status": "DEGRADED",
            "explanation": (
                f"{rejection['explanation']} {mismatch['explanation']}".strip()
            ),
        }

    if fallback["count"] >= FALLBACK_WATCH_THRESHOLD:
        return {"status": "WATCH", "explanation": fallback["explanation"]}

    return {"status": "HEALTHY", "explanation": "مفيش أي مؤشر خلل في نظام التعبير في آخر 30 يوم."}


def compute_confidence(errors: list) -> str:
    """
    full: صفر أخطاء. degraded: بعض القراءات فشلت. unknown: كل القراءات فشلت
    (أو مفيش قراءة اتحاولت أصلًا -- زي firestore_db is None).
    """
    if not errors:
        return "full"
    total_signals = 4  # fallback, rejection, mismatch, self_state
    if len(errors) >= total_signals:
        return "unknown"
    return "degraded"


def compute_internal_warnings(self_state, self_state_err, fallback, rejection, mismatch, diagnosis_ok) -> list:
    """
    قايمة تحذيرات evidence-backed -- كل بُعد من self_state_engine (لو level != "none")
    + كل عدّاد تشخيصي (لو count > 0)، كل واحد بمرجعه الأصلي (evidence_event_ids
    + explanation) زي ما هو، من غير صياغة جديدة. فشل جزئي في مصدر واحد
    مايمنعش باقي المصادر -- وبيظهر كـ "unavailable" صريح، مش بيتشال بصمت.

    كل تحذير دلوقتي معه "category" صريحة ("domain" أو "runtime") -- تصنيف
    بس، صفر تغيير في المعنى أو النص (render_report ماعندوش لمسة، لسه بيطبع
    نفس explanation بالحرف). ده بيوضّح الفصل المعماري الموجود أصلًا (health_status
    مايشوفش self_state خالص) بشكل صريح على مستوى كل تحذير فردي، مش بس ضمني
    من اسم الـsource.
    """
    warnings = []

    if self_state_err:
        warnings.append({
            "source": "loans_self_state",
            "category": "domain",
            "status": "unavailable",
            "explanation": "مش قادر أقرا حالة الأقساط الداخلية دلوقتي -- فشلت القراءة.",
        })
    else:
        for dim_name, dim in self_state.items():
            if dim_name == "computed_at":
                continue
            if dim.get("level") and dim["level"] != "none":
                warnings.append({
                    "source": dim_name,
                    "category": "domain",
                    "level": dim["level"],
                    "count": dim.get("count"),
                    "evidence_event_ids": dim.get("evidence_event_ids", []),
                    "explanation": dim["explanation"],
                })

    if not diagnosis_ok:
        warnings.append({
            "source": "self_diagnosis",
            "category": "runtime",
            "status": "unavailable",
            "explanation": "مش قادر أقرا بيانات تشخيص نظام التعبير دلوقتي -- فشلت القراءة.",
        })
    else:
        for source, counter in (("fallback_activation", fallback), ("validator_rejection", rejection), ("verbatim_mismatch", mismatch)):
            if counter["count"] > 0:
                warnings.append({
                    "source": source,
                    "category": "runtime",
                    "count": counter["count"],
                    "evidence_event_ids": counter["evidence_event_ids"],
                    "explanation": counter["explanation"],
                })

    return warnings


def compute_current_mode(health_status: str, warnings: list, confidence: str) -> str:
    """
    اشتقاق بحت -- صفر مصدر بيانات مستقل، صفر حالة مُختلَقة. الترتيب:
      confidence == "unknown"  -> "unknown"
      confidence == "degraded" -> "degraded"  (القراءة نفسها مش موثوقة بالكامل)
      health_status == "DEGRADED" -> "degraded"
      health_status == "WATCH" أو فيه warnings -> "attention_needed"
      غير كده -> "normal"
    """
    if confidence == "unknown":
        return "unknown"
    if confidence == "degraded":
        return "degraded"
    if health_status == "DEGRADED":
        return "degraded"
    if health_status == "WATCH" or warnings:
        return "attention_needed"
    return "normal"


def compute_diagnosis_summary(fallback, rejection, mismatch, diagnosis_ok) -> str:
    """نفس تجميع get_self_diagnosis_report بالظبط + الجملة الجديدة (verbatim mismatch)."""
    if not diagnosis_ok:
        return "مش قادر أجمّع ملخص التشخيص دلوقتي -- فشلت قراءة أحداث التشخيص."
    return f"{fallback['explanation']} {rejection['explanation']} {mismatch['explanation']}"


def compute_self_state_core() -> dict:
    """
    الدالة الأساسية -- بتحسب الخمس حقول سوا، فريش كل مرة، صفر تخزين. كل قراءة
    فرعية معزولة (try/except مستقل) عشان فشل واحدة مايمنعش الباقي.
    """
    fallback, err1 = _safe_call(self_diagnosis.compute_fallback_count)
    rejection, err2 = _safe_call(self_diagnosis.compute_validator_rejection_diagnosis)
    mismatch, err3 = _safe_call(self_diagnosis.compute_verbatim_mismatch_diagnosis)
    self_state, err4 = _safe_call(self_state_engine.compute_self_state)

    diagnosis_ok = not (err1 or err2 or err3)
    errors = [e for e in (err1, err2, err3, err4) if e]

    confidence = compute_confidence(errors)
    health = compute_health_status(fallback, rejection, mismatch, diagnosis_ok)
    warnings = compute_internal_warnings(self_state, err4, fallback, rejection, mismatch, diagnosis_ok)

    # تكامل Tool Health -- best-effort بحت، مش جزء من computation_errors/confidence
    # (قرار موثّق في docstring الملف: توسيع Confidence لهذا مش مطروح في المرحلة دي)
    try:
        from services import tool_health_engine
        warnings = warnings + tool_health_engine.get_tool_health_warnings()
    except Exception as e:
        logger.warning(f"⚠️ Self State Core: تعذّر قراءة Tool Health warnings (best-effort، مش هتأثر على confidence): {e}")

    current_mode = compute_current_mode(health["status"], warnings, confidence)
    diagnosis_summary = compute_diagnosis_summary(fallback, rejection, mismatch, diagnosis_ok)

    # تحقق الأدلة (تصحيح دلالي معتمد 2026-07-27): كل ادّعاء من الأربعة دول
    # لازم evidence_event_ids ظاهرة على مستواه هو، مش بس متداخلة جوه warnings.
    # health_status/diagnosis_summary مبنيين حصريًا من fallback+rejection+mismatch
    # (نفس القاعدة المعمارية اللي health_status ماعندهوش وصول لـself_state خالص).
    # current_mode/confidence بيعتمدوا على الاتنين (التشخيص + كل الـwarnings)،
    # فدليلهم اتحاد الاتنين سوا.
    diagnosis_evidence = _union_evidence([fallback, rejection, mismatch]) if diagnosis_ok else []
    mode_and_confidence_evidence = list(dict.fromkeys(diagnosis_evidence + _union_evidence(warnings)))

    return {
        "health_status": health["status"],
        "health_status_explanation": health["explanation"],
        "health_status_evidence_event_ids": diagnosis_evidence,
        "internal_warnings": warnings,
        "confidence": confidence,
        "confidence_evidence_event_ids": mode_and_confidence_evidence,
        "current_mode": current_mode,
        "current_mode_evidence_event_ids": mode_and_confidence_evidence,
        "diagnosis_summary": diagnosis_summary,
        "diagnosis_summary_evidence_event_ids": diagnosis_evidence,
        "computed_at": now_cairo().isoformat(),
        "computation_errors": errors,
    }


# تصحيح مؤكَّد (2026-07-27، اكتُشف بإعادة إنتاج حقيقية للحادثة): الثلاثة
# مصادر دول (fallback_activation/validator_rejection/verbatim_mismatch) بيغطّيهم
# diagnosis_summary بالكامل بالفعل (compute_diagnosis_summary بيلصق تفسيرهم
# التلاتة دايمًا، بصرف النظر عن العدد). لو سابناهم كمان في نشرة internal_warnings
# لما count>0، نفس جملة التفسير بتتكرر حرفيًا مرتين في نفس التقرير -- ده اللي
# حصل فعليًا (تأكد بإعادة إنتاج مباشرة). الاستبعاد هنا عرض بس -- الداتا
# نفسها (compute_internal_warnings) لسه فيها الأدلة الثلاثة كاملة لأي مستهلك
# تاني (current_mode evidence union، اختبارات Tool Health، إلخ).
_DIAGNOSIS_SUMMARY_SOURCES = {"fallback_activation", "validator_rejection", "verbatim_mismatch"}


def render_report(core: dict) -> str:
    """
    نص عربي واحد متماسك -- ده اللي بيترجع للموديل، وده نفسه اللي بيتسجل كـ
    pending verification (Option A). كتلة واحدة، مش خمس شظايا منفصلة --
    نفس حبيبة التحقق اللي request_verified_expression شغالة بيها (نص واحد
    لكل نداء).
    """
    lines = [
        f"الحالة: {HEALTH_STATUS_LABELS[core['health_status']]}",
        f"الوضع الحالي: {MODE_LABELS[core['current_mode']]}",
        f"مستوى الثقة في القراءة دي: {CONFIDENCE_LABELS[core['confidence']]}",
    ]

    # صفر تكرار: نطبع بس تحذيرات مش مغطاة أصلًا بالحرف جوه diagnosis_summary تحت
    renderable_warnings = [
        w for w in core["internal_warnings"] if w.get("source") not in _DIAGNOSIS_SUMMARY_SOURCES
    ]
    if renderable_warnings:
        lines.append("تحذيرات داخلية:")
        for w in renderable_warnings:
            lines.append(f"- {w['explanation']}")
    elif not core["internal_warnings"]:
        lines.append("مفيش أي تحذيرات داخلية دلوقتي.")

    lines.append(core["diagnosis_summary"])

    return "\n".join(lines)
