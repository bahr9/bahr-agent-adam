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
