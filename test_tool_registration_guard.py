# -*- coding: utf-8 -*-
"""
🛡️ Tool Registration Guard -- اختبار حارس ضد حادثة "الأداة الجديدة مش
ظاهرة في البيئة المستضافة" (2026-07-27).

السبب الحقيقي للحادثة كان دبلوي (origin/main كان متأخر 4 commits عن
الكود المحلي -- الكود نفسه كان سليم ومسجّل بالكامل، بس مايتبعتش لـ GitHub
أصلًا). الاختبار ده مش بيحل مشكلة الدبلوي (ده عملية خارج نطاق الكود)، لكنه
بيضمن إن أي رجوع مستقبلي لنفس نوع الخطأ -- تسجيل ناقص للأداة نفسها في
الكود -- يتمسك فورًا بفشل اختبار واضح، مش باكتشاف يدوي متأخر.

بيتأكد من التلاتة معًا، مش بس واحد:
  1. الأداة موجودة في claude_service.TOOLS (تعريف الأداة).
  2. الـdispatch (_execute_tool) يقدر يوصلها فعليًا -- استدعاء حقيقي، مش
     grep على النص.
  3. تعريفها بالشكل الصح (name/description/input_schema) -- نفس الـobject
     اللي بيتبعت لـClaude حرفيًا (tools=TOOLS مباشرة في ask_claude_agentic،
     صفر قايمة موازية أو فلترة).

صفر LLM هنا -- كله فحص بنيوي واستدعاء دوال حقيقية بس.
"""

from fake_firestore import install_fake_firestore
from services.claude_service import TOOLS, _execute_tool

REQUIRED_TOOLS = [
    "request_verified_expression",  # مسار Self-State الأصلي (Loans self-state expression, Stage 6/7)
    "get_adam_self_state",          # Self State Core V1 -- تقرير شامل (Health/Warnings/Confidence/Mode/Diagnosis)
    "get_self_diagnosis_report",    # قراءة self_diagnosis.py المباشرة (Runtime Activation milestone)
    "get_tools_health_status",      # Runtime Capabilities & Tool Health V1
]


def test_required_tools_defined_in_tools_list():
    """(1) الأداة موجودة في claude_service.TOOLS -- تعريفها كأداة."""
    tool_names = {t["name"] for t in TOOLS}
    missing = [name for name in REQUIRED_TOOLS if name not in tool_names]
    assert missing == [], f"❌ أدوات ناقصة من claude_service.TOOLS خالص: {missing}"
    print(f"✅ كل الأدوات المطلوبة ({len(REQUIRED_TOOLS)}) موجودة في claude_service.TOOLS")


def test_tool_schema_shape_matches_what_is_sent_to_claude():
    """
    (3) كل تعريف أداة فيه name/description/input_schema -- نفس الشكل اللي
    Anthropic API محتاجه، ونفس الـobject (TOOLS) اللي بيتبعت مباشرة في
    `tools=TOOLS` جوه ask_claude_agentic -- صفر قايمة موازية.
    """
    for t in TOOLS:
        assert "name" in t and isinstance(t["name"], str) and t["name"], t
        if "input_schema" not in t:
            # أداة Anthropic native (زي web_search) -- شكلها مختلف تمامًا
            # (type/max_uses/cache_control بدل description/input_schema)،
            # ومش بتمر على _execute_tool أصلًا -- استثناء موثّق، مش تجاهل.
            assert t.get("type"), f"أداة native بدون 'type' خالص: {t}"
            continue
        assert "description" in t and isinstance(t["description"], str) and t["description"], t
        assert isinstance(t["input_schema"], dict), t
        assert t["input_schema"].get("type") == "object", t

    import inspect
    from services import claude_service
    source = inspect.getsource(claude_service.ask_claude_agentic)
    assert "tools=TOOLS" in source, (
        "المفروض ask_claude_agentic تستخدم tools=TOOLS مباشرة -- لو ده اتغيّر لقايمة "
        "تانية، ده احتمال حقيقي لمشكلة 'الأداة مسجّلة بس مش بتوصل للموديل'"
    )
    print("✅ كل تعريفات الأدوات بالشكل الصح، وask_claude_agentic بتستخدم TOOLS نفسها مباشرة (صفر قايمة موازية)")


def test_dispatch_actually_reaches_required_tools():
    """
    (2) استدعاء حقيقي عبر _execute_tool -- مش grep. لو الأداة مسجّلة في
    TOOLS بس نسينا نضيف elif في الـdispatch، النتيجة هتكون "أداة غير معروفة"
    والاختبار ده هيفشل فورًا.
    """
    install_fake_firestore()

    for tool_name in REQUIRED_TOOLS:
        result = _execute_tool(tool_name, {}, chat_id=None)
        assert isinstance(result, str)
        assert "أداة غير معروفة" not in result, (
            f"❌ '{tool_name}' موجودة في TOOLS لكن الـdispatch (_execute_tool) مش عارف "
            f"يوصلها -- نتيجة فعلية: {result}"
        )
        print(f"✅ dispatch وصل فعليًا لـ '{tool_name}' (نتيجة حقيقية، مش fallback 'أداة غير معروفة')")


def main():
    test_required_tools_defined_in_tools_list()
    test_tool_schema_shape_matches_what_is_sent_to_claude()
    test_dispatch_actually_reaches_required_tools()
    print("\n✅✅✅ Tool Registration Guard: كل الأدوات المطلوبة مسجّلة بالكامل (TOOLS + dispatch + نفس الـschema المُرسَل فعليًا لـClaude)")


if __name__ == "__main__":
    main()
