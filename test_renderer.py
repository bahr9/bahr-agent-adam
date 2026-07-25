# -*- coding: utf-8 -*-
"""
Tests First -- Renderer (Architecture v2). اتكتبت قبل أي سطر في
services/renderer.py.

الـ Renderer هو الآلية الحتمية اللي بتقفل مشكلة "الموديل بيكتب رقم خام"
بالكامل: Companionship بيكتب نص فيه *مراجع بالاسم* (Slots)، والـ Renderer
هو الوحيد اللي بيملأها بقيم حقيقية من الـ Meaning Packet. مفيش رقم أو
نص استنتاج بيتولّد من الموديل مباشرة -- بيتلصق حرفيًا هنا.

مفيش LLM هنا خالص، ومفيش I/O -- Unit Tests بحتة.
"""


def run_test(name, fn):
    try:
        fn()
        print(f"✅ {name}")
        return True
    except AssertionError as e:
        print(f"❌ {name}: {e}")
        return False
    except Exception as e:
        print(f"❌ {name}: خطأ غير متوقع -- {type(e).__name__}: {e}")
        return False


def main():
    from services import renderer as rd

    results = []

    sample_meaning_packet = {
        "referenced_facts": {
            "unresolved_conflict.count": 3,
            "unresolved_conflict.level": "high",
        },
        "fired_inferences": [
            {"rule_id": "unresolved_conflict_high", "text": "الوضع محتاج مراجعة عاجلة"},
        ],
    }

    # ============================================================
    def test_renders_fact_slot():
        out = rd.render("عندك {unresolved_conflict.count} حالات تعارض", sample_meaning_packet)
        assert out == "عندك 3 حالات تعارض", f"لقيت: {out!r}"
    results.append(run_test("fact slot بسيط بيتملأ بالقيمة الحقيقية", test_renders_fact_slot))

    def test_renders_inference_slot():
        out = rd.render("{inference:unresolved_conflict_high}", sample_meaning_packet)
        assert out == "الوضع محتاج مراجعة عاجلة", f"لقيت: {out!r}"
    results.append(run_test("inference slot بيتملأ بنص الـ rule بالحرف", test_renders_inference_slot))

    def test_renders_multiple_different_slots():
        template = "فيه {unresolved_conflict.count} حالات، والمستوى {unresolved_conflict.level}، و{inference:unresolved_conflict_high}."
        out = rd.render(template, sample_meaning_packet)
        assert out == "فيه 3 حالات، والمستوى high، والوضع محتاج مراجعة عاجلة.", f"لقيت: {out!r}"
    results.append(run_test("أكتر من slot مختلف في نفس القالب بيتملوا كلهم صح", test_renders_multiple_different_slots))

    def test_renders_same_slot_twice():
        template = "العدد {unresolved_conflict.count}، وأكرر: {unresolved_conflict.count}."
        out = rd.render(template, sample_meaning_packet)
        assert out == "العدد 3، وأكرر: 3.", f"لقيت: {out!r}"
    results.append(run_test("نفس الـ slot متكرر مرتين بيتملا صح في الاتنين", test_renders_same_slot_twice))

    def test_plain_text_passes_through():
        out = rd.render("مفيش أي تعارض معلّق دلوقتي.", sample_meaning_packet)
        assert out == "مفيش أي تعارض معلّق دلوقتي."
    results.append(run_test("نص عادي من غير أي slot بيعدي زي ما هو", test_plain_text_passes_through))

    def test_empty_template():
        assert rd.render("", sample_meaning_packet) == ""
    results.append(run_test("قالب فاضي بيرجع نص فاضي", test_empty_template))

    def test_unknown_fact_slot_raises():
        try:
            rd.render("عندك {pending_obligation_load.count} قسط", sample_meaning_packet)
            raise AssertionError("كان المفروض يرفض -- pending_obligation_load.count مش موجود في referenced_facts")
        except rd.UnknownSlotError:
            pass
    results.append(run_test("fact slot مش موجود في referenced_facts بيرفع UnknownSlotError", test_unknown_fact_slot_raises))

    def test_unknown_inference_slot_raises():
        try:
            rd.render("{inference:some_other_rule}", sample_meaning_packet)
            raise AssertionError("كان المفروض يرفض -- rule_id مش موجود في fired_inferences")
        except rd.UnknownSlotError:
            pass
    results.append(run_test("inference slot مش موجود في fired_inferences بيرفع UnknownSlotError", test_unknown_inference_slot_raises))

    def test_extract_slots():
        slots = rd.extract_slots("عندك {unresolved_conflict.count} و{inference:unresolved_conflict_high}")
        assert set(slots) == {"unresolved_conflict.count", "inference:unresolved_conflict_high"}, f"لقيت: {slots}"
    results.append(run_test("extract_slots() بترجع كل أسماء الـ slots الموجودة في نص معيّن", test_extract_slots))

    def test_no_llm_in_renderer_source():
        import services.renderer as rd_module
        source = open(rd_module.__file__, encoding="utf-8").read()
        forbidden = ["anthropic", "claude_client", "ask_claude", "openai"]
        found = [t for t in forbidden if t in source]
        assert not found, f"لقيت إشارات LLM في renderer.py: {found}"
    results.append(run_test("renderer.py مفيهوش أي استدعاء LLM", test_no_llm_in_renderer_source))

    # ============================================================
    print(f"\n{sum(results)}/{len(results)} اختبار عدّى")
    if all(results):
        print("✅✅✅ كل الاختبارات عدّت")
    else:
        print("❌ فيه اختبارات فشلت")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
