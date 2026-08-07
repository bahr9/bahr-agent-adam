# -*- coding: utf-8 -*-
"""
حارس صدق الإنذار: إنذار "القراء شايفين حالة قديمة" لازم يدق **بس** لما يكون
فيه انحراف حقيقي.

الحادثة اللي خلّت الملف ده يتكتب (2026-08-07): اللوج كان فيه 347 إنذار
"❌❌ حالة القسط اتكتبت في Firestore بس -- Supabase فشل!" و279 كتابة على
ca_71. الشكل كان بيقول إن البيانات المالية بتاعة أحمد اتخربت من 2026-08-06.

الحقيقة: كل الإنذارات دي كانت من تشغيلات الاختبارات. الاختبارات بتركّب
fake_firestore بس عمرها ما بتهيّئ Supabase (init_supabase بتتنادى في
main.py بس)، فـ supabase_store._client() بيرجع None وكل دوال الكتابة
بترجع False من حارس الـ None -- من غير أي استثناء. المنادي كان بيقرا الـ
False دي على إنها "الكتابة فشلت" ويدق الإنذار.

الضرر مش تجميلي: إنذار بيكذب 347 مرة بيدفن الإنذار الحقيقي لما يحصل.

بيشتغل على fake_firestore -- صفر شبكة.
"""

from fake_firestore import install_fake_firestore
from services import event_store, supabase_store


class _Recorder:
    """بيمسك رسايل اللوج بمستوياتها من غير ما يلمس إعدادات اللوجر."""

    def __init__(self):
        self.errors = []
        self.debugs = []

    def error(self, msg, *a, **k):
        self.errors.append(str(msg))

    def debug(self, msg, *a, **k):
        self.debugs.append(str(msg))

    def __getattr__(self, _name):
        return lambda *a, **k: None


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

    import services.supabase_service as supabase_service

    def _write_one_event(recorder, client):
        """كتابة حدث واحد بـ Supabase على الحالة المطلوبة، وترجيع اللوج."""
        original_client = supabase_service.supabase_client
        original_logger = event_store.logger
        supabase_service.supabase_client = client
        event_store.logger = recorder
        try:
            event_store.record_event_with_write(
                entity_type="probe", entity_id="mirror_alarm", attribute="state",
                domain_collection="probe_domain", domain_document="doc",
                domain_data={"v": 1},
                new_value="b", previous_value="a", source="test", actor="guard",
            )
        finally:
            supabase_service.supabase_client = original_client
            event_store.logger = original_logger

    def silent_when_supabase_is_not_configured():
        """مفيش Supabase = مفيش قراء = مفيش انحراف = ممنوع إنذار.

        ده الاختبار اللي بيفشل من غير الإصلاح: كان بيدق إنذار انحراف كاذب.
        """
        rec = _Recorder()
        _write_one_event(rec, None)

        assert not rec.errors, (
            "دق إنذار انحراف وSupabase مش متصل أصلاً -- ده الباگ اللي ولّد "
            f"347 إنذار كاذب في اللوج:\n  - " + "\n  - ".join(rec.errors)
        )
        assert rec.debugs, "المفروض يتسجل سطر debug إن الـ mirror اتخطى"

    def loud_when_supabase_is_configured_and_the_write_fails():
        """انحراف حقيقي لازم يفضل يدق -- الإصلاح مخفّفش الإنذار الصح."""

        class _RefusingClient:
            def table(self, _name):
                raise RuntimeError("الكتابة مرفوضة (محاكاة فشل حقيقي)")

        rec = _Recorder()
        _write_one_event(rec, _RefusingClient())

        assert rec.errors, (
            "Supabase متصل والكتابة فشلت -- الإنذار الحقيقي مدقّش. "
            "الإصلاح كتّم إنذار المفروض يفضل عالي."
        )
        assert any("mirror" in e for e in rec.errors), rec.errors

    def is_configured_tells_the_two_states_apart():
        """الدالة اللي الفرق كله مبني عليها."""
        original = supabase_service.supabase_client
        try:
            supabase_service.supabase_client = None
            assert supabase_store.is_configured() is False
            supabase_service.supabase_client = object()
            assert supabase_store.is_configured() is True
        finally:
            supabase_service.supabase_client = original

    results = [
        run_test("مفيش إنذار كاذب لما Supabase مش متصل", silent_when_supabase_is_not_configured),
        run_test("الإنذار الحقيقي لسه بيدق لما الكتابة تفشل فعلاً",
                 loud_when_supabase_is_configured_and_the_write_fails),
        run_test("is_configured بتفرّق بين الحالتين", is_configured_tells_the_two_states_apart),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
