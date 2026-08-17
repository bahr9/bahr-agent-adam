# -*- coding: utf-8 -*-
"""
حارس تنبيه رصيد Anthropic (حادثتان: 2026-08-06 و 2026-08-15).

المرتين الرصيد خلص في نص شغل، والمرتين أحمد اكتشفها من **رد فاشل** مش من
تنبيه. والرد الفاشل كان بيقول "❌ حصلت مشكلة" -- مبيقولش السبب ولا الحل،
فالمحاولة بتتكرر.

الحاجات اللي الملف ده بيحرسها:

  1. **الفاضي مش صفر.** لو `api_usage` مش قابل للقراءة، `spend_since`
     بترجع None مش 0.0. صفر معناه "مصرفتش حاجة" -- طمأنينة كاذبة في
     اللحظة اللي المفروض ننبّه فيها. نفس فخ الـ`[]`.

  2. **التنبيه مرة واحدة لكل نسبة.** فحص كل 6 ساعات × نسبتين = إزعاج
     يخلي أحمد يتجاهل التنبيه، وساعتها التنبيه نفسه بيبقى بلا قيمة.

  3. **رسالة نفاد الرصيد بتتعرف من الخطأ الحقيقي** اللي Anthropic بتبعته
     بالحرف، مش من صيغة متخيلة.

صفر شبكة وصفر موديل -- كل حاجة بالحقن.
"""


def run_test(name, fn):
    try:
        fn()
        print("OK  " + name)
        return True
    except AssertionError as e:
        print("FAIL " + name + ": " + str(e))
        return False
    except Exception as e:
        print("FAIL " + name + ": خطأ غير متوقع -- " + type(e).__name__ + ": " + str(e))
        return False


def main():
    from services import credit_watch as cw

    results = []

    # ---------- (1) نفاد الرصيد بيتعرف ----------

    def the_real_anthropic_error_is_recognised():
        """نص الخطأ ده منقول بالحرف من التشغيلة اللي وقفت النهاردة."""
        real = ("Error code: 400 - {'type': 'error', 'error': {'type': "
                "'invalid_request_error', 'message': 'Your credit balance is too "
                "low to access the Anthropic API. Please go to Plans & Billing to "
                "upgrade or purchase credits.'}}")
        assert cw.is_credit_exhausted(real), "الخطأ الحقيقي ماتعرفش عليه"

    def other_errors_are_not_mistaken_for_it():
        for other in ("Connection timeout", "rate_limit_error: too many requests",
                      "overloaded_error", "", None):
            assert not cw.is_credit_exhausted(other), repr(other)

    def the_message_says_what_still_works():
        """رسالة مبتقولش الحل مبتنفعش -- دي كانت المشكلة الأصلية."""
        m = cw.EXHAUSTED_MESSAGE
        assert "تشحن" in m, m
        assert "التذكيرات" in m, "مبتقولش إيه اللي لسه شغال: " + m

    # ---------- (2) الفاضي مش صفر ----------

    def an_unreadable_usage_table_returns_none_not_zero():
        """أهم حارس هنا. صفر معناه 'مصرفتش' -- والصح 'مش عارف'."""
        from services import supabase_store
        original = supabase_store._client
        supabase_store._client = lambda: None
        try:
            assert cw.spend_since("2026-01-01T00:00:00") is None, (
                "رجّع رقم وهو مش قادر يقرا -- ده بيمنع التنبيه في أسوأ وقت"
            )
        finally:
            supabase_store._client = original

    def unknown_spend_never_produces_an_alert():
        """لو المصروف مجهول، الحالة مش ok، والتنبيه مبيتبعتش."""
        original = cw.spend_since
        cw.spend_since = lambda at: None
        sent = []
        try:
            st_orig = cw.status
            cw.status = lambda: {"ok": False, "reason": "مقدرتش أقرا"}
            try:
                assert cw.check_and_alert(sent.append) is None
                assert not sent, "بعت تنبيه من غير ما يعرف المصروف: " + str(sent)
            finally:
                cw.status = st_orig
        finally:
            cw.spend_since = original

    # ---------- (3) التنبيه مرة واحدة لكل نسبة ----------

    def it_alerts_once_per_threshold():
        saved, sent = {}, []
        orig = cw.status
        cw.status = lambda: {
            "ok": True, "amount": 20.0, "spent": 17.0, "remaining": 3.0,
            "pct": 0.85, "at": "2026-08-17T00:00:00", "alerted": list(saved.get("a", [])),
        }
        class _Ref:
            def set(self, d, merge=False): saved["a"] = d["alerted"]
        orig_flags = cw._flags
        cw._flags = lambda: _Ref()
        try:
            assert cw.check_and_alert(sent.append) is not None, "مابعتش أول تنبيه"
            assert saved.get("a") == [0.80], saved
            assert cw.check_and_alert(sent.append) is None, "كرّر نفس التنبيه"
            assert len(sent) == 1, sent
        finally:
            cw.status, cw._flags = orig, orig_flags

    def crossing_the_second_threshold_alerts_again():
        saved, sent = {"a": [0.80]}, []
        orig = cw.status
        cw.status = lambda: {
            "ok": True, "amount": 20.0, "spent": 19.4, "remaining": 0.6,
            "pct": 0.97, "at": "x", "alerted": list(saved["a"]),
        }
        class _Ref:
            def set(self, d, merge=False): saved["a"] = d["alerted"]
        orig_flags = cw._flags
        cw._flags = lambda: _Ref()
        try:
            assert cw.check_and_alert(sent.append) is not None, "ما نبّهش عند 95%"
            assert 0.95 in saved["a"], saved
        finally:
            cw.status, cw._flags = orig, orig_flags

    def below_the_threshold_stays_quiet():
        sent = []
        orig = cw.status
        cw.status = lambda: {"ok": True, "amount": 20.0, "spent": 4.0,
                             "remaining": 16.0, "pct": 0.20, "at": "x", "alerted": []}
        try:
            assert cw.check_and_alert(sent.append) is None
            assert not sent, sent
        finally:
            cw.status = orig

    # ---------- (4) الحساب ----------

    def the_cost_matches_a_hand_computed_row():
        """مليون توكن دخل على سونيت = $3 بالظبط."""
        row = {"model": "claude-sonnet-5", "input_tokens": 1_000_000,
               "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
        assert abs(cw._cost_of(row) - 3.00) < 1e-9, cw._cost_of(row)
        row2 = {"model": "claude-sonnet-5", "input_tokens": 0, "output_tokens": 100_000,
                "cache_read_tokens": 1_000_000, "cache_write_tokens": 1_000_000}
        # 100k خرج = 1.5 + قراءة 0.30 + كتابة 6.00 (سعر الساعة)
        assert abs(cw._cost_of(row2) - 7.80) < 1e-9, cw._cost_of(row2)

    def an_unknown_model_falls_back_instead_of_crashing():
        row = {"model": "claude-future-9", "input_tokens": 1_000_000,
               "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
        assert cw._cost_of(row) > 0, "موديل مش معروف كسر الحساب"

    def a_bad_topup_amount_is_refused():
        """التأكيد على **سبب** الرفض مش على الرفض نفسه.

        النسخة الأولى كانت `assert not ok` وبس -- وطلعت فاضية: المخزن مش
        متاح في الاختبارات، فكل مبلغ بيترفض بـ"مش قادر أوصل للتخزين" حتى
        لو فحص المبلغ اتشال بالكامل. اتمسكت بالتحوير.
        """
        for bad in ("", "كتير", None):
            ok, msg = cw.record_topup(bad)
            assert not ok, "قبل مبلغ غلط: " + repr(bad)
            assert "رقم" in msg, f"رفضه للسبب الغلط ({bad!r}): {msg}"

        for bad in ("-5", "0", 0, -1.5):
            ok, msg = cw.record_topup(bad)
            assert not ok, "قبل مبلغ غلط: " + repr(bad)
            assert "أكبر من صفر" in msg, f"رفضه للسبب الغلط ({bad!r}): {msg}"

    for name, fn in [
        ("خطأ Anthropic الحقيقي بيتعرف", the_real_anthropic_error_is_recognised),
        ("أخطاء تانية مبتتخلطش بيه", other_errors_are_not_mistaken_for_it),
        ("الرسالة بتقول إيه اللي لسه شغال", the_message_says_what_still_works),
        ("جدول مش مقروء = None مش صفر", an_unreadable_usage_table_returns_none_not_zero),
        ("مصروف مجهول = مفيش تنبيه", unknown_spend_never_produces_an_alert),
        ("تنبيه مرة واحدة لكل نسبة", it_alerts_once_per_threshold),
        ("النسبة التانية بتنبّه من جديد", crossing_the_second_threshold_alerts_again),
        ("تحت النسبة = سكوت", below_the_threshold_stays_quiet),
        ("الحساب مطابق ليدوي", the_cost_matches_a_hand_computed_row),
        ("موديل مش معروف مبيكسرش", an_unknown_model_falls_back_instead_of_crashing),
        ("مبلغ شحن غلط بيترفض", a_bad_topup_amount_is_refused),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
