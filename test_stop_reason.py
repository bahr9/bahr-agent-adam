# -*- coding: utf-8 -*-
"""
Tests First -- معالجة أسباب توقف الموديل (أوديت 2026-08-05).

الباگ: اللوب كان بيقول `if response.stop_reason != "tool_use": return النص`.
يعني:
  - pause_turn (بحث وِب وقف عشان يكمّل في طلب تاني) كان بيترجع كإجابة نهائية
    -- بحث نص مكتمل بيوصل لأحمد كأنه رد كامل.
  - max_tokens كان بيترجع نص مقطوع من غير أي إشارة إنه اتقطع.
  - max_tokens وسط استدعاء أداة كان بيرمي الاستدعاء -- الموديل قال لأحمد
    "هعملك كذا" والأداة **متنفذتش** ومحدش عرف.
  - refusal بمحتوى فاضي كان بيرجع "تمام." الملفقة.

الاختبارات دي بتستبدل عميل Anthropic بالكامل -- صفر نداءات API.
"""


class _Text:
    type = "text"

    def __init__(self, text):
        self.text = text


class _ToolUse:
    type = "tool_use"

    def __init__(self, name, block_id="tu_1", tool_input=None):
        self.name = name
        self.id = block_id
        self.input = tool_input or {}


class _Response:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content


class _FakeClient:
    """بيرد بردود مكتوبة بالترتيب، وبيسجّل كل نداء اتعمل."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("اتنده على الـ API أكتر من المتوقع")
        return self._responses.pop(0)


def run_test(name, fn):
    try:
        fn()
        print(f"OK  {name}")
        return True
    except AssertionError as e:
        print(f"FAIL {name}: {e}")
        return False
    except Exception as e:
        print(f"FAIL {name}: خطأ غير متوقع -- {type(e).__name__}: {e}")
        return False


def main():
    import services.claude_service as cs
    import services.tool_lifecycle_diagnostics as tld

    # تعطيل كل حاجة بتلمس Firestore أو بتحلل الرسالة.
    #
    # الترقيعات دي عالمية على مستوى الموديول، ولازم ترجع في `finally`
    # (2026-08-09). الملف ده كان بيسيبها مركّبة، وده مكانش بيأذي مع
    # المشغّل القديم لأن كل ملف كان بياخد عملية لوحده. تحت pytest --
    # عملية واحدة -- كان بيسمّم `tool_lifecycle_diagnostics` لكل ملف
    # بعده: خمس اختبارات في test_tool_lifecycle_diagnostics.py كانت
    # بتفشل بـ`payload_included is None` والسبب مالوش أي علاقة بيها.
    _PATCHED = [
        (tld, "record_payload_snapshot", tld.record_payload_snapshot),
        (tld, "record_model_selection", tld.record_model_selection),
        (tld, "detect_explicit_tool_request", tld.detect_explicit_tool_request),
        (cs, "build_system_prompt_parts", cs.build_system_prompt_parts),
        (cs, "_execute_tool", cs._execute_tool),
    ]

    def _restore_patched():
        for mod, attr, original in _PATCHED:
            setattr(mod, attr, original)

    tld.record_payload_snapshot = lambda *a, **k: None
    tld.record_model_selection = lambda *a, **k: None
    tld.detect_explicit_tool_request = lambda *a, **k: None
    cs.build_system_prompt_parts = lambda **k: ("ثابت", "متغير")

    executed = []
    cs._execute_tool = lambda name, tool_input, chat_id: (
        executed.append(name) or "نتيجة الأداة"
    )

    original_client = cs.claude_client

    def ask(responses):
        executed.clear()
        client = _FakeClient(responses)
        cs.claude_client = client
        try:
            reply = cs.ask_claude_agentic("رسالة اختبار", chat_id=1)
        finally:
            cs.claude_client = original_client
        return reply, client

    results = []

    # ---------- المسار العادي ----------
    def normal_reply_passes_through():
        reply, client = ask([_Response("end_turn", [_Text("أهلاً يا أحمد")])])
        assert reply == "أهلاً يا أحمد", reply
        assert len(client.calls) == 1

    def empty_reply_falls_back():
        reply, _ = ask([_Response("end_turn", [])])
        assert reply == "تمام.", reply

    def tool_use_runs_the_tool_then_answers():
        reply, client = ask([
            _Response("tool_use", [_ToolUse("get_weather")]),
            _Response("end_turn", [_Text("الجو حلو")]),
        ])
        assert executed == ["get_weather"], executed
        assert reply == "الجو حلو", reply
        assert len(client.calls) == 2

    # ---------- pause_turn ----------
    def pause_turn_resumes_instead_of_returning():
        """الحارس: البحث الموقوف لازم يكمّل، مش يترجع كإجابة."""
        reply, client = ask([
            _Response("pause_turn", [_Text("ببحث...")]),
            _Response("end_turn", [_Text("لقيت السعر: 900 جنيه")]),
        ])
        assert reply == "لقيت السعر: 900 جنيه", reply
        assert len(client.calls) == 2, f"مكملش الدور -- {len(client.calls)} نداء بس"

    def pause_turn_keeps_partial_content_in_context():
        _, client = ask([
            _Response("pause_turn", [_Text("ببحث...")]),
            _Response("end_turn", [_Text("خلاص")]),
        ])
        second_call_messages = client.calls[1]["messages"]
        assert any(m.get("role") == "assistant" for m in second_call_messages), \
            "المحتوى الجزئي مترجعش في الطلب التاني"

    # ---------- max_tokens ----------
    def truncated_text_is_flagged():
        reply, _ = ask([_Response("max_tokens", [_Text("التقرير بيقول إن")])])
        assert "التقرير بيقول إن" in reply, reply
        assert "اتقطع" in reply, "الرد المقطوع عدّى من غير أي إشارة -- " + reply

    def truncated_tool_call_says_it_did_not_run():
        """أخطر حالة: الموديل قال هيعمل حاجة، والتوكنز خلصت، والأداة متنفذتش."""
        reply, _ = ask([
            _Response("max_tokens", [_Text("تمام هسجلها"), _ToolUse("save_price")]),
        ])
        assert executed == [], "الأداة اتنفذت رغم إن الاستدعاء كان مقطوع!"
        assert "معملتهاش" in reply, reply

    # ---------- refusal ----------
    def refusal_is_explicit_not_fake_ok():
        reply, _ = ask([_Response("refusal", [])])
        assert reply != "تمام.", "الرفض اترجع كموافقة ملفقة"
        assert "مقدرتش" in reply, reply

    # ---------- الحد الأقصى للتوكنز ----------
    def max_tokens_budget_was_raised():
        _, client = ask([_Response("end_turn", [_Text("خلاص")])])
        assert client.calls[0]["max_tokens"] >= 4096, client.calls[0]["max_tokens"]

    for name, fn in [
        ("الرد العادي بيعدي زي ما هو", normal_reply_passes_through),
        ("الرد الفاضي بيرجع 'تمام.'", empty_reply_falls_back),
        ("tool_use بينفّذ الأداة وبعدين يرد", tool_use_runs_the_tool_then_answers),
        ("pause_turn بيكمّل مش بيرجع (الحارس الأساسي)", pause_turn_resumes_instead_of_returning),
        ("pause_turn بيحتفظ بالمحتوى الجزئي", pause_turn_keeps_partial_content_in_context),
        ("الرد المقطوع بيتقال إنه مقطوع", truncated_text_is_flagged),
        ("استدعاء أداة مقطوع مابينفذش وبيتقال", truncated_tool_call_says_it_did_not_run),
        ("الرفض بيتقال صراحة مش 'تمام.'", refusal_is_explicit_not_fake_ok),
        ("حد التوكنز اترفع لـ 4096", max_tokens_budget_was_raised),
    ]:
        results.append(run_test(name, fn))

    _restore_patched()

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
