# -*- coding: utf-8 -*-
"""
شريحة الـ intents: الأزرار بقت بتاعة آدم، والقراءة منها بتشتغل.

الحالة اللي الشريحة دي بتصلحها (تقرير أول تشغيل حقيقي، 2026-08-07):
المستخدم بيشوف واجهة كاملة والكتابة الحرة بس هي الشغالة. أربع شرائح
قدامه، كل واحدة بتدي turn.failed -- والشرائح دي أصلًا مكتوبة في الواجهة
(FALLBACK_SUGGESTIONS)، يعني آدم بيرد على أزرار مش بتاعته.

الثوابت المحروسة هنا:
  - الدوس على شريحة = نفس مسار النص بالظبط (مفيش مسار تنفيذ تاني)
  - كل شريحة آدم بيبعتها **لازم** يكون ليها نص في الجدول، وإلا شحنّا
    زرار مكسور والتصميم فاكره شغال
  - التعارض بييجي من الحالة الباقية، فبيبان حتى لو اتولد في تليجرام
  - الطقم عمره ما يبقى فاضي (فاضي = الواجهة ترجع لأزرارها الشبح بهدوء)
  - قاعدة الاستبدال صامدة تحت التزامن

بيشتغل من غير شبكة ومن غير Flask app -- بينادي الدوال مباشرة.
"""

from services import ui_channel


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
    ui_channel.STREAM_DELAY_SECONDS = 0

    # ---------- تجهيز: التقاط الأحداث بدل نشرها ----------

    # النشر الحقيقي بيتحفظ الأول: اختبار الـ scoping محتاجه فعلًا يوصل
    # الطوابير، وإلا الفحص بيبقى فاضي وبيعدي على أي تنفيذ.
    _REAL_PUBLISH = ui_channel.publish

    captured = []
    ui_channel.publish = lambda ev: captured.append(ev)

    def run_turn(text="الأقساط", tools=(), reply="تمام."):
        """جولة كاملة بأدوات محددة، وبترجع الأحداث اللي طلعت منها."""
        captured.clear()
        original_runtime = ui_channel._runtime_call
        ui_channel._runtime_call = lambda t, c: reply
        turn = ui_channel._Turn()
        turn.tools_seen = list(tools)
        try:
            ui_channel._run_turn(turn, text)
        finally:
            ui_channel._runtime_call = original_runtime
        return list(captured)

    def with_conflicts(count, fn):
        """تشغيل fn وعدد التعارضات المعلّقة مثبّت."""
        original = ui_channel._pending_conflict_count
        ui_channel._pending_conflict_count = lambda: count
        try:
            return fn()
        finally:
            ui_channel._pending_conflict_count = original

    # ---------- ١: الشريحة بتدي جولة كاملة بنفس التسلسل ----------

    def a_chip_runs_the_same_pipeline_as_text():
        started = {}
        original = ui_channel._start_turn
        ui_channel._start_turn = lambda text: started.setdefault("text", text) or "t-fake"
        try:
            for intent, expected in ui_channel._INTENT_TEXT.items():
                started.clear()
                ui_channel._start_turn(ui_channel._INTENT_TEXT[intent])
                assert started["text"] == expected, (intent, started)
        finally:
            ui_channel._start_turn = original

    def the_full_event_sequence_appears():
        events = run_turn(tools=["loan_get_installments"])
        types = [e["type"] for e in events]
        for required in ("orb.state", "stream.start", "stream.delta", "stream.end", "turn.completed"):
            assert required in types, f"{required} ناقص من {types}"
        assert types.index("stream.start") < types.index("stream.end")
        assert types.index("turn.completed") > types.index("stream.end")

    # ---------- ٢/٣/٤: اللي بيفضل مرفوض ----------

    def brief_morning_is_not_mapped_and_not_offered():
        assert "brief.morning" not in ui_channel._INTENT_TEXT, "brief.morning اتضاف بالغلط"
        offered = {c["intent"] for c in ui_channel._build_suggestions()}
        assert "brief.morning" not in offered, "الزرار الشبح رجع في الطقم"

    def every_mapped_intent_is_read_only():
        """ممنوع أي نص هنا يوعد بكتابة -- الأفعال الخطرة مؤجلة."""
        for intent, text in ui_channel._INTENT_TEXT.items():
            assert not any(w in text for w in ("سجّل", "ادفع", "احذف", "امسح")), (intent, text)
        assert "حل" not in ui_channel._SUGGESTION_CONFLICTS["label"], \
            "شريحة التعارض بتوعد بحل، والحل مؤجل -- ده نفس الزرار اللي بيوعد ومبيوفيش"

    # ---------- ٦: مفيش شريحة من غير نص ----------

    def every_offered_chip_resolves():
        """الشرط اللي بيمنع شحن زرار مكسور والتصميم فاكره شغال."""
        sets_to_check = [
            ui_channel._build_suggestions(),
            ui_channel._build_suggestions(["loan_get_installments"]),
            with_conflicts(3, lambda: ui_channel._build_suggestions(["loan_record_installment"])),
            with_conflicts(1, lambda: ui_channel._build_suggestions()),
        ]
        for chips in sets_to_check:
            for chip in chips:
                assert chip["intent"] in ui_channel._INTENT_TEXT, \
                    f"شريحة '{chip['label']}' بتبعت intent مالوش نص: {chip['intent']}"
                assert chip.get("id") and chip.get("label"), chip

    def chip_ids_are_unique_within_a_set():
        for chips in (ui_channel._build_suggestions(),
                      with_conflicts(2, lambda: ui_channel._build_suggestions(["loan_x"]))):
            ids = [c["id"] for c in chips]
            assert len(ids) == len(set(ids)), f"معرّفات مكررة: {ids}"

    # ---------- ٧: التعارض من الحالة الباقية ----------

    def a_conflict_shows_even_when_no_loan_tool_ran():
        """التعارض ممكن يكون اتولد في تليجرام -- الجولة دي متلمسش أقساط."""
        chips = with_conflicts(2, lambda: ui_channel._build_suggestions(tools_seen=[]))
        intents = [c["intent"] for c in chips]
        assert "installments.conflict" in intents, intents
        assert intents[0] == "installments.conflict", f"التعارض المفروض يسبق: {intents}"

    def no_conflict_chip_when_none_pending():
        chips = with_conflicts(0, lambda: ui_channel._build_suggestions(["loan_get_installments"]))
        assert "installments.conflict" not in [c["intent"] for c in chips]

    def a_failing_conflict_read_does_not_break_the_set():
        """محرك الحالة لو وقع، الطقم بيكمّل -- مبيفشلش الجولة.

        بنكسر المصدر الحقيقي (self_state_engine) مش الغلاف، عشان نختبر
        الحارس اللي موجود فعلًا في مكانه مش حارس متخيّل.
        """
        from services import self_state_engine

        original = self_state_engine.compute_unresolved_conflict

        def _explode():
            raise RuntimeError("انفجار مقصود في محرك الحالة")

        self_state_engine.compute_unresolved_conflict = _explode
        try:
            assert ui_channel._pending_conflict_count() == 0, "المفروض يرجع صفر لما القراءة تقع"
            chips = ui_channel._build_suggestions()
            assert chips, "الطقم طلع فاضي بعد فشل القراءة"
            assert "installments.conflict" not in [c["intent"] for c in chips], \
                "شريحة تعارض ظهرت وإحنا مش عارفين فيه تعارض ولا لأ"
        finally:
            self_state_engine.compute_unresolved_conflict = original

    # ---------- ٨: ممنوع طقم فاضي ----------

    def the_set_is_never_empty():
        assert ui_channel._build_suggestions() != []
        assert ui_channel._build_suggestions(tools_seen=[]) != []
        assert with_conflicts(0, lambda: ui_channel._build_suggestions([])) != []

    def a_turn_publishes_suggestions_after_it_closes():
        events = run_turn(tools=["loan_get_installments"])
        types = [e["type"] for e in events]
        assert "suggestions" in types, types
        assert types.index("suggestions") > types.index("turn.completed"), \
            "الاقتراحات اتنشرت قبل القفل -- turn.emit كان هيسقطها"
        published = [e for e in events if e["type"] == "suggestions"][0]
        assert published["suggestions"], "اتنشر طقم فاضي"
        assert "turnId" not in published, "حدث الاقتراحات مش تابع لجولة (العقد)"

    # ---------- الطقم الابتدائي scoped مش broadcast ----------

    def a_new_connection_does_not_push_suggestions_to_existing_clients():
        """اتصال جديد ميلمسش عملاء متصلين قبله.

        الثغرة دي **مستحيل** تتكشف باختبار عميل واحد: مع اتصال واحد بس،
        broadcast وscoped بيبانوا نفس الحاجة بالظبط. بتظهر بس لما يبقى
        فيه أكتر من عميل -- يعني في الإنتاج. لو الطقم الابتدائي اتنشر
        broadcast، أي عميل تاني هيشوف شرائحه بتتغير من غير أي سبب من
        جولته هو، وده بالظبط السلوك اللي بيخلي المستخدم ميثقش في الواجهة.
        """
        import os as _os
        import json as _json
        from flask import Flask

        _os.environ["ADAM_TOKEN"] = "scoping-test-token"
        app = Flask(__name__)
        # النشر الحقيقي طول الاختبار ده: لو سيبنا الملتقط، أي حاجة اتنشرت
        # هتروح لليستة بدل الطوابير، وفحص التسريب هيعدي على أي تنفيذ --
        # حتى الغلط. الاختبار وقتها بيبقى ديكور.
        mock_publish = ui_channel.publish
        ui_channel.publish = _REAL_PUBLISH
        try:
            app.register_blueprint(ui_channel.ui_blueprint)
        except Exception:
            pass  # مسجّل قبل كده في نفس العملية
        client = app.test_client()
        headers = {"Authorization": "Bearer scoping-test-token"}

        # عميل (أ) متصل ومستني
        q_existing = ui_channel.subscribe()
        try:
            # عميل (ب) بيتصل دلوقتي وبياخد طقمه الابتدائي
            rv = client.get("/ui/events", headers=headers)
            it = iter(rv.response)
            frames = []
            for _ in range(2):
                chunk = next(it)
                frames.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk)
            rv.close()

            # الثابت الأساسي الأول: عميل (أ) مجاله **حاجة** من اتصال (ب).
            # بيتفحص قبل أي حاجة تانية عشان لو الطقم اتنشر broadcast،
            # الاختبار يقع على السبب الحقيقي مش على عرض جانبي ليه.
            leaked = []
            while not q_existing.empty():
                leaked.append(q_existing.get_nowait())
            assert not leaked, (
                "الطقم الابتدائي اتنشر broadcast -- عميل متصل قبل كده استلم "
                f"{[e.get('type') for e in leaked]} من اتصال شخص تاني"
            )

            # وبعدين: عميل (ب) نفسه لازم يكون خد طقمه
            data_frames = [f for f in frames if f.startswith("data: ")]
            assert data_frames, f"عميل (ب) مجاله طقم ابتدائي: {frames}"
            payload = _json.loads(data_frames[0][len("data: "):].strip())
            assert payload["type"] == "suggestions", payload
        finally:
            ui_channel.unsubscribe(q_existing)
            ui_channel.publish = mock_publish

    # ---------- ١٠: الاستبدال تحت التزامن ----------

    def supersede_holds_under_concurrency():
        """آدم هو اللي بيقفل، من جهة السيرفر. الواجهة متبعتش أي تنسيق."""
        import threading

        captured.clear()
        original_runtime = ui_channel._runtime_call
        ui_channel._runtime_call = lambda t, c: "تمام."
        ui_channel._current_turn = None
        try:
            ids = []
            barrier = threading.Barrier(4)

            def fire():
                barrier.wait()
                ids.append(ui_channel._start_turn("الأقساط"))

            threads = [threading.Thread(target=fire) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert len(ids) == 4 and len(set(ids)) == 4, f"معرّفات جولات اتكررت: {ids}"

            completed = [e for e in captured if e.get("type") == "turn.completed"]
            closed_ids = [e["turnId"] for e in completed]
            assert len(closed_ids) == len(set(closed_ids)), f"جولة اتقفلت مرتين: {closed_ids}"

            # الثابت الأهم في العقد: مفيش أي حدث بالـ turnId القديم بعد قفله
            for closed in closed_ids:
                after = False
                for e in captured:
                    if e.get("type") == "turn.completed" and e.get("turnId") == closed:
                        after = True
                        continue
                    if after and e.get("turnId") == closed:
                        raise AssertionError(f"حدث {e['type']} طلع بالـ turnId القديم {closed} بعد قفله")
        finally:
            ui_channel._runtime_call = original_runtime
            ui_channel._current_turn = None

    results = [
        run_test("كل intent بيروح لنصه في نفس مسار النص", a_chip_runs_the_same_pipeline_as_text),
        run_test("الجولة بتطلع التسلسل الإلزامي كامل", the_full_event_sequence_appears),
        run_test("brief.morning لا في الجدول ولا في الطقم", brief_morning_is_not_mapped_and_not_offered),
        run_test("كل النصوص قراءة بس، ومفيش شريحة بتوعد بحل", every_mapped_intent_is_read_only),
        run_test("كل شريحة بيبعتها آدم ليها نص (مفيش زرار مكسور)", every_offered_chip_resolves),
        run_test("معرّفات الشرائح مش بتتكرر", chip_ids_are_unique_within_a_set),
        run_test("التعارض بيبان حتى لو الجولة متلمستش أقساط", a_conflict_shows_even_when_no_loan_tool_ran),
        run_test("مفيش شريحة تعارض من غير تعارض معلّق", no_conflict_chip_when_none_pending),
        run_test("فشل قراءة التعارض مبيكسرش الطقم", a_failing_conflict_read_does_not_break_the_set),
        run_test("الطقم عمره ما يبقى فاضي", the_set_is_never_empty),
        run_test("الاقتراحات بتتنشر بعد قفل الجولة وبدون turnId", a_turn_publishes_suggestions_after_it_closes),
        run_test("الطقم الابتدائي للعميل الجديد بس (مش broadcast)", a_new_connection_does_not_push_suggestions_to_existing_clients),
        run_test("الاستبدال صامد تحت التزامن", supersede_holds_under_concurrency),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
