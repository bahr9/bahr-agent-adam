# -*- coding: utf-8 -*-
"""
🔬 Tool Lifecycle Diagnostics -- معيار تشخيص دائم لكل أداة في آدم.
=====================================================
اتبنى بعد حادثة حقيقية (2026-07-27): آدم رد بجملة محادثة "الأداة دي مش
متاحة" لما اتطلب منه ينفّذ get_adam_self_state -- مع إن الأداة كانت مسجّلة
بالكامل (TOOLS + dispatch + tools=TOOLS الفعلي، اتأكد بالفحص المباشر). خلاصة
مهمة: **"مسجّلة" مش نفس معنى "قابلة للاستخدام فعليًا".** السبب الجذري الحقيقي
كان تعليمة قديمة في الـsystem prompt بتقول "استخدم request_verified_expression
بس" -- مكتوبة قبل ما get_adam_self_state يتبنى أصلًا، وده اتصلح في نفس
الالتزام ده. الملف ده هو البنية التحتية اللي بتضمن إن أي حادثة مشابهة
تتمسك فورًا بدليل، مش بتخمين.

خمس مراحل، كل واحدة قابلة للتحقق باستقلالية:
    Registration -> Payload Construction -> Model Tool Selection ->
    Runtime Execution -> Result Returned

Registration: services/capabilities_registry.py (موجودة أصلًا).
Payload Construction + Model Tool Selection: الجديد هنا -- بيتسجلوا كحدثين
    خفيفين في Event Store (entity_type="tool_lifecycle") قبل/بعد كل نداء
    حقيقي لـmessages.create() في ask_claude_agentic.
Runtime Execution + Result Returned: services/tool_health_engine.py +
    services/tool_failure_observer.py (موجودين أصلًا -- إعادة استخدام، صفر
    تكرار).

صفر LLM هنا. صفر تخزين لبيانات حساسة -- بس أسماء أدوات وstop_reason.
"""

import re

from services import event_store, capabilities_registry, tool_health_engine
from utils.logger import logger

PAYLOAD_ENTITY_ID = "_payload"
SELECTION_ENTITY_ID = "_selection"

# ============================================================
# Explicit Tool Execution Detection -- حادثة 2026-07-27 (تكملة)
# =====================================================
# دليل حقيقي (Railway logs): الأداة كانت مسجّلة، وفي الـpayload الفعلي،
# لكن الموديل رد بكلام محادثة (stop_reason=end_turn, selected_tools=[])
# بدل ما ينفّذ الأداة اللي أحمد طلبها صراحة بالاسم. الحل مش "نجبر كل حاجة"
# -- ده تصنيف حتمي ضيق (صفر LLM) بيمسك بس الحالة الواضحة: اسم أداة حقيقي
# اتكتب بالحرف + كلمة أمر ("استخدم"/"use"/"call"/...) في نفس رسالة المستخدم.
# ============================================================

EXPLICIT_TOOL_TRIGGER_WORDS = [
    "استخدم", "استعمل", "شغّل", "شغل", "نفّذ", "نفذ",
    "use", "call", "execute", "run",
]

# ============================================================
# Website Review Intent -- حادثة 2026-08-07
# =====================================================
# نفس نمط حادثة 2026-07-27، لكن أخطر: أحمد ميكتبش "view_website" بالاسم
# أبدًا (طلب طبيعي "شوف موقعنا وقولي رأيك")، فـdetect_explicit_tool_request
# فوق ماكانش هيمسكها أصلًا. وأخطر من كده: بعد أول رد ملفّق واحد ("شفت
# الموقع...")، كل رد تالي في نفس المحادثة كان بيبني على كذبته القديمة في
# الـhistory بدل ما يتحقق تاني -- أربع ردود متتالية بالدليل من Supabase
# (conversation_messages)، رغم تعليمة نصية صريحة في الـsystem prompt تقول
# "ناديها الأداة قبل أي رأي". التعليمات النصية وحدها مش كفاية لما الموديل
# عنده precedent قوي من رده هو نفسه في نفس المحادثة -- الحل زي 2026-07-27
# بالظبط: تصنيف حتمي (صفر LLM) بيفرض tool_choice، مش بيعتمد على "الموديل
# هيقرر صح المرة دي".
_WEBSITE_NOUNS = ["موقعنا", "الموقع", "موقعي", "موقع بحر", "bahr-designs-office"]
_WEBSITE_REVIEW_VERBS = [
    "شوف", "شوفي", "قيّم", "قيم", "راجع", "عاين", "افتح", "رأيك", "رايك",
]


def detect_website_review_intent(user_message: str) -> bool:
    """كشف حتمي لطلب "شوف الموقع وقولي رأيك" -- بدون اسم أداة صريح.

    شرطين: (1) كلمة تشاور على موقع Bahr Designs تحديدًا (مش أي موقع
    عمومًا -- عشان ميتفرضش على "شوف موقع المورد ده https://...")،
    (2) فعل مراجعة/رأي في نفس الرسالة. القصد: الحالة الضيقة اللي أحمد
    بيقصد بيها موقعه هو من غير ما يديله رابط -- ده اللي كان بيتلخبط.
    """
    if not user_message:
        return False
    has_noun = any(n in user_message for n in _WEBSITE_NOUNS)
    has_verb = any(v in user_message for v in _WEBSITE_REVIEW_VERBS)
    return has_noun and has_verb


def detect_explicit_tool_request(user_message: str, tool_names) -> str:
    """
    كشف حتمي (صفر LLM، صفر تخمين دلالي) لطلب صريح لتنفيذ أداة بعينها.
    شرطين لازم الاتنين سوا: (1) اسم الأداة يظهر بالحرف (word boundary) في
    رسالة المستخدم -- مش تشابه أو تخمين، (2) فيه كلمة أمر واضحة في نفس
    الرسالة. لو الاسم مش من ضمن tool_names الحقيقية أصلًا، أو مفيش كلمة
    أمر، بيرجع None -- مفيش فرض في الحالتين دول (نفس قاعدة "أداة غلط
    الاسم مايتفرضش" و"سؤال عادي مايتفرضش").
    """
    if not user_message:
        return None
    for name in tool_names:
        if re.search(rf"\b{re.escape(name)}\b", user_message) and any(
            trigger in user_message for trigger in EXPLICIT_TOOL_TRIGGER_WORDS
        ):
            return name
    return None


def record_payload_snapshot(tool_names: list) -> None:
    """
    يتنادى مباشرة *قبل* كل استدعاء حقيقي لـmessages.create() في
    ask_claude_agentic. بيسجّل حدث واحد بس (مش حدث لكل أداة -- 54 حدث لكل
    رسالة تليجرام كان هيضخّم Event Store من غير داعي حقيقي) فيه القايمة
    الكاملة اللي *فعليًا* هتتبعت -- ده الدليل المباشر على "Payload Construction".
    """
    try:
        event_store.record_event(
            entity_type="tool_lifecycle", entity_id=PAYLOAD_ENTITY_ID,
            attribute="payload_sent",
            new_value={"count": len(tool_names), "tool_names": sorted(tool_names)},
            source="system", actor="claude_service.ask_claude_agentic",
        )
    except Exception as e:
        logger.error(f"❌ فشل تسجيل payload_sent lifecycle event (مش حرج): {e}")

    logger.info(f"📦 Payload: {len(tool_names)} tool(s) sent to Claude: {', '.join(sorted(tool_names))}")


def record_model_selection(stop_reason: str, selected_tools: list) -> None:
    """
    يتنادى مباشرة بعد استلام الرد من Claude، قبل أي تنفيذ. بيوضّح صراحة
    "الموديل اختار يستخدم كذا" أو "الموديل قرر ميستخدمش أي أداة الدورة دي"
    -- بدل ما نسيب المحادثة تفترض حاجة مالهاش دليل.
    """
    try:
        event_store.record_event(
            entity_type="tool_lifecycle", entity_id=SELECTION_ENTITY_ID,
            attribute="model_selection",
            new_value={"stop_reason": stop_reason, "selected_tools": selected_tools},
            source="system", actor="claude_service.ask_claude_agentic",
        )
    except Exception as e:
        logger.error(f"❌ فشل تسجيل model_selection lifecycle event (مش حرج): {e}")

    if selected_tools:
        logger.info(f"🧠 Model selected tool(s): {', '.join(selected_tools)}")
    else:
        logger.info("🧠 Model chose not to use any tool this round.")


def _last_payload_included(tool_name: str, lookback: int = 20):
    """True/False لو فيه دليل، None لو مفيش أي payload snapshot اتسجل خالص لسه."""
    events = event_store.get_events_for_entity("tool_lifecycle", PAYLOAD_ENTITY_ID, limit=lookback)
    if not events:
        return None
    last = events[-1]
    return tool_name in (last.get("new_value") or {}).get("tool_names", [])


def _recently_selected(tool_name: str, lookback: int = 50):
    """True لو ظهرت في أي اختيار مسجّل مؤخرًا، False لو فيه سجلات لكن مافيهاش الأداة دي، None لو مفيش دليل خالص."""
    events = event_store.get_events_for_entity("tool_lifecycle", SELECTION_ENTITY_ID, limit=lookback)
    if not events:
        return None
    for e in reversed(events):
        if tool_name in (e.get("new_value") or {}).get("selected_tools", []):
            return True
    return False


def get_tool_lifecycle_status(tool_name: str) -> dict:
    """
    يجمع حالة الخمس مراحل لأداة معيّنة من الأدلة الحقيقية المسجّلة -- بيستخدم
    مباشرة capabilities_registry (Registration) وtool_health_engine
    (Execution/Result، إعادة استخدام صفر تكرار). القيم: True/False لو فيه
    دليل، None لو مفيش دليل كافٍ للحكم (مش "لأ" مُخترعة).
    """
    registry = capabilities_registry.get_registry()
    registered = tool_name in registry

    payload_included = _last_payload_included(tool_name) if registered else None
    model_selected = _recently_selected(tool_name) if registered else None

    execution_status = None
    if registered:
        evaluations = tool_health_engine.evaluate_all_tools()
        execution_status = evaluations.get(tool_name, {}).get("status")

    return {
        "tool_name": tool_name,
        "registered": registered,
        "payload_included": payload_included,
        "model_selected": model_selected,
        "execution_status": execution_status,
    }


def render_lifecycle_report(tool_name: str) -> str:
    """نص تشخيصي مباشر -- للمطوّر/أحمد، مش تقرير موجّه لـClaude. صفر LLM."""
    status = get_tool_lifecycle_status(tool_name)

    def _mark(value):
        if value is True:
            return "✅"
        if value is False:
            return "❌"
        return "—"  # مفيش دليل كافٍ للحكم لسه

    return "\n".join([
        f"Tool: {status['tool_name']}",
        f"Registration: {_mark(status['registered'])}",
        f"Payload: {_mark(status['payload_included'])}",
        f"Model Selected: {_mark(status['model_selected'])}",
        f"Execution: {status['execution_status'] or '—'}",
    ])


# ============================================================
# Tool Result Provenance / Conversation Consistency -- حادثة 2026-07-27
# (تكملة تانية): دليل حقيقي (إعادة إنتاج مباشرة) إن الموديل، في دورة لاحقة،
# ممكن يدّعي إن أداة حقيقية *مسجّلة فعليًا ونفّذت بنجاح قبل كده في نفس
# المحادثة* "مش موجودة" أو "كانت مُلفّقة" -- خصوصًا لما أحمد يلصق نتيجة
# أداة سابقة كرسالة عادية. السبب البنيوي: format_history_for_claude بيحوّل
# تاريخ المحادثة لنص عادي user/assistant بس -- بيرمي بنية tool_use/tool_result
# الحقيقية اللي كانت موجودة وقت التنفيذ الفعلي (مش متخزنة في Firestore
# أصلًا)، فالموديل في الدورة الجديدة معندوش أي إشارة بنيوية إن رد سابق كان
# فعلًا ناتج استدعاء أداة حقيقي. حل جذري كامل (تخزين tool_use/tool_result
# الكامل) خارج نطاق الإصلاح ده -- ده تعديل أوسع لسكيمة تخزين المحادثة. بدل
# كده: شبكة أمان حتمية أخيرة (heuristic، مش ضمان كامل -- نفس تصنيف فحوصات
# claim_validator.py) بتمسك الادّعاء الكاذب قبل ما يوصل لأحمد وتصححه.
# ============================================================

FALSE_UNAVAILABILITY_PATTERNS = [
    r"مش موجود[ةه]?", r"مش متاح[ةه]?", r"غير موجود[ةه]?", r"غير متاح[ةه]?",
    r"مالهاش وجود", r"لا يوجد", r"not available", r"doesn'?t exist",
    r"does not exist", r"unavailable",
]
FABRICATION_CLAIM_PATTERNS = [
    r"ملفّق[ةه]?", r"ملفق[ةه]?", r"مختلق[ةه]?", r"اخترعت", r"اخترعته",
    r"مش حقيقي[ةه]?", r"fabricated", r"made up", r"wasn'?t real", r"was not real",
]
_AVAILABILITY_PROXIMITY_WINDOW = 60


def guard_against_false_tool_unavailability_claims(reply_text: str, real_tool_names=None) -> str:
    """
    فحص حتمي أخير (heuristic -- مبني على قرب النص، مش تحليل دلالي كامل،
    نفس تصنيف فحوصات claim_validator.py) على *كل* رد خارج، بصرف النظر عن
    وجود pending verification من عدمه. بيدوّر على اسم أداة حقيقية (موجودة
    فعليًا في claude_service.TOOLS دلوقتي) ظاهر قريب من عبارة "مش موجودة/
    مش متاحة/مُلفّقة" -- تناقض مباشر مع الحقيقة (الأداة فعلًا مسجّلة). لو
    اتلقط، بيسجّل تحذير واضح ("contradiction prevented") ويضيف ملاحظة
    تصحيحية صريحة في الآخر -- بدون ما يمسح أو يعيد صياغة كلام الموديل
    الأصلي (نفس فلسفة verify_and_finalize: إضافة، مش محو).
    """
    if not reply_text:
        return reply_text

    if real_tool_names is None:
        from services.claude_service import TOOLS
        real_tool_names = {t["name"] for t in TOOLS}

    flagged = []
    for name in real_tool_names:
        for m in re.finditer(rf"\b{re.escape(name)}\b", reply_text):
            start = max(0, m.start() - _AVAILABILITY_PROXIMITY_WINDOW)
            end = min(len(reply_text), m.end() + _AVAILABILITY_PROXIMITY_WINDOW)
            nearby = reply_text[start:end]
            if any(re.search(p, nearby) for p in FALSE_UNAVAILABILITY_PATTERNS + FABRICATION_CLAIM_PATTERNS):
                flagged.append(name)
                break

    if not flagged:
        return reply_text

    flagged = sorted(set(flagged))
    logger.warning(
        f"⚠️ Contradiction prevented: reply claimed real registered tool(s) {flagged} "
        f"unavailable/fabricated -- these ARE registered right now"
    )
    label = "أداة حقيقية متاحة ومسجّلة فعليًا" if len(flagged) == 1 else "أدوات حقيقية متاحة ومسجّلة فعليًا"
    note = (
        "\n\n[ملاحظة دقة تلقائية]: " + "، ".join(f"'{n}'" for n in flagged) + " " + label +
        " -- أي كلام فوق بيقول عكس كده مش دقيق ومايتبنيش."
    )
    return reply_text + note
