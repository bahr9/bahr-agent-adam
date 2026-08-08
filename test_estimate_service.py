# -*- coding: utf-8 -*-
"""
اختبارات المقايسة (2026-08-08).

المقايسة بتخرج من بحر كعرض سعر لعميل. فالخطر مش إنها متطلعش رقم -- الخطر
إنها **تطلع رقم كامل نصه مخترع**: فراغ اتحسب بصفر، سعر اتخمّن، بند اتخطى
بصمت، أو تحذير جه بعد الرقم بدل ما يسبقه.

كل اختبار هنا على واحدة من دول. صفر Firestore وصفر شبكة.
"""

import services.estimate_service as est
from services.project_file_service import resolve_project_name as _REAL_RESOLVE
from services.price_base_service import search_items as _REAL_SEARCH


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


DOC = {
    "display_name": "Rock Eden - essam farag",
    "facts": {
        "أبعاد": {
            "Master Bedroom": {"value": "4.20 × 3.15", "computed_area_m2": 13.23},
            "Reception": {"value": "6.00 × 4.50", "computed_area_m2": 27.0},
            "Kitchen": {"value": "مش واضح"},                       # مفيش مساحة
        },
        "فراغات": {
            "Bath 1": {"value": "الفراغ موجود في البلان -- الأبعاد مش واضحة"},
        },
    },
}

PORCELAIN = {"item": "متر البورسلين 60×120", "price": "500:2000", "unit": "متر مسطح"}
LABOUR = {"item": "مصنعية تركيب بورسلين 60×120", "price": "150", "unit": "متر مسطح"}


def main():
    results = []

    # ---------- الفراغات ----------

    def الفراغ_من_غير_أبعاد_بيتقال_مش_بيتحسب_صفر():
        """أخطر شكل للخطأ: فراغ يختفي من الحساب ومن التحذير مع بعض."""
        measured, unmeasured = est.measured_rooms(DOC)
        assert [n for n, _ in measured] == ["Master Bedroom", "Reception"], measured
        assert set(unmeasured) == {"Kitchen", "Bath 1"}, unmeasured

    def المساحة_مجموع_المحسوب_بس():
        measured, _ = est.measured_rooms(DOC)
        assert abs(sum(a for _, a in measured) - 40.23) < 0.001, measured

    def ملف_فاضي_مبيرجعش_أصفار():
        measured, unmeasured = est.measured_rooms({"facts": {}})
        assert measured == [] and unmeasured == []

    # ---------- الصناديق ----------

    def الصناديق_بتتقرّب_لفوق():
        """100 م² ÷ 1.44 = 69.4 -> 70 صندوق. نص صندوق مش بيتشترى."""
        assert est.boxes_needed(100, 1.44) == 70
        assert est.boxes_needed(1.44, 1.44) == 1
        assert est.boxes_needed(1.45, 1.44) == 2

    def التغطية_المجهولة_مبتتخمنش_من_المقاس():
        """محتوى الصندوق مش هو مقاس البلاطة، والمصانع بتختلف."""
        for coverage in (None, 0, -1):
            assert est.boxes_needed(100, coverage) is None, coverage

    # ---------- السطور ----------

    def البند_من_غير_سعر_بيترجع_بالاسم():
        line = est.build_line({"item": "باب خشب", "basis": "floor"}, 40.23, None)
        assert "skipped" in line and "مش في قاعدة أسعارك" in line["skipped"], line
        assert line["quantity"] == 40.23, "الكمية اتحسبت برضه عشان يبان الناقص إيه"

    def السعر_المش_مفهوم_بيترفض():
        line = est.build_line({"item": "x", "basis": "floor"}, 10,
                              {"item": "x", "price": "حسب الشغل"})
        assert "skipped" in line and "مش مفهوم" in line["skipped"], line

    def الحوائط_من_غير_كمية_مبتتحسبش():
        """الارتفاع مش مكتوب في البلان -- فالمحيط لازم ييجي من أحمد."""
        line = est.build_line({"item": "متر النقاش", "basis": "manual"}, 40.23,
                              {"item": "متر النقاش", "price": "75"})
        assert "skipped" in line and "كمية يدوية ناقصة" in line["skipped"], line

    def الكمية_اليدوية_بتشتغل():
        line = est.build_line({"item": "بيت النور", "basis": "manual", "quantity": 42,
                               "unit": "متر طولي"}, 40.23,
                              {"item": "بيت النور", "price": "300"})
        assert line["quantity"] == 42 and line["unit"] == "متر طولي", line
        assert line["cost_low"] == 12600, line

    def المدى_بيفضل_مدى_مبيتوسطش():
        line = est.build_line({"item": "متر البورسلين 60×120", "basis": "floor"}, 40.23, PORCELAIN)
        assert line["unit_price_low"] == 500 and line["unit_price_high"] == 2000, line
        assert abs(line["cost_low"] - 20115) < 0.01, line
        assert abs(line["cost_high"] - 80460) < 0.01, line

    def الفلوس_بتتحسب_على_المشترى_مش_المركّب():
        """بالصناديق: 40.23 م² -> 28 صندوق = 40.32 م² مشتراة."""
        entry = dict(PORCELAIN, box_coverage_m2=1.44)
        line = est.build_line({"item": "متر البورسلين 60×120", "basis": "floor"}, 40.23, entry)
        assert line["boxes"] == 28, line["boxes"]
        assert abs(line["billed_quantity"] - 40.32) < 0.01, line
        assert line["billed_quantity"] > line["quantity"], "الفلوس اتحسبت على أقل من المشترى"

    def أساس_غلط_بيترفض():
        line = est.build_line({"item": "x", "basis": "حاجة"}, 10, PORCELAIN)
        assert "skipped" in line, line

    # ---------- التقرير ----------

    def التحذير_بيسبق_الرقم():
        """رقم جزئي متقري قبل تحذيره بيدخل الدماغ كإجمالي."""
        measured, unmeasured = est.measured_rooms(DOC)
        line = est.build_line({"item": "متر البورسلين 60×120", "basis": "floor"}, 40.23, PORCELAIN)
        out = est.format_estimate("Rock Eden", measured, unmeasured, [line])
        assert out.index("تقدير جزئي") < out.index("الإجمالي"), out[:200]
        assert "Kitchen" in out and "Bath 1" in out, "الفراغ الناقص مذكرش بالاسم"

    def المصنعية_والخامة_سطرين_مش_مجموعين():
        """قرار أحمد: بيفصلهم فعليًا -- ممنوع دمج."""
        measured, unmeasured = est.measured_rooms(DOC)
        lines = [
            est.build_line({"item": "متر البورسلين 60×120", "basis": "floor"}, 40.23, PORCELAIN),
            est.build_line({"item": "مصنعية تركيب بورسلين 60×120", "basis": "floor"}, 40.23, LABOUR),
        ]
        out = est.format_estimate("Rock Eden", measured, unmeasured, lines)
        assert "متر البورسلين 60×120" in out and "مصنعية تركيب بورسلين 60×120" in out
        assert out.count("•") == 2, "البندين اتدمجوا في سطر"

    def المش_محسوب_بيتعرض_بالاسم_والسبب():
        measured, unmeasured = est.measured_rooms(DOC)
        lines = [est.build_line({"item": "باب خشب", "basis": "floor"}, 40.23, None)]
        out = est.format_estimate("Rock Eden", measured, unmeasured, lines)
        assert "مش محسوب" in out and "باب خشب" in out, out
        assert "save_prices_bulk" in out, "مقالش لأحمد يعمل إيه بعدها"

    def مفيش_بنود_محسوبة_بيتقال_صراحة():
        measured, unmeasured = est.measured_rooms(DOC)
        out = est.format_estimate("Rock Eden", measured, unmeasured, [])
        assert "محتاجة أسعار مسجّلة" in out, out
        assert "الإجمالي" not in out, "طلع إجمالي من غير ولا بند"

    def الخطوة_الجاية_حسب_سبب_التعذر():
        """كانت بتقول "سجّل أسعار" والسبب أبعاد ناقصة -- شغل ملهوش لازمة."""
        no_dims = {"facts": {"فراغات": {"الريسبشن": {"value": "x"},
                                        "الماستر": {"value": "y"}}}}
        m, u = est.measured_rooms(no_dims)
        out = est.format_estimate("Rock Eden", m, u, [])
        assert "الناقص **أبعاد** مش أسعار" in out, out
        assert "محتاجة أسعار مسجّلة" not in out, out
        assert "0 م²" not in out, "عرض صفر متر كأنها مساحة"

    def اقتراح_تسجيل_الأسعار_بيظهر_لما_يكون_ده_السبب():
        m, u = est.measured_rooms(DOC)
        with_price_gap = [est.build_line({"item": "باب", "basis": "floor"}, 40.23, None)]
        assert "save_prices_bulk" in est.format_estimate("R", m, u, with_price_gap)
        only_qty_gap = [est.build_line({"item": "متر النقاش", "basis": "manual"}, 40.23,
                                       {"item": "متر النقاش", "price": "75"})]
        assert "save_prices_bulk" not in est.format_estimate("R", m, u, only_qty_gap),             "اقترح تسجيل أسعار والسعر مش هو الناقص"

    # ---------- التسجيل ----------

    # ---------- المسار كامل: estimate_project_cost نفسها ----------
    # كل اللي فوق على دوال pure. الدالة اللي آدم بينديها فعلاً -- واللي
    # ناتجها بيروح لعميل -- مكانتش متغطية بولا اختبار (اتكشف في مراجعة
    # 2026-08-08). أخطر فرع فيها هو حل اسم البند: مرشحين = التباس، والتباس
    # في سعر جوه مقايسة أخطر من بند ناقص.

    class _Files:
        def __init__(self, names, doc):
            self._names, self._doc = names, doc
            self.reads = []
        def list_project_names(self):
            return list(self._names)
        def resolve_project_name(self, q, names):
            # الدالة الحقيقية اتمسكت وقت الاستيراد. لو اتندهت من جوه هنا
            # بـimport هتلاقي الـfake نفسه (لأنه هو اللي متركب على الحزمة)
            # وتنده نفسها لحد RecursionError.
            return _REAL_RESOLVE(q, names)
        def project_id_for_name(self, n):
            return "proj-x"
        def _collection(self):
            outer = self
            class _Snap:
                exists = True
                def to_dict(_self): return outer._doc
            class _Doc:
                def get(_self): return _Snap()
            class _Col:
                def document(_self, _id): return _Doc()
            return _Col()

    class _Prices:
        def __init__(self, rows):
            self._rows = rows
        def _all_docs_supabase_first(self):
            return list(self._rows)
        def search_items(self, q, names):
            return _REAL_SEARCH(q, names)

    def _swap(files, prices):
        """يبدّل الموديولين في **المكانين**: sys.modules وحزمة services.

        estimate_project_cost بتستخدم شكلين استيراد لنفس الموديول --
        `from services import project_file_service as pfs` (بيقرا من الحزمة)
        و`from services.project_file_service import _collection` (بيقرا من
        sys.modules). تبديل واحد منهم بس بيسيب النص التاني بينده الحقيقي،
        واللي بيرمي "Firestore مش متصل" في الاختبار.
        """
        import sys, services
        keys = ("services.project_file_service", "services.price_base_service")
        old_mods = {k: sys.modules.get(k) for k in keys}
        old_attrs = (services.project_file_service, services.price_base_service)
        sys.modules[keys[0]] = files
        sys.modules[keys[1]] = prices
        services.project_file_service = files
        services.price_base_service = prices

        def restore():
            for k, v in old_mods.items():
                if v is not None:
                    sys.modules[k] = v
            services.project_file_service, services.price_base_service = old_attrs
        return restore

    def _run(project, lines, names=("Rock Eden - essam farag",), doc=None, rows=()):
        files = _Files(names, DOC if doc is None else doc)
        restore = _swap(files, _Prices(rows))
        try:
            return est.estimate_project_cost(project, lines)
        finally:
            restore()

    def المسار_كامل_بيحسب_من_الأبعاد_الحقيقية():
        out = _run("Rock Eden", [{"item": "متر البورسلين 60×120", "basis": "floor"}],
                   rows=[PORCELAIN])
        assert "40.23 م²" in out or "40" in out, out
        assert "20,115" in out or "20115" in out, out

    def اسم_بند_ملتبس_بيترفض_مش_بياخد_الأول():
        """أخطر فرع: مرشحين لنفس البحث -- ممنوع يختار واحد."""
        two = [{"item": "متر البورسلين 60×120", "price": "500"},
               {"item": "متر البورسلين 60×60", "price": "300"}]
        out = _run("Rock Eden", [{"item": "بورسلين", "basis": "floor"}], rows=two)
        assert "مش في قاعدة أسعارك" in out, "اختار سعر من مرشحين ملتبسين: " + out[:200]
        assert "الإجمالي" not in out, out

    def مرشح_واحد_بيتاخد():
        one = [{"item": "متر البورسلين 60×120", "price": "500"}]
        out = _run("Rock Eden", [{"item": "بورسلين 60×120", "basis": "floor"}], rows=one)
        assert "الإجمالي" in out, "مرشح وحيد اترفض: " + out[:200]

    def اسم_مشروع_ملتبس_بيسأل_ومبيقراش_أسعار():
        out = _run("مشروع", [{"item": "x", "basis": "floor"}],
                   names=("مشروع أ", "مشروع ب"), rows=[PORCELAIN])
        assert "أنهي واحد" in out, out
        assert "الإجمالي" not in out and "مقايسة" not in out, out

    def مشروع_مش_موجود_بيقول_الموجود():
        out = _run("حاجة مش موجودة", [], names=("Rock Eden - essam farag",))
        assert "مفيش ملف مشروع" in out, out
        assert "Rock Eden" in out, "مقالش الموجود إيه: " + out

    def ملف_من_غير_فراغات_بيطلب_البلان():
        out = _run("Rock Eden", [{"item": "x", "basis": "floor"}], doc={"facts": {}})
        assert "ابعت البلان" in out or "مفيهوش فراغات" in out, out

    def من_غير_بنود_بيعرض_المساحات_ويسأل():
        out = _run("Rock Eden", [])
        assert "40.23" in out or "40" in out, out
        assert "قوللي البنود" in out, out

    def قراءة_الأسعار_لما_تقع_المقايسة_بترفض():
        """كانت بتكمّل بقاعدة فاضية وتقول لأحمد "سجّل أسعار" وهو مسجّلها.

        الاختبار ده كان بيثبّت السلوك الغلط نفسه (مراجعة 2026-08-08).
        """
        class _Broken(_Prices):
            def _all_docs_supabase_first(self):
                raise RuntimeError("Supabase وقع")
        restore = _swap(_Files(("Rock Eden - essam farag",), DOC), _Broken(()))
        try:
            out = est.estimate_project_cost("Rock Eden",
                                            [{"item": "بورسلين", "basis": "floor"}])
        finally:
            restore()
        assert "مقدرتش أقرا قاعدة أسعارك" in out, out
        assert "مش في قاعدة أسعارك" not in out,             "قال إن البند مش مسجّل والحقيقة إن القراءة نفسها وقعت"
        assert "الإجمالي" not in out, "طلع إجمالي والأسعار مقريتش"
        assert "save_prices_bulk" not in out, "بعت أحمد يسجّل أسعار هو مسجّلها"

    def السقف_على_عدد_البنود():
        many = [{"item": "متر النقاش", "basis": "manual", "quantity": 1}
                for _ in range(est.MAX_LINES + 10)]
        out = _run("Rock Eden", many, rows=[{"item": "متر النقاش", "price": "75"}])
        assert out.count("•") <= est.MAX_LINES, out.count("•")

    def الزيادة_عن_السقف_بتتقال():
        """price_capture بيبلّغ عن الزيادة من أول يوم؛ دي كانت بتقص ساكت."""
        many = [{"item": "متر النقاش", "basis": "manual", "quantity": 1}
                for _ in range(est.MAX_LINES + 7)]
        out = _run("Rock Eden", many, rows=[{"item": "متر النقاش", "price": "75", "unit": "يومية"}])
        assert "7 بند" in out and "زيادة عن حد" in out, out

    def وحدة_السعر_الغلط_بترفض():
        """يومية × مساحة = رقم غلط بمراتب في عرض سعر عميل."""
        daily = [{"item": "يومية نجار", "price": "600", "unit": "يومية"}]
        out = _run("Rock Eden", [{"item": "يومية نجار", "basis": "floor"}], rows=daily)
        assert "مش وحدة مساحة" in out, out
        assert "الإجمالي" not in out, "ضرب يومية في متر مسطح"

    def السعر_صفر_مش_سعر():
        """صفر مقروء غلط من صورة بيصفّر بند في مقايسة."""
        for bad in ("0", "0:0", -5):
            out = _run("Rock Eden", [{"item": "متر النقاش", "basis": "floor"}],
                       rows=[{"item": "متر النقاش", "price": bad, "unit": "متر مسطح"}])
            assert "مش مفهوم كرقم" in out, (bad, out[:160])

    def الأداة_مسجلة_في_الخمس_أماكن():
        from services import claude_service as cs, capabilities_registry as reg
        src = open(cs.__file__, encoding="utf-8").read()
        prompt = src.split('"name": "', 1)[0]
        assert "estimate_project_cost" in {t["name"] for t in cs.TOOLS}, "مش في TOOLS"
        assert 'tool_name == "estimate_project_cost"' in src, "مفيش تنفيذ"
        assert "estimate_project_cost" in reg._TOOL_METADATA, "مش في السجل"
        assert "estimate_project_cost" in prompt, "مش موصوفة في البرومبت"
        assert prompt.count("estimate_project_cost") >= 2, "مفيش قاعدة توجيه"

    def البرومبت_بيمنع_الحساب_باليد():
        from services import claude_service as cs
        src = open(cs.__file__, encoding="utf-8").read()
        prompt = src.split('"name": "', 1)[0]
        assert "ممنوع تحسب بإيدك" in prompt, "مفيش منع صريح للحساب في النص"

    for name, fn in [
        ("الفراغ من غير أبعاد بيتقال", الفراغ_من_غير_أبعاد_بيتقال_مش_بيتحسب_صفر),
        ("المساحة مجموع المحسوب بس", المساحة_مجموع_المحسوب_بس),
        ("ملف فاضي مبيرجعش أصفار", ملف_فاضي_مبيرجعش_أصفار),
        ("الصناديق بتتقرّب لفوق", الصناديق_بتتقرّب_لفوق),
        ("التغطية المجهولة مبتتخمنش", التغطية_المجهولة_مبتتخمنش_من_المقاس),
        ("البند من غير سعر بيترجع بالاسم", البند_من_غير_سعر_بيترجع_بالاسم),
        ("السعر المش مفهوم بيترفض", السعر_المش_مفهوم_بيترفض),
        ("الحوائط من غير كمية مبتتحسبش", الحوائط_من_غير_كمية_مبتتحسبش),
        ("الكمية اليدوية بتشتغل", الكمية_اليدوية_بتشتغل),
        ("المدى بيفضل مدى", المدى_بيفضل_مدى_مبيتوسطش),
        ("الفلوس على المشترى مش المركّب", الفلوس_بتتحسب_على_المشترى_مش_المركّب),
        ("أساس غلط بيترفض", أساس_غلط_بيترفض),
        ("التحذير بيسبق الرقم", التحذير_بيسبق_الرقم),
        ("المصنعية والخامة سطرين", المصنعية_والخامة_سطرين_مش_مجموعين),
        ("المش محسوب بالاسم والسبب", المش_محسوب_بيتعرض_بالاسم_والسبب),
        ("مفيش بنود محسوبة بيتقال", مفيش_بنود_محسوبة_بيتقال_صراحة),
        ("الخطوة الجاية حسب سبب التعذر", الخطوة_الجاية_حسب_سبب_التعذر),
        ("اقتراح الأسعار لما يكون هو السبب", اقتراح_تسجيل_الأسعار_بيظهر_لما_يكون_ده_السبب),
        ("المسار كامل بيحسب من الأبعاد", المسار_كامل_بيحسب_من_الأبعاد_الحقيقية),
        ("اسم بند ملتبس بيترفض", اسم_بند_ملتبس_بيترفض_مش_بياخد_الأول),
        ("مرشح واحد بيتاخد", مرشح_واحد_بيتاخد),
        ("اسم مشروع ملتبس بيسأل", اسم_مشروع_ملتبس_بيسأل_ومبيقراش_أسعار),
        ("مشروع مش موجود بيقول الموجود", مشروع_مش_موجود_بيقول_الموجود),
        ("ملف من غير فراغات بيطلب البلان", ملف_من_غير_فراغات_بيطلب_البلان),
        ("من غير بنود بيعرض المساحات", من_غير_بنود_بيعرض_المساحات_ويسأل),
        ("قراءة الأسعار لما تقع بترفض", قراءة_الأسعار_لما_تقع_المقايسة_بترفض),
        ("السقف على عدد البنود", السقف_على_عدد_البنود),
        ("الزيادة عن السقف بتتقال", الزيادة_عن_السقف_بتتقال),
        ("وحدة السعر الغلط بترفض", وحدة_السعر_الغلط_بترفض),
        ("السعر صفر مش سعر", السعر_صفر_مش_سعر),
        ("الأداة مسجلة في الخمس أماكن", الأداة_مسجلة_في_الخمس_أماكن),
        ("البرومبت بيمنع الحساب باليد", البرومبت_بيمنع_الحساب_باليد),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
