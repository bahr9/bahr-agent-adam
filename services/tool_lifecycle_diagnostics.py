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
# أسماء أقسام موقع Bahr Designs نفسها -- امتداد للحادثة (نفس اليوم بعد
# ساعة): "شوف الستايلات وقسم الكاميرا" مفيهاش كلمة "موقع" أصلًا، فالكاشف
# الأصلي ما مسكهاش، والموديل رجع لفّق تاني (selected_tools=[] بالدليل).
# طلب مراجعة قسم من أقسام الموقع = طلب مراجعة موقع، بنفس الفرض بالظبط.
_WEBSITE_SECTION_WORDS = [
    "الستايلات", "ستايلات", "البورتفوليو", "التخصصات", "الهيرو", "الفوتر",
    "قسم الكاميرا", "قسم الكاميرات", "بتاع الكاميرا", "قسم البث",
    "styles", "livecam", "portfolio",
]
_WEBSITE_REVIEW_VERBS = [
    "شوف", "شوفي", "قيّم", "قيم", "راجع", "عاين", "افتح", "رأيك", "رايك",
]


def detect_website_review_intent(user_message: str) -> bool:
    """كشف حتمي لطلب "شوف الموقع/قسم منه وقولي رأيك" -- بدون اسم أداة صريح.

    شرطين: (1) كلمة تشاور على موقع Bahr Designs تحديدًا أو قسم من أقسامه
    (مش أي موقع عمومًا -- عشان ميتفرضش على "شوف موقع المورد ده https://...")،
    (2) فعل مراجعة/رأي في نفس الرسالة. القصد: الحالة اللي أحمد بيقصد بيها
    موقعه هو من غير ما يديله رابط -- ده اللي كان بيتلخبط.
    """
    if not user_message:
        return False
    has_noun = any(n in user_message for n in _WEBSITE_NOUNS) or any(
        s in user_message for s in _WEBSITE_SECTION_WORDS
    )
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


# ============================================================
# سياق الدورة الواحدة (2026-08-10، الجولة التانية)
# ============================================================
# الحارس اللي فوق كان بيسأل `_recently_selected` -- نافذة **عامة** على
# آخر ن اختيار مسجّل في المخزن كله. والنافذة دي بتتلوّث من أي نداء تاني:
# نداءين تجربة الساعة 8:35 و8:43 حطّوا get_project_details في آخر ستة،
# فلما أحمد سأل 8:57 الحارس شاف "اتنادت مؤخرًا" وسكت -- والرد الكاذب عدّى.
#
# يعني الحارس كان بيبطل يشتغل بالظبط لما النظام يتستخدم. ده مش ضبط
# حساسية، ده سؤال غلط من الأساس: المهم مش "اتنادت في آخر ستة"، المهم
# "اتنادت **في الرد ده**".
#
# السياق هنا بيتفتح في أول `ask_claude_agentic` وبيتقفل بعد ما الرد
# يتفحص. مفيش استمرار بين الدورات بالقصد.

_turn_context = {}          # chat_id -> {"question": str, "tools": set()}


def begin_turn(chat_id, user_text=""):
    """بداية دورة رد جديدة. بيمسح أي سياق قديم لنفس المحادثة."""
    _turn_context[chat_id] = {"question": user_text or "", "tools": set()}


def note_turn_selection(chat_id, tool_names):
    """أدوات الموديل اختارها في جولة جوه الدورة الحالية."""
    ctx = _turn_context.get(chat_id)
    if ctx is not None:
        ctx["tools"].update(tool_names or [])


def turn_tools(chat_id):
    """أدوات الدورة الحالية، أو None لو مفيش سياق مفتوح.

    None مهمة: معناها "مش عارف" مش "مفيش أدوات اتنادت". الحارس لازم
    يسكت عند None بدل ما يفترض إن مفيش نداء حصل -- نفس قاعدة `[]`.
    """
    ctx = _turn_context.get(chat_id)
    return set(ctx["tools"]) if ctx is not None else None


def turn_question(chat_id):
    ctx = _turn_context.get(chat_id)
    return ctx["question"] if ctx is not None else ""


def end_turn(chat_id):
    _turn_context.pop(chat_id, None)


# ============================================================
# حارس: "مفيش بيانات" ادعاء زي أي ادعاء (2026-08-10)
# ============================================================
# الحادثة: أحمد سأل عن «قيمة أعمال التعديلات المعمارية في مقايسة التأسيس
# لمشروع عصام فرج». آدم رد «مفيش أي بند مقايسة أو تكلفة تأسيس مسجل هناك»،
# واخترع سبب: «BAHR OS بيتابع حالة المشروع مش تفاصيل المقايسات المالية
# بهذا العمق».
#
# الحقيقة: 24 بند تأسيس بإجمالي 326,130 موجودين في نفس اللحظة، و
# get_project_details بترجّعهم. سجل tool_lifecycle بيقول التسلسل بالحرف:
#
#     get_bahr_projects -> end_turn -> get_project_file -> end_turn
#
# get_project_details **عمرها ما اتنادت**. يعني آدم نفى وجود بيانات موجودة
# في أداة هو نفسه عنده، من غير ما يفتحها.
#
# ليه: البرومبت فيه قاعدة إن أي اسم مشروع يودّي على get_project_file
# فورًا -- وده مخزن **ملفات التصميم** (فراغات/أبعاد/قرارات)، مش مقايسات
# BAHR OS. لقاه فاضي، وقايمة get_bahr_projects كان شكلها شامل، فالنتيجة
# "مفيش".
#
# ده نفس فخ الـ[] بس على مستوى المحادثة مش الاستعلام: "مقدرتش أقرا"
# اتحوّلت لـ"مفيش"، والفرق بين الاتنين هو الفرق بين ادّعاء صحيح وادّعاء
# كاذب. والاختراع اللي جا بعده (قاعدة عن BAHR OS مالهاش أصل في أي مكان)
# هو النمط المعروف: الموديل بيبرّر نتيجة غلط بقاعدة بيألّفها.
#
# الحارس ده حتمي وبيضيف مايمسحش -- نفس فلسفة
# guard_against_false_tool_unavailability_claims فوق.

# نفي وجود بيانات. القايمة اتوسّعت بعد الجولة التانية (2026-08-10):
# النسخة الأولى فاتها "مفيهوش" و"مش موجود عندي" و"مش سجلت"، وكل واحدة
# منهم كانت في رد كاذب حقيقي وصل لأحمد.
_NO_DATA_PATTERNS = [
    r"مفيش أي", r"مفيش بند", r"مفيش بنود", r"مفيش تفاصيل", r"مفيش مقايس",
    r"مفيش تكلف", r"مش مسجل", r"مش متسجل", r"مالهوش بنود", r"لا يوجد أي",
    r"مفيش أسعار", r"مفيش داتا", r"مفيش بيانات", r"مفيش سعر", r"مفيش حاجة",
    r"مفيهوش", r"مفيهاش", r"مش موجود عندي", r"مش موجود في أي مكان",
    r"مش سجلت", r"معنديش", r"ماعنديش", r"مش لاقي",
]

# ⚠️ الموضوع بيتحدد من **سؤال أحمد**، مش من كلمات رد آدم.
#
# النسخة الأولى كانت بتدوّر على مفردات المقايسة في الرد نفسه، فرد زي
# "ملف المشروع مفيهوش أي بيانات عن تكييفات ولا تكلفتها" كان بيعدّي: مفيش
# فيه كلمة "مقايسة" ولا "بند". لكن السؤال كان «صرف التكييفات كلف كام عند
# عصام فرج» -- سؤال تكلفة عن مشروع، وده كل اللي محتاجينه.
#
# القاعدة: سؤال فيه تكلفة/سعر/صرف + اسم مشروع أو عميل، ورد بينفي، وأداة
# المقايسات ماتنادتش في نفس الدورة = ادّعاء من غير قراءة.
_COST_QUESTION_PATTERNS = [
    r"تكلف", r"كلف", r"سعر", r"أسعار", r"اسعار", r"بكام", r"كام",
    r"قيمة", r"مقايس", r"بند", r"إجمالي", r"اجمالي", r"صرف", r"ميزاني",
    r"فلوس", r"جنيه", r"حصر", r"كميات",
]

# اختراع قواعد عن قدرات BAHR OS. آدم مالوش أي مصدر يعرف منه إيه اللي
# BAHR OS بيسجّله وإيه اللي مابيسجّلهوش -- فأي جملة من الشكل ده تأليف.
# والتأليف هنا أخطر من النفي نفسه: تفسير معقول بيخلي النفي يبان متسق،
# فمحدش يشك فيه ومحدش يفتح الأداة يتأكد.
_INVENTED_CAPABILITY_PATTERNS = [
    r"BAHR OS بيتابع",
    r"BAHR OS مش بي",
    r"BAHR OS مابي",
    r"BAHR OS بس بي",
    r"Bahr OS بيتابع",
    r"Bahr OS مش بي",
    r"بحر أو إس مش",
    r"النظام مش بيسجل",
    r"النظام مبيسجلش",
    r"مش بيسجّل تفاصيل مالية",
    r"مش بيسجل تفاصيل مالية",
]

# "فحصتها فعليًا" وأخواتها. العبارة دي بتزوّد ثقة أحمد في النفي، فلو
# النفي غلط بتضاعف ضرره -- والفحص اللي حصل كان في مخزن تاني خالص.
_VERIFICATION_CLAIM_PATTERNS = [
    r"فحصته?ا? فعلي", r"راجعته?ا? فعلي", r"شوفت فعلي", r"اتأكدت فعلي",
    r"بصيت فعلي", r"دورت فعلي",
]

# المخزن الوحيد اللي فيه بنود المقايسات وأسعارها
_ESTIMATE_TOOL = "get_project_details"

# مخازن بتتلخبط معاها. الفحص فيها **مش** فحص في المقايسة.
_NOT_THE_ESTIMATE = ("get_expenses", "expense_summary", "list_expenses",
                     "get_project_file")


def guard_against_unread_no_data_claims(reply_text: str, chat_id=None) -> str:
    """نفي وجود بيانات مالية عن مشروع من غير ما `get_project_details` تتنادى.

    الفرق اللي الحارس ده بيحميه:

        "مفيش تفاصيل"     ادّعاء عن الواقع. لازم دليل.
        "مقراتش المقايسة"  ادّعاء عن نفسه. صحيح دايمًا لما الأداة ماتنفتحش.

    الأولانية بتقفل الموضوع وأحمد بيمشي فاكر إن الداتا مش موجودة.
    التانية بتفتحه. والاتنين نفس الكلفة على الموديل.

    الفحص مربوط بـ**الدورة الواحدة** مش بنافذة عامة. النسخة الأولى كانت
    بتسأل "اتنادت في آخر ستة اختيارات؟" فأي نداء تاني كان بيقمعها -- وده
    اللي حصل فعلًا: نداءين تجربة سكّتوا الحارس عن رد كاذب بعدهم بربع ساعة.
    """
    if not reply_text:
        return reply_text

    notes = []
    tools = turn_tools(chat_id)
    question = turn_question(chat_id) or ""

    # مفيش سياق دورة = **مش عارف** إيه اللي اتنادى، مش "مفيش حاجة اتنادت".
    # نفس قاعدة `[]`: الجهل مايتحولش لحكم. الخروج هنا صريح ومبكر عشان
    # يبقى فرع حقيقي يتجرّب عليه تحوير -- كان شرطًا ميتًا جوه الفحص
    # (السؤال بيبقى فاضي أصلاً من غير سياق، فالفرع مكانش يوصل).
    no_turn_context = tools is None

    denies = any(re.search(p, reply_text) for p in _NO_DATA_PATTERNS)
    cost_question = any(re.search(p, question) for p in _COST_QUESTION_PATTERNS)
    read_estimate = (not no_turn_context) and _ESTIMATE_TOOL in tools

    # --- (1) نفي بيانات مالية من غير قراءة المقايسة ---
    if denies and cost_question and not no_turn_context and not read_estimate:
        looked_elsewhere = sorted(set(tools) & set(_NOT_THE_ESTIMATE))
        logger.warning(
            "⚠️ Contradiction prevented: سؤال تكلفة + نفي + "
            f"{_ESTIMATE_TOOL} ماتنادتش في الدورة دي (اتنادى: {sorted(tools)})"
        )
        note = (
            f"السؤال ده عن تكلفة، و**{_ESTIMATE_TOOL} ماتنادتش في الرد ده** -- "
            "فنفي وجود الرقم مش مبني على قراءة. بنود المقايسات وأسعارها "
            "هناك وبس. الصح: 'مقراتش المقايسة' مش 'مفيش'."
        )
        if looked_elsewhere:
            # المصاريف والمقايسة حاجتين مختلفتين: المقايسة تقدير متعاقد
            # عليه، والمصروف صرف فعلي. الفحص في واحدة مش فحص في التانية.
            note += (
                " والفحص اللي حصل كان في " + "، ".join(looked_elsewhere)
                + " -- ده مخزن تاني خالص: المصروف صرف فعلي، والمقايسة تقدير "
                "متعاقد عليه، وغياب الأول مش دليل على غياب التاني."
            )
        notes.append(note)

        # "فحصتها فعليًا" جنب نفي من غير قراءة = ثقة مبنية على لا حاجة
        if any(re.search(p, reply_text) for p in _VERIFICATION_CLAIM_PATTERNS):
            notes.append(
                "⚠️ ادّعاء فحص مضلّل: الرد بيقول إنه فحص فعليًا، والفحص كان "
                "في مخزن تاني مش في المقايسة -- فالعبارة بتزوّد الثقة في نفي "
                "مش متحقق منه."
            )

    # --- (2) اختراع قاعدة عن قدرات النظام ---
    if any(re.search(p, reply_text) for p in _INVENTED_CAPABILITY_PATTERNS):
        logger.warning("⚠️ Contradiction prevented: الرد اخترع قاعدة عن قدرات النظام")
        notes.append(
            "BAHR OS **بيسجّل** المقايسات فعلًا: التأسيس والفينيش والفينيش "
            "والديكور وحصر الكميات، ببنودها وأسعارها. أي كلام فوق بيقول إنه "
            "بيتابع الحالة بس مش دقيق ومايتبنيش، ومحدش قال لآدم الكلام ده."
        )

    if not notes:
        return reply_text

    return reply_text + "\n\n[ملاحظة دقة تلقائية]: " + " ".join(notes)
