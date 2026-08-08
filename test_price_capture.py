# -*- coding: utf-8 -*-
"""
اختبارات تسجيل الأسعار بالجملة (2026-08-08).

الخطر هنا مضروب في عدد البنود: نداء واحد بيلمس عشرات الأسعار، والأسعار
دي بتروح لمقايسة عميل. فمعظم الاختبارات على **اللي المفروض ميعديش**:

  - سعر مش مفهوم كرقم -> بيتسجل في Firestore بس والقراءة Supabase-first،
    يعني "اتسجل" كدبة. لازم يترفض قبل الحفظ.
  - سعر موجود بيتغيّر -> لازم يبان في التقرير بالقديم والجديد.
  - بند اتقص للسقف -> لازم يتقال. القص الصامت في مقايسة = رقم ناقص.

صفر شبكة، صفر Firestore -- الحفظ متبدّل بمسجّل في الذاكرة.
"""

import services.price_capture as pcap


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


class _Store:
    """بديل price_base_service: بيقرا من قاموس وبيسجّل الكتابة."""

    def __init__(self, existing=None):
        self.existing = dict(existing or {})
        self.writes = []

    def _all_docs_supabase_first(self):
        return [{"item": k, "price": v} for k, v in self.existing.items()]

    def save_price(self, item, price, unit="", note=""):
        self.writes.append({"item": item, "price": price, "unit": unit, "note": note})
        return "اتسجل في قاعدة الأسعار: " + item + " = " + price


def _swap_store(store):
    """يبدّل price_base_service بالمزيّف ويرجّع الأصلي.

    البديل بيتحط كـ**attribute على حزمة services** مش في sys.modules:
    `from services import price_base_service` بيقرا الحزمة، فتبديل
    sys.modules لوحده مبيوصلش (اتكشف لما الاختبارات فشلت بـ"Firestore
    مش متصل" -- يعني النداء الحقيقي كان بيعدي).
    """
    import services
    import services.price_base_service          # يضمن إن الـattribute موجود قبل التبديل
    original = services.price_base_service
    services.price_base_service = store
    return original


def _restore_store(original):
    import services
    services.price_base_service = original


def _run(items, existing=None):
    """يشغّل save_prices_bulk بتخزين مزيّف -- ويرجّع الحقيقي مكانه."""
    store = _Store(existing)
    original = _swap_store(store)
    try:
        return pcap.save_prices_bulk(items), store
    finally:
        _restore_store(original)


LIST = [
    {"item": "متر البورسلين 60×120", "price": "600:2200", "unit": "متر مسطح"},
    {"item": "مصنعية تركيب بورسلين 60×120", "price": "150", "unit": "متر مسطح"},
    {"item": "متر الرخام جلالة", "price": "1200-1500", "unit": "متر مسطح"},
    {"item": "يومية نجار", "price": "٦٠٠", "unit": "يومية"},
]


def main():
    results = []

    # ---------- التحقق (pure) ----------

    def السعر_المش_مفهوم_بيترفض_مش_بيتحفظ():
        """أهم اختبار: 'حسب الشغل' بيتحفظ في Firestore ويختفي من القراءة."""
        ok, bad = pcap.validate_items([
            {"item": "مصنعية جبس", "price": "حسب الشغل"},
            {"item": "متر نقاش", "price": "75"},
        ])
        assert [e["item"] for e in ok] == ["متر نقاش"], ok
        assert bad and bad[0][0] == "مصنعية جبس", bad
        assert "مش مفهوم" in bad[0][1], bad[0][1]

    def الأشكال_اللي_أحمد_بيكتب_بيها_بتعدي():
        ok, bad = pcap.validate_items(LIST)
        assert len(ok) == 4, [e["item"] for e in ok]
        assert bad == [], bad

    def بند_من_غير_اسم_أو_سعر_بيترفض():
        ok, bad = pcap.validate_items([
            {"item": "", "price": "100"},
            {"item": "متر نقاش", "price": ""},
            {"item": "سليم", "price": "80"},
        ])
        assert [e["item"] for e in ok] == ["سليم"], ok
        assert len(bad) == 2, bad

    def التكرار_بيتقال_مش_بيعدي_ساكت():
        ok, bad = pcap.validate_items([
            {"item": "متر نقاش", "price": "75"},
            {"item": "متر نقاش", "price": "90"},
        ])
        assert len(ok) == 1 and ok[0]["price"] == "90", ok
        assert any("اتكرر" in why for _, why in bad), bad

    def القص_للسقف_بيتقال_مش_بيحصل_بصمت():
        """بند مقصوص بصمت = رقم ناقص في مقايسة محدش واخد باله."""
        many = [{"item": "بند " + str(i), "price": "10"} for i in range(pcap.MAX_ITEMS + 5)]
        ok, bad = pcap.validate_items(many)
        assert len(ok) == pcap.MAX_ITEMS, len(ok)
        assert any("زيادة عن حد" in why for _, why in bad), bad
        assert any("5 بند" in name for name, _ in bad), bad

    # ---------- التصنيف والتقرير ----------

    def التغيير_بيتفصل_عن_الجديد():
        fresh, changed, same = pcap.classify(
            [{"item": "أ", "price": "100"}, {"item": "ب", "price": "50"}, {"item": "ج", "price": "20"}],
            {"ب": "40", "ج": "20"},
        )
        assert [e["item"] for e in fresh] == ["أ"], fresh
        assert [e["item"] for e in changed] == ["ب"], changed
        assert changed[0]["old_price"] == "40", changed[0]
        assert [e["item"] for e in same] == ["ج"], same

    def التقرير_بيوري_القديم_جنب_الجديد():
        """أحمد لازم يمسك الرقم الغلط هنا، مش في مقايسة عميل."""
        report, _ = _run(
            [{"item": "متر البورسلين 60×120", "price": "600:2200"}],
            existing={"متر البورسلين 60×120": "500:2000"},
        )
        assert "اتغيّر" in report, report
        assert "500:2000 ← 600:2200" in report, report

    def التقرير_بيقول_المرفوض_بالاسم_والسبب():
        report, store = _run([
            {"item": "متر نقاش", "price": "75"},
            {"item": "مصنعية جبس", "price": "على حسب"},
        ])
        assert "متسجلش" in report, report
        assert "مصنعية جبس" in report, report
        assert [w["item"] for w in store.writes] == ["متر نقاش"], store.writes

    def المرفوض_عمره_ما_بيوصل_التخزين():
        """الحارس الحقيقي: التحقق قبل الكتابة مش بعدها."""
        _, store = _run([{"item": "س", "price": "مش عارف"}, {"item": "ص", "price": "بعدين"}])
        assert store.writes == [], store.writes

    def ليستة_فاضية_مبتكتبش():
        report, store = _run([])
        assert store.writes == []
        assert "ابعت الأسعار" in report, report

    # ---------- المسار كامل ----------

    def كل_البنود_الصالحة_بتتكتب():
        report, store = _run(LIST)
        assert len(store.writes) == 4, store.writes
        assert "سجّلت 4 بند" in report, report

    def الوحدة_والملاحظة_بيوصلوا():
        _, store = _run([{"item": "متر رخام", "price": "1200", "unit": "متر مسطح", "note": "شامل التركيب"}])
        w = store.writes[0]
        assert w["unit"] == "متر مسطح" and w["note"] == "شامل التركيب", w

    def قراءة_الموجود_لما_تفشل_الحفظ_بيكمّل():
        """القاعدة لو مقريتش، التقرير يقول 'جديد' على الكل -- بس الحفظ ميقفش."""

        class _Broken(_Store):
            def _all_docs_supabase_first(self):
                raise RuntimeError("Supabase وقع")

        store = _Broken()
        original = _swap_store(store)
        try:
            report = pcap.save_prices_bulk([{"item": "متر نقاش", "price": "75"}])
        finally:
            _restore_store(original)
        assert len(store.writes) == 1, store.writes
        assert "سجّلت 1 بند" in report, report

    def المسجّل_فعلاً_بيمسك_الكتابة():
        """حارس ضد اختبار أجوف: لو التبديل مبيوصلش، كل اللي فوق بلا معنى."""
        import services.firebase_service as fb
        real_db = fb.firestore_db
        fb.firestore_db = None            # أي كتابة حقيقية هتفشل وتبان
        try:
            report, store = _run([{"item": "متر نقاش", "price": "75"}])
            assert len(store.writes) == 1, "التبديل مبيوصلش -- الاختبارات جوفاء"
            assert "متسجلش" not in report, report
        finally:
            fb.firestore_db = real_db

    # ---------- التسجيل في الخمس أماكن ----------

    def الأداة_مسجلة_في_الخمس_أماكن():
        from services import claude_service as cs, capabilities_registry as reg
        src = open(cs.__file__, encoding="utf-8").read()
        prompt = src.split('"name": "', 1)[0]

        assert "save_prices_bulk" in {t["name"] for t in cs.TOOLS}, "مش في TOOLS"
        assert 'tool_name == "save_prices_bulk"' in src, "مفيش تنفيذ"
        assert "save_prices_bulk" in reg._TOOL_METADATA, "مش في السجل"
        assert "save_prices_bulk" in prompt, "مش موصوفة في البرومبت"
        assert prompt.count("save_prices_bulk") >= 2, "مفيش قاعدة توجيه (إمتى تستخدمها)"

    def الوصف_بيمنع_التخمين_صراحة():
        from services import claude_service as cs
        desc = next(t for t in cs.TOOLS if t["name"] == "save_prices_bulk")["description"]
        assert "ممنوع تخمّن" in desc, desc

    for name, fn in [
        ("السعر المش مفهوم بيترفض", السعر_المش_مفهوم_بيترفض_مش_بيتحفظ),
        ("أشكال أحمد في الكتابة بتعدي", الأشكال_اللي_أحمد_بيكتب_بيها_بتعدي),
        ("بند من غير اسم أو سعر بيترفض", بند_من_غير_اسم_أو_سعر_بيترفض),
        ("التكرار بيتقال مش بيعدي ساكت", التكرار_بيتقال_مش_بيعدي_ساكت),
        ("القص للسقف بيتقال", القص_للسقف_بيتقال_مش_بيحصل_بصمت),
        ("التغيير بيتفصل عن الجديد", التغيير_بيتفصل_عن_الجديد),
        ("التقرير بيوري القديم جنب الجديد", التقرير_بيوري_القديم_جنب_الجديد),
        ("التقرير بيقول المرفوض بالاسم والسبب", التقرير_بيقول_المرفوض_بالاسم_والسبب),
        ("المرفوض عمره ما بيوصل التخزين", المرفوض_عمره_ما_بيوصل_التخزين),
        ("ليستة فاضية مبتكتبش", ليستة_فاضية_مبتكتبش),
        ("كل البنود الصالحة بتتكتب", كل_البنود_الصالحة_بتتكتب),
        ("الوحدة والملاحظة بيوصلوا", الوحدة_والملاحظة_بيوصلوا),
        ("قراءة الموجود لما تفشل الحفظ بيكمّل", قراءة_الموجود_لما_تفشل_الحفظ_بيكمّل),
        ("المسجّل فعلاً بيمسك الكتابة", المسجّل_فعلاً_بيمسك_الكتابة),
        ("الأداة مسجلة في الخمس أماكن", الأداة_مسجلة_في_الخمس_أماكن),
        ("الوصف بيمنع التخمين صراحة", الوصف_بيمنع_التخمين_صراحة),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
