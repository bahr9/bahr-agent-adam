# -*- coding: utf-8 -*-
"""
المتابعة: آدم يرجع يتكلم لما يبقى فيه سبب حقيقي.

الحالة اللي ولّدت ده (2026-08-08): آدم بيبادر مرة واحدة بس -- لحظة ما بُعد
يوصل أسوأ درجة لأول مرة. بعدها بيسكت للأبد لحد ما المستوى ينزل ويطلع تاني.
النتيجة العملية: 3 تعارضات قاعدة على `high`، آدم قال عنها مرة، ومكانش
هيفتح الموضوع تاني أبدًا.

القاعدة الأصلية اتحطت لسبب محترم (منع التكرار المزعج)، بس حلّت "ميزنّش"
بإنه "ميرجعش خالص" -- وده الطرف التاني من نفس المشكلة.

قرار أحمد: سببين بس يستاهلوا كلام جديد، والاتنين مش وقت أعمى:
  ١. الحالة اتحركت (العدد اتغيّر وهو لسه على أسوأ درجة)
  ٢. ثبات تام طويل على أسوأ درجة -- السكوت الطويل مش معناه إنها استقرت،
     معناه إن حد سايبها

والقاعدة الحاكمة فوق الاتنين: **{days} بتتحسب من `since` المخزّن أو
الجملة متتقالش**. ممنوع يتخترع رقم مدة، زي المساحات والأسعار بالظبط.

بيشتغل على fake_firestore -- صفر شبكة.
"""

from datetime import datetime, timedelta, timezone

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

    from services import decision_engine, expression_vocabulary

    DIM = "unresolved_conflict"

    def state(count, level="high"):
        return {DIM: {"level": level, "count": count, "evidence_event_ids": ["e1"]}}

    def days_ago(n):
        return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()

    def seed(record):
        decision_engine._save_last_levels({DIM: record})

    def decide(count, level="high"):
        return decision_engine.decide_expression(state(count, level))[DIM]

    # ---------- السلوك الأصلي زي ما هو ----------

    def first_escalation_still_speaks_once():
        seed({"level": "elevated", "count": 1, "since": days_ago(3)})
        d = decide(3)
        assert d["mode"] == "active", d

    def steady_state_stays_silent():
        """نفس العدد، ومدة أقل من الحد -> ساكت. ده الضمان ضد الزن."""
        seed({"level": "high", "count": 3, "since": days_ago(2)})
        d = decide(3)
        assert d["mode"] == "passive", d

    # ---------- السبب الأول: الحالة اتحركت ----------

    def a_changed_count_earns_new_words():
        seed({"level": "high", "count": 3, "since": days_ago(1)})
        d = decide(4)
        assert d["mode"] == "active_changed", d
        assert d["count"] == 4, d

    def resolving_one_while_another_appears_still_counts_as_movement():
        """نفس العدد بعد حركة حقيقية مبيبانش -- ده قيد معروف ومقصود توثيقه."""
        seed({"level": "high", "count": 3, "since": days_ago(1)})
        d = decide(3)
        assert d["mode"] == "passive", (
            "العدد نفسه بيتقرا كسكون. ده مقبول دلوقتي لأن العدد هو الإشارة "
            "الوحيدة المخزّنة -- لو احتجنا نمسك التبديل، الهوية لازم تتخزن مش العدد."
        )

    # ---------- السبب التاني: ثبات طويل ----------

    def long_stasis_makes_him_come_back():
        seed({"level": "high", "count": 3, "since": days_ago(decision_engine.STALE_DAYS + 1)})
        d = decide(3)
        assert d["mode"] == "active_stalled", d
        assert d["days"] == decision_engine.STALE_DAYS + 1, d

    def stasis_just_under_the_threshold_stays_silent():
        seed({"level": "high", "count": 3, "since": days_ago(decision_engine.STALE_DAYS - 1)})
        d = decide(3)
        assert d["mode"] == "passive", d

    def speaking_resets_the_clock_so_it_never_nags():
        """أهم ضمان: بعد ما يتكلم، الساعة تصفّر -- مش يكررها كل فحص (4 مرات/يوم)."""
        seed({"level": "high", "count": 3, "since": days_ago(decision_engine.STALE_DAYS + 5)})
        first = decide(3)
        assert first["mode"] == "active_stalled", first

        second = decide(3)
        assert second["mode"] == "passive", (
            f"اتكلم مرتين ورا بعض -- ده الزن اللي القاعدة الأصلية اتحطت عشانه: {second}"
        )

    # ---------- قاعدة الأمانة: مفيش رقم مخترع ----------

    def a_missing_since_never_invents_a_duration():
        """أهم قاعدة: مفيش `since` -> مفيش جملة فيها مدة، ولا رقم مخمّن."""
        seed({"level": "high", "count": 3, "since": None})
        d = decide(3)
        assert d["mode"] != "active_stalled", f"اخترع مدة من غير since: {d}"
        assert d["days"] is None, d

    def legacy_string_data_reads_without_breaking():
        """البيانات القديمة في الإنتاج نص واحد -- لازم تعدي من غير كسر."""
        seed("high")                       # الشكل القديم بالظبط
        d = decide(3)
        assert d["mode"] != "active_stalled", "اخترع مدة من بيانات قديمة مفيهاش وقت"
        assert d["days"] is None, d

    def unreadable_since_is_treated_as_unknown():
        seed({"level": "high", "count": 3, "since": "مش تاريخ خالص"})
        d = decide(3)
        assert d["mode"] != "active_stalled", d
        assert d["days"] is None, d

    # ---------- الصياغة ----------

    def the_new_wording_exists_and_says_stasis_is_not_stability():
        stalled = expression_vocabulary.get_template(DIM, "high", "active_stalled")
        assert stalled, "مفيش قالب active_stalled"
        assert "{count}" in stalled and "{days}" in stalled, stalled
        assert "الثبات ده مش استقرار" in stalled, (
            "المعنى الجوهري ضاع -- الجملة دي كلها موجودة عشان توصّل إن السكوت مؤشر"
        )
        changed = expression_vocabulary.get_template(DIM, "high", "active_changed")
        assert changed and "{count}" in changed, changed

    def the_wording_never_asks_a_question_it_cannot_receive():
        """قرار أحمد: مفيش سؤال من غير مسار يستقبل الرد."""
        for mode in ("active", "active_changed", "active_stalled"):
            t = expression_vocabulary.get_template(DIM, "high", mode)
            assert t and "؟" not in t, (
                f"قالب {mode} بيسأل سؤال ومفيش مسار يستقبل الإجابة: {t}"
            )

    def every_active_mode_the_engine_can_emit_has_wording():
        """مفيش وضع يقرره المحرك ومفيش ليه نص -- نفس منطق 'مفيش زرار مكسور'."""
        for dim, highest in decision_engine.HIGHEST_TIER.items():
            for mode in ("active", "active_changed", "active_stalled"):
                assert expression_vocabulary.get_template(dim, highest, mode), (
                    f"المحرك يقدر يطلّع {mode} لـ {dim}={highest} ومفيش نص ليه"
                )

    results = [
        run_test("أول وصول لأسوأ درجة لسه بيتكلم", first_escalation_still_speaks_once),
        run_test("استقرار قصير = سكوت", steady_state_stays_silent),
        run_test("العدد اتحرك = كلام جديد", a_changed_count_earns_new_words),
        run_test("نفس العدد بيتقرا كسكون (قيد موثّق)", resolving_one_while_another_appears_still_counts_as_movement),
        run_test("ثبات طويل = يرجع يتكلم", long_stasis_makes_him_come_back),
        run_test("تحت الحد بشوية = لسه ساكت", stasis_just_under_the_threshold_stays_silent),
        run_test("بعد ما يتكلم الساعة تصفّر (مفيش زن)", speaking_resets_the_clock_so_it_never_nags),
        run_test("مفيش since = مفيش مدة مخترعة", a_missing_since_never_invents_a_duration),
        run_test("البيانات القديمة بتعدي من غير كسر", legacy_string_data_reads_without_breaking),
        run_test("since مش مقروء = مجهول", unreadable_since_is_treated_as_unknown),
        run_test("الصياغة موجودة وبتقول المعنى", the_new_wording_exists_and_says_stasis_is_not_stability),
        run_test("مفيش سؤال من غير مسار رد", the_wording_never_asks_a_question_it_cannot_receive),
        run_test("كل وضع يقدر يطلع ليه نص", every_active_mode_the_engine_can_emit_has_wording),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
