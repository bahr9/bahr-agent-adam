# -*- coding: utf-8 -*-
"""
اختبارات إمساك البلان (2026-08-08).

الخطر الحقيقي في المسار ده مش إنه ميشتغلش -- إنه **يشتغل ويكتب حاجة غلط**.
ملف مشروع بيتقري بعد شهور، والرقم المخترع فيه هيبان كأنه رقم أحمد. فمعظم
الاختبارات هنا بتتأكد إن اللي **مش** المفروض يتخزن مبيتخزنش.

صفر شبكة، صفر Firestore. الكتابة كلها متبدّلة بمسجّل في الذاكرة -- ولو
حد غيّر ده بحيث تعدي كتابة حقيقية، `الكتابة_مبتوصلش_للإنتاج` بيفشل.
"""

import services.plan_capture as pc


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


class _Recorder:
    """بديل save_project_fact -- بيسجّل النداءات بدل ما يكتب."""

    def __init__(self):
        self.calls = []

    def __call__(self, project_name, category, key, value, source="ahmed"):
        self.calls.append({
            "project": project_name, "category": category,
            "key": key, "value": value, "source": source,
        })
        return "اتسجلت في ملف مشروع " + project_name + ": " + key


def _with_mocks(structured, caption="", recorder=None):
    """يشغّل capture_plan بتهيكِل ثابت وكتابة مسجّلة -- ويرجّع كل حاجة مكانها."""
    from services import project_file_service as pfs

    rec = recorder or _Recorder()
    rec.seen_caption = []
    real_structure = pc.structure_plan_text
    real_save = pfs.save_project_fact

    def fake_structure(text, cap=""):
        rec.seen_caption.append(cap)
        return structured

    pc.structure_plan_text = fake_structure
    pfs.save_project_fact = rec
    try:
        return pc.capture_plan("نص بلان", caption), rec
    finally:
        pc.structure_plan_text = real_structure
        pfs.save_project_fact = real_save


PLAN = {
    "project_name": "Rock Eden - essam farag",
    "location": "6 أكتوبر",
    "drawing_date": "21 oct",
    "drawing_number": "A-01",
    "rooms": [
        {"name": "Master Bedroom", "dimensions": "4.20 × 3.15"},
        {"name": "Reception", "dimensions": "6.00 × 4.50"},
        {"name": "Bath 2", "dimensions": None},
    ],
    "notes": ["اتجاه الشمال أعلى اللوحة"],
}


def main():
    results = []

    # ---------- منطق pure ----------

    def المجهول_بيرجع_None_مش_نص():
        """'مش واضح' لو اتخزنت كنص تبقى حقيقة مكتوبة عن حاجة مش معروفة."""
        for marker in ["مش واضح", "غير واضح", "N/A", "-", "", "   ", None]:
            assert pc.clean_value(marker) is None, "المفروض None: " + repr(marker)
        assert pc.clean_value("  4.20 × 3.15 ") == "4.20 × 3.15"

    def مفيش_اسم_يبقى_مفيش_ملف():
        """ملف اسمه 'بدون اسم' تلوث دائم -- السؤال أرخص."""
        assert pc.pick_project_name({"project_name": None}) is None
        assert pc.pick_project_name({"project_name": "مش واضح"}) is None
        assert pc.pick_project_name({"project_name": "Rock Eden"}) == "Rock Eden"

    def جملة_مش_بتعدي_كاسم_مشروع():
        """حزام الأمان: لو التهيكِل رجّع جملة رغم التعليمات، مبتتحفظش.

        الاختبار ده اتكتب بعد ما كشف إن جملة من 57 حرف كانت هتعدي --
        فالحد اتحوّل من "تعريف الاسم" لـ"آخر بوابة".
        """
        sentence = "ابعتلك البلان ده بص عليه وقوللي رأيك في التوزيع بتاع الغرف والحمامات"
        assert pc.pick_project_name({"project_name": sentence}) is None, sentence

    def التعليق_بيوصل_للتهيكِل_عشان_يحكم_عليه():
        """قرار 'ده اسم ولا طلب' بيتاخد في التهيكِل، فلازم يشوف التعليق."""
        _, rec = _with_mocks(PLAN, caption="بلان شقة مدحت")
        assert rec.seen_caption == ["بلان شقة مدحت"], rec.seen_caption

    def الفراغ_بأبعاد_يروح_لأبعاد_واللي_من_غير_يروح_لفراغات():
        facts = pc.facts_from_structured(PLAN)
        by_key = {k: (c, v) for c, k, v in facts}
        assert by_key["Master Bedroom"][0] == "أبعاد", by_key["Master Bedroom"]
        assert by_key["Master Bedroom"][1] == "4.20 × 3.15"
        assert by_key["Bath 2"][0] == "فراغات", by_key["Bath 2"]
        assert "مش واضحة" in by_key["Bath 2"][1], "غياب البعد لازم يتقال صراحة"

    def المساحة_بتتحسب_من_الأبعاد_المستخرجة():
        """الربط الفعلي: الرقم المستخرج لازم يعدّي على الحساب الحتمي الموجود."""
        from services.project_file_service import computed_area
        facts = pc.facts_from_structured(PLAN)
        dims = next(v for c, k, v in facts if k == "Master Bedroom")
        assert computed_area(dims) == 13.23, computed_area(dims)

    def بيانات_اللوحة_المجهولة_مبتتخزنش():
        blank = dict(PLAN, location=None, drawing_date="مش واضح", drawing_number=None)
        keys = [k for _, k, _ in pc.facts_from_structured(blank)]
        for absent in ["الموقع", "تاريخ اللوحة", "رقم اللوحة"]:
            assert absent not in keys, absent + " اتخزن وهو مجهول"

    def فراغ_من_غير_اسم_بيتتخطى():
        data = dict(PLAN, rooms=[{"name": "", "dimensions": "3 × 3"},
                                 {"name": None, "dimensions": "2 × 2"}])
        assert pc.facts_from_structured(data) == [
            f for f in pc.facts_from_structured(data) if f[0] == "ملاحظات"
        ], "فراغ بمفتاح فاضي اتخزن"

    def مفيش_فراغات_يبقى_مفيش_كلام():
        empty = {"project_name": None, "location": None, "drawing_date": None,
                 "drawing_number": None, "rooms": [], "notes": []}
        assert pc.facts_from_structured(empty) == []
        note, rec = _with_mocks(empty)
        assert note is None, note
        assert rec.calls == [], "اتكتب حاجة من بلان فاضي"

    # ---------- المسار كامل (بكتابة مسجّلة) ----------

    def المصدر_بيوصل_plan_مش_ahmed():
        """أهم اختبار: أحمد مقالش الأرقام دي، موديل قراها من رسمة."""
        note, rec = _with_mocks(PLAN)
        assert rec.calls, "مكتبش حاجة"
        bad = [c for c in rec.calls if c["source"] != "plan"]
        assert not bad, "بنود اتسجلت كأن أحمد قالها: " + str(bad[:2])
        assert note and "مش مراجعة" in note, note

    def التهيكِل_لما_يفشل_مفيش_كتابة():
        note, rec = _with_mocks(None)
        assert note is None
        assert rec.calls == [], "اتكتب حاجة والتهيكِل فاشل"

    def مفيش_اسم_يبقى_سؤال_مش_كتابة():
        anon = dict(PLAN, project_name=None)
        note, rec = _with_mocks(anon, caption="")
        assert rec.calls == [], "اتكتب ملف من غير اسم مشروع"
        assert note and "اسم المشروع مش واضح" in note, note

    def الملخص_بيعد_مش_بيوصف():
        facts = pc.facts_from_structured(PLAN)
        line = pc.summarize_capture("Rock Eden", facts, len(facts))
        assert "3 فراغ" in line, line
        assert "2 بأبعاد" in line, line

    def الملخص_بيقول_لما_حاجة_متحفظتش():
        facts = pc.facts_from_structured(PLAN)
        line = pc.summarize_capture("Rock Eden", facts, len(facts) - 2)
        assert "2 بند مقدرتش أحفظه" in line, line

    def الكتابة_مبتوصلش_للإنتاج():
        """حارس: لو حد شال الـmock، النداء الحقيقي هيبان هنا."""
        import services.firebase_service as fb
        real_db = fb.firestore_db
        fb.firestore_db = None            # أي كتابة حقيقية هترمي
        try:
            note, rec = _with_mocks(PLAN)
            assert rec.calls, "المسجّل مشتغلش -- الاختبار أجوف"
        finally:
            fb.firestore_db = real_db

    # ---------- العرض ----------

    def العرض_بيعلّم_المستخرج():
        from services.project_file_service import format_project_file
        doc = {"display_name": "Rock Eden", "facts": {
            "أبعاد": {
                "Master Bedroom": {"value": "4.20 × 3.15", "source": "plan"},
                "Kitchen": {"value": "3.00 × 2.50", "source": "ahmed"},
            }}}
        out = format_project_file(doc)
        master = next(l for l in out.splitlines() if "Master" in l)
        kitchen = next(l for l in out.splitlines() if "Kitchen" in l)
        assert "لسه مش مراجَع" in master, master
        assert "لسه مش مراجَع" not in kitchen, "كلام أحمد اتعلّم كأنه مستخرج: " + kitchen

    def السلوك_القديم_مفيهوش_تغيير():
        """كل النداءات القديمة من غير source لازم تفضل 'ahmed'."""
        import inspect
        from services.project_file_service import save_project_fact
        assert inspect.signature(save_project_fact).parameters["source"].default == "ahmed"

    for name, fn in [
        ("المجهول بيرجع None مش نص", المجهول_بيرجع_None_مش_نص),
        ("مفيش اسم يبقى مفيش ملف", مفيش_اسم_يبقى_مفيش_ملف),
        ("جملة مش بتعدي كاسم مشروع", جملة_مش_بتعدي_كاسم_مشروع),
        ("التعليق بيوصل للتهيكِل", التعليق_بيوصل_للتهيكِل_عشان_يحكم_عليه),
        ("توزيع الفراغات على الفئات صح", الفراغ_بأبعاد_يروح_لأبعاد_واللي_من_غير_يروح_لفراغات),
        ("المساحة بتتحسب من الأبعاد المستخرجة", المساحة_بتتحسب_من_الأبعاد_المستخرجة),
        ("بيانات اللوحة المجهولة مبتتخزنش", بيانات_اللوحة_المجهولة_مبتتخزنش),
        ("فراغ من غير اسم بيتتخطى", فراغ_من_غير_اسم_بيتتخطى),
        ("مفيش فراغات يبقى مفيش كلام", مفيش_فراغات_يبقى_مفيش_كلام),
        ("المصدر بيوصل plan مش ahmed", المصدر_بيوصل_plan_مش_ahmed),
        ("التهيكِل لما يفشل مفيش كتابة", التهيكِل_لما_يفشل_مفيش_كتابة),
        ("مفيش اسم يبقى سؤال مش كتابة", مفيش_اسم_يبقى_سؤال_مش_كتابة),
        ("الملخص بيعد مش بيوصف", الملخص_بيعد_مش_بيوصف),
        ("الملخص بيقول لما حاجة متحفظتش", الملخص_بيقول_لما_حاجة_متحفظتش),
        ("الكتابة مبتوصلش للإنتاج", الكتابة_مبتوصلش_للإنتاج),
        ("العرض بيعلّم المستخرج", العرض_بيعلّم_المستخرج),
        ("السلوك القديم مفيهوش تغيير", السلوك_القديم_مفيهوش_تغيير),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
