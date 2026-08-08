# -*- coding: utf-8 -*-
"""
اختبارات المقايسة (2026-08-08).

المقايسة بتخرج من بحر كعرض سعر لعميل. فالخطر مش إنها متطلعش رقم -- الخطر
إنها **تطلع رقم كامل نصه مخترع**: فراغ اتحسب بصفر، سعر اتخمّن، بند اتخطى
بصمت، أو تحذير جه بعد الرقم بدل ما يسبقه.

كل اختبار هنا على واحدة من دول. صفر Firestore وصفر شبكة.
"""

import services.estimate_service as est


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
        """بالصناديق: بتدفع تمن 70 صندوق مش 40 متر."""
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
