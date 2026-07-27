# -*- coding: utf-8 -*-
"""
Tests First -- Tool Lifecycle Diagnostics (حادثة 2026-07-27).

الجزء الحاسم هنا (test_live_model_actually_selects_get_adam_self_state)
مش اختبار وحدات -- ده نداء حقيقي لـask_claude_agentic بيثبت إن السبب الجذري
الحقيقي (تعليمة قديمة في الـsystem prompt بتقول "استخدم request_verified_
expression بس" -- مكتوبة قبل ما get_adam_self_state يتبنى) اتصلح فعليًا،
مش مجرد "التسجيل موجود نظريًا". لو الإصلاح ده يوم من الأيام اترجع بالغلط،
الاختبار ده هيفشل فورًا بدليل حقيقي، مش هيسيب حد يكتشفها بالصدفة زي ما حصل.
"""

from services.firebase_service import init_firebase
from services import event_store, tool_lifecycle_diagnostics
from services.claude_service import ask_claude_agentic

FAKE_TOOL = "test_lifecycle_fake_tool_does_not_exist"
TEST_CHAT_ID = 999003


def test_unregistered_tool_shows_no_fabricated_state():
    """أداة مش موجودة أصلًا في claude_service.TOOLS -- registered=False، وباقي المراحل '—' (مفيش دليل)، مش False مُخترعة."""
    status = tool_lifecycle_diagnostics.get_tool_lifecycle_status(FAKE_TOOL)
    assert status["registered"] is False
    assert status["payload_included"] is None
    assert status["model_selected"] is None
    assert status["execution_status"] is None

    report = tool_lifecycle_diagnostics.render_lifecycle_report(FAKE_TOOL)
    assert "Registration: ❌" in report
    assert "Payload: —" in report and "Model Selected: —" in report
    print("✅ أداة غير مسجّلة خالص: Registration=❌، باقي المراحل '—' (مفيش دليل، مش حكم مُخترَع)")


def test_recording_and_query_for_real_registered_tool():
    """
    تسجيل حقيقي (Event Store) لـpayload + model_selection، وتأكيد إن
    get_tool_lifecycle_status وrender_lifecycle_report بيقرأوا الدليل ده صح.
    """
    real_tool = "list_graph_nodes"  # موجودة فعليًا في claude_service.TOOLS

    tool_lifecycle_diagnostics.record_payload_snapshot([real_tool, "get_adam_self_state", "get_tools_health_status"])
    tool_lifecycle_diagnostics.record_model_selection("tool_use", [real_tool])

    status = tool_lifecycle_diagnostics.get_tool_lifecycle_status(real_tool)
    assert status["registered"] is True
    assert status["payload_included"] is True
    assert status["model_selected"] is True
    print(f"✅ get_tool_lifecycle_status('{real_tool}'): registered/payload/selected كلهم True فعليًا بعد تسجيل حقيقي")

    report = tool_lifecycle_diagnostics.render_lifecycle_report(real_tool)
    assert f"Tool: {real_tool}" in report
    assert "Registration: ✅" in report and "Payload: ✅" in report and "Model Selected: ✅" in report
    print("✅ render_lifecycle_report بالشكل الصح (Tool/Registration/Payload/Model Selected/Execution)")

    # أداة تانية موجودة في الـRegistry لكن ماكانتش في آخر payload المُسجَّل ولا في آخر اختيار
    other_real_tool = "get_backup_status"
    status2 = tool_lifecycle_diagnostics.get_tool_lifecycle_status(other_real_tool)
    assert status2["registered"] is True
    assert status2["payload_included"] is False, "المفروض False -- الأداة دي مش كانت جوه آخر payload اتسجل"
    assert status2["model_selected"] is False, "المفروض False -- الأداة دي مالهاش دليل اختيار في آخر سجلات"
    print(f"✅ أداة مسجّلة لكن مش في آخر payload/selection ({other_real_tool}): payload_included=False, model_selected=False (دليل حقيقي، مش تخمين)")


def test_live_model_actually_selects_get_adam_self_state():
    """
    الاختبار الحاسم -- نداء حقيقي لـask_claude_agentic (تكلفة Anthropic حقيقية،
    مُتعمَّدة) يطلب صراحة استخدام get_adam_self_state، ويتأكد إن:
    (أ) الرد ماحتواش ادّعاء "الأداة دي مش متاحة"، (ب) model_selected=True فعليًا.
    ده هو الدليل المباشر إن إصلاح تعليمة الـsystem prompt القديمة شغّال، مش
    مجرد أن البنية التحتية موجودة نظريًا.
    """
    reply = ask_claude_agentic(
        "استخدم أداة get_adam_self_state دلوقتي بالظبط وقولي النتيجة اللي رجعتها بالحرف من غير أي تلخيص",
        TEST_CHAT_ID,
    )

    unavailable_phrases = ["مش متاح", "غير متاحة", "not available", "لا أملك", "مالكش"]
    assert not any(p in reply for p in unavailable_phrases), (
        f"الموديل لسه بيدّعي إن get_adam_self_state مش متاحة رغم إصلاح تعليمة الـsystem prompt: {reply}"
    )
    print(f"✅ الرد ماحتواش أي ادّعاء 'مش متاحة' -- عيّنة: {reply[:150]!r}")

    status = tool_lifecycle_diagnostics.get_tool_lifecycle_status("get_adam_self_state")
    assert status["registered"] is True
    assert status["payload_included"] is True
    assert status["model_selected"] is True, (
        "❌ الموديل مااستخدمش get_adam_self_state فعليًا في النداء ده -- السبب الجذري (تعليمة "
        "الـsystem prompt القديمة أو ما يشبهها) لسه موجود، مش مجرد مسألة بنية تحتية"
    )
    print("✅ model_selected=True فعليًا -- الموديل استخدم get_adam_self_state حقيقةً، مش بس 'الأداة موجودة نظريًا'")


def main():
    assert init_firebase(), "فشل الاتصال بـ Firebase"
    test_unregistered_tool_shows_no_fabricated_state()
    test_recording_and_query_for_real_registered_tool()
    test_live_model_actually_selects_get_adam_self_state()
    print("\n✅✅✅ Tool Lifecycle Diagnostics: كل المراحل الخمسة قابلة للتحقق بدليل حقيقي، "
          "والسبب الجذري الفعلي لحادثة get_adam_self_state اتصلح ومُثبَت بنداء حي، مش مجرد افتراض.")


if __name__ == "__main__":
    main()
