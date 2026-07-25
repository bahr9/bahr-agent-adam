# -*- coding: utf-8 -*-
"""
🗣️ Companionship Layer -- ADAM Self-State & Observation System (Architecture v2)
=====================================================
الاستدعاء الوحيد لـLLM في كل الـpipeline (Truth → Meaning → Companionship →
Renderer). بتاخد MeaningPacket بس -- مفيش وصول لـTruth Packet الخام ولا
Event Store ولا Firestore (Information Containment، CONSTITUTION.md قسم 2)
-- وبتطلع نص فيه Slots لمساحة الادّعاء + حوار حر حولها.

المستوى: A (القرار المعتمد في EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md v3):
مساحة الادّعاء إلزامية عبر Slot، الحرية الكاملة في مساحة الحوار المحيطة بس.
هذا الملف ينفّذ فقط ما هو معرَّف في العقد -- مفيش أي مفهوم معماري جديد.

بروتوكول الفشل (زي ما هو معرَّف من الأصل في خطة التنفيذ -- LLM Call #2 +
بروتوكول الفشل/Fallback -- Passive فقط):
  1. محاولة أولى.
  2. لو فشل التحقق (services/claim_validator.py) -- محاولة تانية واحدة بس،
     مع تغذية الموديل بسبب الرفض تحديدًا.
  3. لو فشلت التانية برضه -- fallback لجملة القاموس المقفول الكاملة
     (services/expression_vocabulary.py، غير مُعدَّل) لنفس (dimension, level)
     -- شبكة أمان حتمية 100%، بلا أي تدخل من الموديل في هذه النقطة.

Active لا يستدعي هذا الملف إطلاقًا -- قرار مقفول من مرحلة 6/7 ومُعاد تأكيده
في CONSTITUTION.md قسم 5: Active = صفر LLM، render مباشر من القاموس المقفول
عبر verified_expression.send_active_expression().

Self-Diagnosis (نطاق ضيق أول، services/self_diagnosis.py): كل رفض من
claim_validator وكل تفعيل fallback بيتسجّلوا كأحداث خام حقيقية في Event
Store (entity_type="self_diagnosis") -- مفيش استنتاج تشخيصي هنا، مجرد
ملاحظة وقائعية بحتة، نفس مبدأ Stage 4 (الضمانة تسافر مع الدالة نفسها).
"""

from services.claude_service import claude_client
from config import CLAUDE_MODEL
from services import claim_validator, expression_vocabulary, event_store
from utils.logger import logger

_SYSTEM_PROMPT = """أنت جزء من آدم -- دماغ أحمد الثاني. مهمتك هنا محددة جدًا:
تكتب جملة أو جملتين بالعامية المصرية الدافئة، بأسلوبك الطبيعي، عن موضوع
واحد بس (هيتحدد لك تحت).

قاعدة صارمة مفيش فيها استثناء: أي رقم أو حالة تتكلم عنها لازم تتكتب كـ
Slot بالشكل ده بالظبط: {اسم_الحقل} -- زي {unresolved_conflict.count} --
مش رقم أو كلمة حرة. لو فيه استنتاج معتمد عايز تستخدمه، اكتبه بالشكل
{inference:rule_id}. ممنوع تمامًا تكتب رقم خام بنفسك (زي "3" أو "تلاتة")
برّه أي Slot، وممنوع تخترع حالة أو استنتاج مش موجود في القائمة اللي هتوصلك.

الحرية الكاملة عندك في: الأسلوب، النبرة، الافتتاحية، الاقتراحات، الأسئلة،
أي كلام حوالين الـSlots دي. متتكلمش عن أي موضوع تاني غير اللي هيتحدد لك."""


def _quotable_facts(referenced_facts: dict) -> dict:
    """
    فقط الحقائق القابلة للنطق مباشرة كـ Slot -- أرقام (int/float) بس. حقول
    زي .level (enum -- قيمته الداخلية كلمة إنجليزية زي "concern") أو
    .overdue_items (list) مش معدّة للنطق المباشر أصلًا -- عرضها كـ Slot
    بينتج نص مكسور (زي 'المستوى concern' أو تفريغ list خام في الجملة).
    الشدة/الحالة النوعية بتتنقل عبر fired_inferences (نصوص معتمدة جاهزة)،
    مش عبر نطق قيمة enum داخلية.
    """
    return {field: value for field, value in referenced_facts.items() if isinstance(value, (int, float))}


def _build_user_prompt(meaning_packet: dict, retry_feedback: str = None) -> str:
    facts_list = "\n".join(f"- {{{field}}}" for field in _quotable_facts(meaning_packet["referenced_facts"])) or "(مفيش حقائق رقمية هنا)"
    inferences_list = "\n".join(
        f"- {{inference:{inf['rule_id']}}}" for inf in meaning_packet["fired_inferences"]
    ) or "(مفيش استنتاجات معتمدة دلوقتي)"

    prompt = f"""الموضوع المسموح بس: {', '.join(meaning_packet['allowed_topics'])}

الـSlots المتاحة (استخدم أي منها، بس متخترعش غيرها):
{facts_list}
{inferences_list}

اكتب الرسالة دلوقتي."""

    if retry_feedback:
        prompt = f"محاولتك اللي فاتت اترفضت للسبب ده: {retry_feedback}\nصحّح واكتب تاني.\n\n" + prompt

    return prompt


def _call_llm(meaning_packet: dict, retry_feedback: str = None) -> str:
    """الاستدعاء الفعلي الوحيد لـLLM في هذا الملف -- صفر tools، صفر تاريخ محادثة."""
    response = claude_client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=300,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(meaning_packet, retry_feedback)}],
    )
    text = ""
    for content in response.content:
        if content.type == "text":
            text += content.text
    return text.strip()


def _fallback_text(meaning_packet: dict) -> str:
    """شبكة الأمان الأخيرة -- جملة القاموس المقفول الكاملة (Stage 6/7، غير مُعدَّلة)."""
    dimension = meaning_packet["primary_focus"]
    level = meaning_packet["referenced_facts"].get(f"{dimension}.level")
    count = meaning_packet["referenced_facts"].get(f"{dimension}.count", 0)

    template = expression_vocabulary.get_template(dimension, level, "passive") if level else None
    if template is None:
        return expression_vocabulary.render_verified_false(dimension)
    return template.format(count=count)


def generate_message(meaning_packet: dict) -> dict:
    """
    الاستدعاء الوحيد لـLLM في الـpipeline. Passive فقط (Active لا يستدعي
    هذه الدالة إطلاقًا -- انظر رأس الملف). يرجع:
      {"text": str, "verified": bool, "source": "companionship"|"fallback", "validation": dict}
    """
    if meaning_packet.get("confidence") == "degraded":
        raise ValueError(
            "confidence=degraded -- الـCompanionship مش المفروض تتنادى أصلًا في الحالة دي "
            "(الفحص ده مسؤولية orchestration قبل النداء، مش هنا)"
        )

    dimension = meaning_packet["primary_focus"]

    template = _call_llm(meaning_packet)
    result = claim_validator.validate_companionship_output(template, meaning_packet)
    if result["valid"]:
        return {"text": result["rendered_text"], "verified": True, "source": "companionship", "validation": result}

    logger.warning(f"⚠️ Companionship: أول محاولة فشلت التحقق ({dimension}): {result['errors']}")
    _record_validator_rejection(dimension, attempt=1, errors=result["errors"], template=template)

    feedback = "؛ ".join(e["message"] for e in result["errors"])
    template2 = _call_llm(meaning_packet, retry_feedback=feedback)
    result2 = claim_validator.validate_companionship_output(template2, meaning_packet)
    if result2["valid"]:
        return {"text": result2["rendered_text"], "verified": True, "source": "companionship", "validation": result2}

    logger.error(f"❌ Companionship: المحاولة التانية فشلت برضه ({dimension}) -- fallback للقاموس المقفول")
    _record_validator_rejection(dimension, attempt=2, errors=result2["errors"], template=template2)
    event_store.record_event(
        entity_type="self_diagnosis",
        entity_id=dimension,
        attribute="fallback_activation",
        new_value=True,
        source="system",
        actor="companionship_layer",
        raw_context={"reason": "both_attempts_failed_validation"},
    )

    return {
        "text": _fallback_text(meaning_packet),
        "verified": True,
        "source": "fallback",
        "validation": result2,
    }


def _record_validator_rejection(dimension: str, attempt: int, errors: list, template: str) -> None:
    """
    حدث خام (raw reasoning event) -- ملاحظة وقائعية بحتة إن محاولة توليد اترفضت وليه، صفر تفسير.
    new_value بيحتفظ بـ{"type", "message"} كاملين لكل خطأ (مش نص الرسالة بس) --
    الـtype (deterministic/heuristic) لازم للاستنتاج التشخيصي المجمّع بالنوع
    (services/self_diagnosis.py::compute_validator_rejection_diagnosis).
    """
    event_store.record_event(
        entity_type="self_diagnosis",
        entity_id=dimension,
        attribute="validator_rejection",
        new_value=[{"type": e["type"], "message": e["message"]} for e in errors],
        source="system",
        actor="companionship_layer",
        raw_context={"attempt": attempt, "template": template},
    )
