# -*- coding: utf-8 -*-
"""
حلقة المبادرة: آدم قال، وأحمد رد ولا لأ؟

الفجوة رقم ٢ من تشخيص 2026-08-08: مسار الـ Active اتجاه واحد -- آدم بيبادر
ومفيش حاجة بتربط رد أحمد بالحاجة اللي اتكلم عنها.

أهم قرار تصميمي محروس هنا: **الحلقة قراءة من بيانات موجودة، مش خطّاف جديد
على مسار تليجرام.** الطرفين متسجلين بأوقاتهم خلاص (expressions في Firestore،
conversation_messages في Supabase)، فمفيش مسار كتابة جديد ينفع يقع ومستحيل
حاجة هنا تأخر رد أحمد.

والقيد المحروس كمان: الربط **زمني مش دلالي**، والحساب لازم يفرّق بين
"محدش رد" و"مكانش ممكن يتسجل رد أصلًا" (مبادرة قبل ما التخزين يبتدي).
الخلط بينهم بيطلّع نسبة استجابة كاذبة.

fake_firestore + Supabase مستبدل -- صفر شبكة.
"""

from datetime import datetime, timedelta, timezone

from fake_firestore import install_fake_firestore
from config import EXPRESSIONS_COLLECTION

BASE = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)


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


class _FakeTable:
    """بديل جدول Supabase -- بيحاكي `order` و`limit` مش بيتجاهلهم.

    قبل كده كان `select().execute()` بس، فلما الكود الحقيقي بقى بيعمل
    `.order(...).limit(...)` الاختبارات فشلت. تجاهل الاتنين هنا كان هيخلي
    الاختبار **يعدي على كود مش بيحد فعلًا** -- وده أسوأ من الفشل، فالمحاكاة
    بتنفّذهم بجد (مراجعة 2026-08-08).
    """

    def __init__(self, rows):
        self._rows = list(rows)
        self._order = None
        self._desc = False
        self._limit = None

    def select(self, *_a, **_k):
        return self

    def order(self, column, desc=False, **_k):
        self._order, self._desc = column, desc
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        rows = self._rows
        if self._order:
            rows = sorted(rows, key=lambda r: str(r.get(self._order) or ""),
                          reverse=self._desc)
        if self._limit is not None:
            rows = rows[:self._limit]

        class R:
            pass
        r = R()
        r.data = rows
        return r


class _FakeSupabase:
    def __init__(self, rows):
        self._rows = rows

    def table(self, _name):
        return _FakeTable(self._rows)


def main():
    db = install_fake_firestore()

    from services import initiative_loop as loop
    from services import supabase_store

    # `_client` بيتربّع تلات مرات تحت، ولازم يرجع في الآخر (2026-08-09):
    # مع المشغّل القديم العملية كانت بتنتهي فتنظّف نفسها، وتحت pytest
    # الـlambda كانت بتفضل مركّبة لباقي السويت.
    _original_client = supabase_store._client

    def seed(initiatives, messages):
        """يزرع الجانبين: تعبيرات في Firestore ورسايل في Supabase."""
        for i, (dim, mode, offset_min) in enumerate(initiatives):
            eid = f"e{i}"
            db.collection(EXPRESSIONS_COLLECTION).document(eid).set({
                "expression_id": eid,
                "dimension": dim,
                "mode": mode,
                "level": "high",
                "rendered_text": f"مبادرة {i}",
                "sent_at": (BASE + timedelta(minutes=offset_min)).isoformat(),
            })
        rows = [{"user_text": t, "occurred_at": (BASE + timedelta(minutes=m)).isoformat()}
                for t, m in messages]
        supabase_store._client = lambda: _FakeSupabase(rows)

    def reset():
        for k in list(db.all_docs(EXPRESSIONS_COLLECTION)):
            db.collection(EXPRESSIONS_COLLECTION).document(k).delete()

    # ---------- الربط الأساسي ----------

    def a_reply_after_an_initiative_is_linked():
        reset()
        seed([("unresolved_conflict", "active", 0)], [("تمام هشوفها", 30)])
        out = loop.get_initiative_outcomes()
        assert len(out) == 1, out
        o = out[0]
        assert o["responded"] is True, o
        assert o["latency_minutes"] == 30.0, o
        assert o["response_text"] == "تمام هشوفها", o

    def silence_is_recorded_as_a_real_outcome():
        """محدش رد = معلومة، مش نقص بيانات."""
        reset()
        seed([("unresolved_conflict", "active", 0)], [("رسالة قبلها", -60)])
        o = loop.get_initiative_outcomes()[0]
        assert o["responded"] is False, o
        assert o["latency_minutes"] is None and o["response_text"] is None, o

    def a_message_before_the_initiative_never_counts():
        reset()
        seed([("unresolved_conflict", "active", 100)], [("كلام سابق", 10)])
        assert loop.get_initiative_outcomes()[0]["responded"] is False

    def a_reply_outside_the_window_does_not_count():
        reset()
        seed([("unresolved_conflict", "active", 0)], [("متأخر أوي", 60 * 30)])
        assert loop.get_initiative_outcomes()[0]["responded"] is False

    def the_first_message_after_wins_not_a_later_one():
        reset()
        seed([("unresolved_conflict", "active", 0)], [("الأول", 10), ("التاني", 20)])
        o = loop.get_initiative_outcomes()[0]
        assert o["response_text"] == "الأول", o

    def passive_expressions_are_not_initiatives():
        """الـ passive بيتقال لما حد يسأل -- مش مبادرة، مينفعش يتحسب."""
        reset()
        seed([("unresolved_conflict", "passive", 0)], [("رد", 5)])
        assert loop.get_initiative_outcomes() == []

    def the_new_active_modes_count_as_initiatives():
        """active_changed و active_stalled مبادرات زيهم زي active."""
        reset()
        seed([("unresolved_conflict", "active_stalled", 0),
              ("pending_obligation_load", "active_changed", 1)], [])
        modes = {o["mode"] for o in loop.get_initiative_outcomes()}
        assert modes == {"active_stalled", "active_changed"}, modes

    # ---------- الحساب الصادق ----------

    def initiatives_before_storage_began_are_excluded_not_counted_as_silence():
        """أهم حساب: مبادرة قبل ما التخزين يبتدي مستحيل يكون ليها رد مسجّل.

        عدّها كـ"محدش رد" بيطلّع نسبة استجابة كاذبة -- وده بالظبط الوضع
        الحقيقي في الإنتاج دلوقتي (المبادرات كلها قبل تخزين المحادثات).
        """
        reset()
        seed([("unresolved_conflict", "active", -60 * 24 * 3),   # قبل أي رسالة
              ("unresolved_conflict", "active", 0)],             # بعدها
             [("رد فعلي", 15)])
        s = loop.summarize()
        assert s["initiatives_total"] == 2, s
        assert s["coverage_gap"] == 1, f"المبادرة القديمة المفروض تتشال: {s}"
        assert s["countable"] == 1, s
        assert s["responded"] == 1, s
        assert s["response_rate"] == 100, f"نسبة كاذبة: {s}"

    def response_rate_is_none_when_nothing_is_countable():
        reset()
        seed([("unresolved_conflict", "active", -60 * 24 * 3)], [("رسالة", 0)])
        s = loop.summarize()
        assert s["countable"] == 0 and s["response_rate"] is None, s

    def unreadable_timestamps_are_skipped_not_guessed():
        reset()
        db.collection(EXPRESSIONS_COLLECTION).document("bad").set({
            "expression_id": "bad", "dimension": "x", "mode": "active",
            "rendered_text": "?", "sent_at": "مش تاريخ",
        })
        supabase_store._client = lambda: _FakeSupabase([])
        assert loop.get_initiative_outcomes() == [], "وقت مش مقروء اتعامل معاه كأنه صالح"

    # ---------- لا يلمس مسار تليجرام ----------

    def the_module_never_writes_anything():
        """الضمانة الأساسية: قراءة بس. أي كتابة هنا = مسار جديد ينفع يقع."""
        import inspect
        src = inspect.getsource(loop)
        for forbidden in (".set(", ".insert(", ".update(", ".delete(", "record_event"):
            assert forbidden not in src, (
                f"الموديول بيكتب ({forbidden}) -- المفروض قراءة بس"
            )

    def a_dead_datasource_degrades_quietly():
        """مصدر واقع = نتيجة فاضية، مش استثناء يوصل لمسار أحمد."""
        reset()
        supabase_store._client = lambda: None
        assert loop.get_initiative_outcomes() == []
        s = loop.summarize()
        assert s["initiatives_total"] == 0 and s["response_rate"] is None, s

    results = [
        run_test("الرد بعد المبادرة بيتربط بيها", a_reply_after_an_initiative_is_linked),
        run_test("السكوت بيتسجل كنتيجة حقيقية", silence_is_recorded_as_a_real_outcome),
        run_test("رسالة قبل المبادرة عمرها ما تتحسب", a_message_before_the_initiative_never_counts),
        run_test("رد برة النافذة مش بيتحسب", a_reply_outside_the_window_does_not_count),
        run_test("أول رسالة بعدها هي الرد", the_first_message_after_wins_not_a_later_one),
        run_test("الـ passive مش مبادرة", passive_expressions_are_not_initiatives),
        run_test("الأوضاع الجديدة بتتحسب مبادرات", the_new_active_modes_count_as_initiatives),
        run_test("مبادرات قبل التخزين بتتشال مش تتعد سكوت", initiatives_before_storage_began_are_excluded_not_counted_as_silence),
        run_test("مفيش نسبة من غير حاجة قابلة للعد", response_rate_is_none_when_nothing_is_countable),
        run_test("وقت مش مقروء بيتتخطى مش يتخمّن", unreadable_timestamps_are_skipped_not_guessed),
        run_test("الموديول مبيكتبش أي حاجة", the_module_never_writes_anything),
        run_test("مصدر واقع بيتدهور بهدوء", a_dead_datasource_degrades_quietly),
    ]

    supabase_store._client = _original_client

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
