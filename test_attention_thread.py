# -*- coding: utf-8 -*-
"""
خيط الانتباه: إيه المفتوح، من إمتى، وآدم قال عنه إيه؟

الفجوة رقم ١ من تشخيص 2026-08-08: آدم عنده ذاكرة مالهاش خيط -- بيخزّن
أحداث ولقطات وتعبيرات كل واحدة لوحدها، ومش قادر يجاوب السؤال اللي بيميز
فرد الأسرة عن نظام المراقبة: "دي مفتوحة من إمتى، وأنا قلت عنها إيه؟"

الثابت الأهم المحروس هنا: **مش عارف ≠ صفر.** أي مدة مش محسوبة من `since`
مخزّن لازم ترجع None، والجملة اللي محتاجاها متتقالش خالص -- ممنوع رقم
يوم يتخترع. نفس قاعدة المساحات والأسعار.

والثابت التاني: الموديول **قراءة بس**. أي كتابة فيه = مسار جديد ينفع يقع
في حتة آدم بيتكلم منها.

كل المصادر مستبدلة -- صفر شبكة، صفر Firestore.
"""

from datetime import datetime, timedelta, timezone

NOW = datetime.now(timezone.utc)


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
    # الأطراف بتتقرا من Firestore حقيقي (مش مصدر ينفع يتبدل بدالة)، فلازم
    # الـ fake يتركّب. باقي المصادر بتتبدل مباشرة تحت.
    from fake_firestore import install_fake_firestore
    db = install_fake_firestore()

    from services import attention_thread as th
    from services import self_state_engine, decision_engine, initiative_loop

    def ago(days):
        return (NOW - timedelta(days=days)).isoformat()

    def setup(state=None, tracked=None, outcomes=None):
        self_state_engine.compute_self_state = lambda: (state or {})
        decision_engine.get_tracked_levels = lambda: (tracked or {})
        initiative_loop.get_initiative_outcomes = lambda *a, **k: (outcomes or [])

    CONFLICT_OPEN = {
        "unresolved_conflict": {"level": "high", "count": 3, "evidence_event_ids": ["e"]},
    }

    # ---------- الأساسيات ----------

    def an_open_item_appears_with_its_age():
        setup(CONFLICT_OPEN, {"unresolved_conflict": {"level": "high", "count": 3, "since": ago(9)}})
        t = th.get_open_threads()
        assert len(t) == 1, t
        assert t[0]["days_open"] == 9, t[0]
        assert t[0]["count"] == 3, t[0]

    def a_closed_item_is_not_a_thread():
        setup({"unresolved_conflict": {"level": "none", "count": 0}}, {})
        assert th.get_open_threads() == []

    def tracking_stability_is_never_a_thread():
        """ملاحظة محايدة مش حاجة مفتوحة -- نفس سبب استبعادها من HIGHEST_TIER."""
        setup({"tracking_stability": {"level": "frequent_corrections", "count": 5}}, {})
        assert th.get_open_threads() == []

    # ---------- قاعدة الأمانة: مش عارف ≠ صفر ----------

    def a_missing_since_yields_unknown_not_zero():
        setup(CONFLICT_OPEN, {"unresolved_conflict": {"level": "high", "count": 3, "since": None}})
        t = th.get_open_threads()[0]
        assert t["days_open"] is None, f"اخترع مدة من غير since: {t}"

    def an_unreadable_since_yields_unknown():
        setup(CONFLICT_OPEN, {"unresolved_conflict": {"level": "high", "count": 3, "since": "مش تاريخ"}})
        assert th.get_open_threads()[0]["days_open"] is None

    def a_dimension_with_no_tracked_record_yields_unknown():
        setup(CONFLICT_OPEN, {})          # مفيش سجل مدة خالص
        assert th.get_open_threads()[0]["days_open"] is None

    def the_sentence_omits_the_duration_when_unknown():
        """أقصر وأصدق: 'فيه 3' أأمن من 'فيه 3 من 7 أيام' والسبعة تخمين."""
        setup(CONFLICT_OPEN, {"unresolved_conflict": {"level": "high", "count": 3, "since": None}})
        s = th.describe_open_threads()
        assert "3" in s, s
        assert "يوم" not in s, f"طلّع مدة وهو مش عارفها: {s}"

    # ---------- الخيط: قال ومحصلش رد ----------

    def an_unanswered_initiative_is_surfaced_with_its_age():
        setup(
            CONFLICT_OPEN,
            {"unresolved_conflict": {"level": "high", "count": 3, "since": ago(12)}},
            [{"dimension": "unresolved_conflict", "sent_at": ago(5),
              "responded": False, "initiative_text": "تنبيه"}],
        )
        t = th.get_open_threads()[0]
        assert t["spoke_about_it"] is True, t
        assert t["answered"] is False, t
        assert t["unanswered_days"] == 5, t
        assert "محصلش رد" in th.describe_open_threads()

    def an_answered_initiative_is_not_flagged_as_unanswered():
        setup(
            CONFLICT_OPEN,
            {"unresolved_conflict": {"level": "high", "count": 3, "since": ago(12)}},
            [{"dimension": "unresolved_conflict", "sent_at": ago(2),
              "responded": True, "initiative_text": "تنبيه"}],
        )
        t = th.get_open_threads()[0]
        assert t["answered"] is True and t["unanswered_days"] is None, t
        assert "رد" in th.describe_open_threads()

    def never_spoken_about_is_stated_plainly():
        setup(CONFLICT_OPEN, {"unresolved_conflict": {"level": "high", "count": 3, "since": ago(4)}}, [])
        t = th.get_open_threads()[0]
        assert t["spoke_about_it"] is False and t["answered"] is None, t
        assert "مقلتش" in th.describe_open_threads()

    def the_most_recent_initiative_wins():
        setup(
            CONFLICT_OPEN,
            {"unresolved_conflict": {"level": "high", "count": 3, "since": ago(20)}},
            [{"dimension": "unresolved_conflict", "sent_at": ago(15), "responded": True,
              "initiative_text": "قديم"},
             {"dimension": "unresolved_conflict", "sent_at": ago(3), "responded": False,
              "initiative_text": "جديد"}],
        )
        t = th.get_open_threads()[0]
        assert t["last_spoken_text"] == "جديد", t
        assert t["unanswered_days"] == 3, t

    # ---------- الترتيب ----------

    def the_oldest_open_comes_first_and_unknown_ages_go_last():
        setup(
            {"unresolved_conflict": {"level": "high", "count": 1},
             "pending_obligation_load": {"level": "concern", "count": 9}},
            {"unresolved_conflict": {"level": "high", "count": 1, "since": None},
             "pending_obligation_load": {"level": "concern", "count": 9, "since": ago(30)}},
        )
        dims = [t["dimension"] for t in th.get_open_threads()]
        assert dims[0] == "pending_obligation_load", f"المعروف مدته المفروض يتصدر: {dims}"
        assert dims[-1] == "unresolved_conflict", dims

    # ---------- الصمود ----------

    def a_failing_source_degrades_instead_of_raising():
        def boom():
            raise RuntimeError("انفجار مقصود")
        self_state_engine.compute_self_state = boom
        assert th.get_open_threads() == []
        assert isinstance(th.describe_open_threads(), str)

    def a_partial_source_failure_still_returns_the_thread():
        """المدد وقعت -> الخيط بيكمّل من غير 'من إمتى' بدل ما يختفي."""
        setup(CONFLICT_OPEN, {}, [])
        def boom():
            raise RuntimeError("انفجار مقصود")
        decision_engine.get_tracked_levels = boom
        t = th.get_open_threads()
        assert len(t) == 1 and t[0]["days_open"] is None, t

    # ---------- الأطراف (الفجوة ٣): شغل بعته ومحدش خده ----------

    def seed_tasks(tasks):
        """tasks = [(target, action, status, age_hours)]"""
        from config import AGENT_TASKS_COLLECTION
        for i, (target, action, status, hours) in enumerate(tasks):
            db.collection(AGENT_TASKS_COLLECTION).document(f"t{i}").set({
                "task_id": f"t{i}", "target": target, "action": action,
                "status": status,
                "created_at": (NOW - timedelta(hours=hours)).isoformat(),
            })

    def clear_tasks():
        from config import AGENT_TASKS_COLLECTION
        for k in list(db.all_docs(AGENT_TASKS_COLLECTION)):
            db.collection(AGENT_TASKS_COLLECTION).document(k).delete()

    def an_unclaimed_task_becomes_a_thread():
        setup({}, {}, [])
        clear_tasks()
        seed_tasks([("مداد", "حاجة مهمة", "pending", 48)])
        t = [x for x in th.get_open_threads() if x.get("kind") == "agent_task"]
        assert len(t) == 1, t
        assert t[0]["task_state"] == "unclaimed" and t[0]["days_open"] == 2, t[0]
        assert "محدش خده" in th.describe_open_threads()

    def a_task_still_inside_the_poll_window_is_not_flagged():
        """مداد بيعمل poll كل دقيقتين -- تاسك عمره دقايق لسه في الطابور مش واقف."""
        setup({}, {}, [])
        clear_tasks()
        seed_tasks([("مداد", "لسه جديد", "pending", 0.1)])
        assert [x for x in th.get_open_threads() if x.get("kind") == "agent_task"] == []

    def a_done_task_is_never_a_thread():
        setup({}, {}, [])
        clear_tasks()
        seed_tasks([("مداد", "خلصت", "done", 48)])
        assert [x for x in th.get_open_threads() if x.get("kind") == "agent_task"] == []

    def a_recent_failure_is_surfaced_and_an_old_one_is_not():
        setup({}, {}, [])
        clear_tasks()
        seed_tasks([("مداد", "فشل قريب", "failed", 24),
                    ("مداد", "فشل قديم", "failed", 24 * 40)])
        t = [x for x in th.get_open_threads() if x.get("kind") == "agent_task"]
        assert len(t) == 1 and t[0]["action"] == "فشل قريب", t

    def a_long_action_is_truncated_before_it_reaches_the_context():
        """النص بيدخل سياق آدم في كل نداء -- فقرة كاملة هنا تكلفة متكررة."""
        setup({}, {}, [])
        clear_tasks()
        seed_tasks([("Hope", "ك" * 400, "pending", 48)])
        line = th.describe_open_threads()
        assert len(line) < 250, f"السطر طويل جدًا ({len(line)} حرف): {line[:120]}"
        assert "…" in line, "المفروض يبان إنه مقصوص"

    def a_task_with_no_timestamp_is_shown_without_an_age():
        """معلّق من غير وقت لسه معلومة -- بنعرضه من غير مدة مش نتخطاه."""
        from config import AGENT_TASKS_COLLECTION
        setup({}, {}, [])
        clear_tasks()
        db.collection(AGENT_TASKS_COLLECTION).document("x").set({
            "task_id": "x", "target": "مداد", "action": "من غير وقت", "status": "pending",
        })
        t = [x for x in th.get_open_threads() if x.get("kind") == "agent_task"]
        assert len(t) == 1 and t[0]["days_open"] is None, t
        assert "يوم" not in th.describe_open_threads(), "اخترع مدة لتاسك من غير وقت"

    def self_state_and_limbs_share_one_thread():
        """"إيه المفتوح" سؤال واحد -- سواء المفتوح جواه ولا في طرف منه."""
        setup(CONFLICT_OPEN, {"unresolved_conflict": {"level": "high", "count": 3, "since": ago(2)}}, [])
        clear_tasks()
        seed_tasks([("مداد", "واقف", "pending", 48)])
        kinds = {x["kind"] for x in th.get_open_threads()}
        assert kinds == {"self_state", "agent_task"}, kinds

    def the_module_never_writes_anything():
        import inspect
        src = inspect.getsource(th)
        for forbidden in (".set(", ".insert(", ".update(", ".delete(", "record_event"):
            assert forbidden not in src, f"الموديول بيكتب ({forbidden}) -- المفروض قراءة بس"

    results = [
        run_test("الحاجة المفتوحة بتظهر بعمرها", an_open_item_appears_with_its_age),
        run_test("المقفولة مش خيط", a_closed_item_is_not_a_thread),
        run_test("tracking_stability عمرها ما تكون خيط", tracking_stability_is_never_a_thread),
        run_test("مفيش since = مش عارف مش صفر", a_missing_since_yields_unknown_not_zero),
        run_test("since مش مقروء = مش عارف", an_unreadable_since_yields_unknown),
        run_test("بُعد من غير سجل مدة = مش عارف", a_dimension_with_no_tracked_record_yields_unknown),
        run_test("الجملة بتشيل المدة لما تكون مجهولة", the_sentence_omits_the_duration_when_unknown),
        run_test("قال ومحصلش رد بيظهر بعمره", an_unanswered_initiative_is_surfaced_with_its_age),
        run_test("اللي اترد عليه مش بيتعلّم كمهمل", an_answered_initiative_is_not_flagged_as_unanswered),
        run_test("اللي مقلش عنه بيتقال صراحة", never_spoken_about_is_stated_plainly),
        run_test("آخر مبادرة هي المعتبرة", the_most_recent_initiative_wins),
        run_test("الأقدم الأول والمجهول في الآخر", the_oldest_open_comes_first_and_unknown_ages_go_last),
        run_test("مصدر واقع بيتدهور مش بينفجر", a_failing_source_degrades_instead_of_raising),
        run_test("فشل جزئي بيسيب الخيط شغال", a_partial_source_failure_still_returns_the_thread),
        run_test("الموديول مبيكتبش أي حاجة", the_module_never_writes_anything),
        run_test("تاسك محدش خده بيبقى خيط", an_unclaimed_task_becomes_a_thread),
        run_test("تاسك لسه في نافذة الـ poll مش واقف", a_task_still_inside_the_poll_window_is_not_flagged),
        run_test("التاسك الخالص مش خيط", a_done_task_is_never_a_thread),
        run_test("الفشل القريب بيبان والقديم لأ", a_recent_failure_is_surfaced_and_an_old_one_is_not),
        run_test("الأكشن الطويل بيتقص قبل السياق", a_long_action_is_truncated_before_it_reaches_the_context),
        run_test("تاسك من غير وقت بيبان من غير مدة", a_task_with_no_timestamp_is_shown_without_an_age),
        run_test("الحالة والأطراف في خيط واحد", self_state_and_limbs_share_one_thread),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
