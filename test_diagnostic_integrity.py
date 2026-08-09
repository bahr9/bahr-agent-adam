# -*- coding: utf-8 -*-
"""
حارس أدوات التشخيص نفسها.

الملف ده اتكتب بعد يوم (2026-08-08) اتقرا فيه اللوج غلط مرتين:

  1. 347 إنذار "حالة القسط اتكتبت في Firestore بس -- Supabase فشل!"
     اتقروا على إنهم خراب بيانات مالية مستمر. كانوا كلهم تشغيلات
     اختبارات، وSupabase مكانش متصل أصلًا فيها.
  2. 114 رفض "السر مش متظبط" اتقروا على إن الوصلات بين آدم والأنظمة
     التانية (مداد، عين الخبير) مقطوعة. كانوا محليين؛ الإنتاج سليم.

الاتنين نفس العطل: **اللوج مش بيقول من أنهي بيئة**، فتشغيلة اختبار
وتشغيلة إنتاج شكلهم واحد بالحرف.

والعطل التالت: مقارنات الظل (اللي المفروض تغذّي الـ Decision Gate في
EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md §6.2) كانت بتتكتب في اللوج
**بس**. اللوج ملف على قرص الكونتينر، وقرص Railway مؤقت -- كل نشر بيمسحه.
يعني القياس شغال من 24 يوليو وبينتج صفر دليل باقي.

الاختبارات دي بتحرس التلاتة. من غيرها، أي حكم على "صدق آدم" أو "مبادرته"
هيتبنى على بيانات مش موثوقة.

بيشتغل على fake_firestore -- صفر شبكة.
"""

import os
import sys

from fake_firestore import install_fake_firestore


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
    install_fake_firestore()

    # لازم importlib هنا: `utils/__init__.py` بيعمل `from .logger import
    # logger`، فالاسم `utils.logger` بيتربط بكائن الـ Logger نفسه بعد
    # استيراد الموديول -- يعني `import utils.logger as X` بيدي الكائن مش
    # الموديول. ده حجب صامت بيخلي أي فحص على الموديول يفشل بشكل مضلل.
    import importlib

    logger_module = importlib.import_module("utils.logger")
    from services import verified_expression, event_store

    # ---------- (ب) علامة البيئة ----------

    def the_environment_marker_is_in_every_line():
        """أي سطر لوج لازم يقول من فين جه."""
        fmt = logger_module.logger.handlers[0].formatter._fmt
        assert "[" in fmt and "]" in fmt, f"مفيش علامة بيئة في الفورمات: {fmt}"
        assert logger_module.ENVIRONMENT in fmt, (
            f"الفورمات مفيهوش البيئة المكتشفة ({logger_module.ENVIRONMENT}): {fmt}"
        )

    def a_test_run_is_labelled_test():
        """الملف ده نفسه تشغيلة اختبار -- لازم يبان كده، مش كإنتاج."""
        assert logger_module.ENVIRONMENT == "test", (
            f"تشغيلة اختبار اتصنّفت '{logger_module.ENVIRONMENT}' -- "
            "ده بالظبط الخلط اللي ولّد إنذارين كاذبين في يوم واحد"
        )

    def test_beats_prod_even_inside_railway():
        """تشغيلة اختبار جوه بيئة الإنتاج تفضل اختبار."""
        original = os.environ.get("RAILWAY_ENVIRONMENT")
        os.environ["RAILWAY_ENVIRONMENT"] = "production"
        try:
            assert logger_module.detect_environment() == "test", (
                "الإنتاج غلب الاختبار -- تشغيلة اختبار على Railway هتتقرا كإنتاج"
            )
        finally:
            if original is None:
                os.environ.pop("RAILWAY_ENVIRONMENT", None)
            else:
                os.environ["RAILWAY_ENVIRONMENT"] = original

    def railway_is_detected_as_prod():
        # المحاكاة لازم تغطي **كل** إشارات "دي تشغيلة اختبار"، ومنها
        # `sys.modules` اللي مش ممكن نزوّره -- عشان كده بنرقّع الدالة نفسها.
        # ده مش إضعاف: الفرع اللي بيتفحص هنا هو ترتيب الأولوية
        # (اختبار > إنتاج > محلي)، وكاشف الاختبار نفسه بيتفحص في
        # `a_test_run_is_labelled_test` جوه تشغيلة اختبار حقيقية.
        original_argv = sys.argv[0]
        original_pytest = os.environ.pop("PYTEST_CURRENT_TEST", None)
        original_railway = os.environ.get("RAILWAY_ENVIRONMENT")
        original_detector = logger_module._is_test_process
        logger_module._is_test_process = lambda: False
        sys.argv[0] = "main.py"
        os.environ["RAILWAY_ENVIRONMENT"] = "production"
        try:
            assert logger_module.detect_environment() == "prod"
        finally:
            logger_module._is_test_process = original_detector
            sys.argv[0] = original_argv
            if original_pytest is not None:
                os.environ["PYTEST_CURRENT_TEST"] = original_pytest
            if original_railway is None:
                os.environ.pop("RAILWAY_ENVIRONMENT", None)
            else:
                os.environ["RAILWAY_ENVIRONMENT"] = original_railway

    def a_plain_local_run_is_local():
        original_argv = sys.argv[0]
        original_pytest = os.environ.pop("PYTEST_CURRENT_TEST", None)
        original_detector = logger_module._is_test_process
        logger_module._is_test_process = lambda: False
        for var in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_NAME"):
            os.environ.pop(var, None)
        sys.argv[0] = "main.py"
        try:
            assert logger_module.detect_environment() == "local"
        finally:
            logger_module._is_test_process = original_detector
            sys.argv[0] = original_argv
            if original_pytest is not None:
                os.environ["PYTEST_CURRENT_TEST"] = original_pytest

    # ---------- (أ) الدليل بيعيش ----------

    def a_shadow_comparison_becomes_a_durable_event():
        """الدليل اللي الـ Decision Gate مستنيه لازم ينجو من النشر."""
        before = event_store.get_events_for_entity("self_diagnosis", "probe_dimension")
        verified_expression._record_shadow_comparison(
            "probe_dimension",
            "النص القديم",
            {"text": "النص الجديد", "source": "companionship"},
            False,
        )
        after = event_store.get_events_for_entity("self_diagnosis", "probe_dimension")
        assert len(after) == len(before) + 1, "المقارنة ماتسجلتش كحدث"

        ev = after[-1]
        assert ev["attribute"] == "shadow_comparison", ev
        payload = ev["new_value"]
        assert payload["old"] == "النص القديم", payload
        assert payload["new"] == "النص الجديد", payload
        assert payload["source"] == "companionship", payload
        assert payload["match"] is False, payload

    def recording_failure_never_breaks_the_real_path():
        """الظل مبيأثرش على أي حاجة بتتبعت -- حتى لو الكتابة وقعت."""
        original = event_store.record_event

        def _explode(*a, **k):
            raise RuntimeError("انفجار مقصود في تسجيل الحدث")

        event_store.record_event = _explode
        try:
            verified_expression._record_shadow_comparison(
                "probe_dimension", "قديم", {"text": "جديد", "source": "x"}, False
            )  # لازم يبلع الاستثناء
        finally:
            event_store.record_event = original

    def the_shadow_still_never_touches_what_gets_sent():
        """الثابت الأصلي للظل: صفر تأثير على النص المرسل.

        إضافة تسجيل الحدث مضافتش أي قيمة راجعة -- الظل لسه بيرجع None،
        فمفيش حاجة تخرج منه وتدخل رد أحمد.
        """
        import inspect

        sig = inspect.signature(verified_expression._shadow_run_pipeline)
        assert sig.return_annotation is None, (
            f"الظل بقى بيرجّع {sig.return_annotation} -- ده بيفتح باب تأثيره على الرد"
        )
        assert verified_expression._shadow_run_pipeline("probe_dimension", "أي نص") is None, (
            "الظل رجّع قيمة فعليًا"
        )

    results = [
        run_test("علامة البيئة موجودة في كل سطر", the_environment_marker_is_in_every_line),
        run_test("تشغيلة الاختبار بتتصنّف test", a_test_run_is_labelled_test),
        run_test("الاختبار بيغلب الإنتاج حتى جوه Railway", test_beats_prod_even_inside_railway),
        run_test("Railway بيتصنّف prod", railway_is_detected_as_prod),
        run_test("التشغيل المحلي بيتصنّف local", a_plain_local_run_is_local),
        run_test("مقارنة الظل بتتحول لحدث دائم", a_shadow_comparison_becomes_a_durable_event),
        run_test("فشل التسجيل مبيكسرش المسار الحقيقي", recording_failure_never_breaks_the_real_path),
        run_test("الظل لسه مبيأثرش على النص المرسل", the_shadow_still_never_touches_what_gets_sent),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
