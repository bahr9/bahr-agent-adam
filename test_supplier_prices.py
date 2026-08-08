# -*- coding: utf-8 -*-
"""
اختبارات أسعار الموردين (2026-08-08).

الخطر هنا مختلف عن باقي الأدوات: الأداة دي **مبتكتبش حاجة**، فالضرر
مش في قاعدة البيانات -- هو في **إن رقم مورد يتقري كأنه سعر أحمد**
ويدخل مقايسة. فأغلب الاختبارات على العرض والتحذير مش على الحفظ.

وأهم اختبار فيهم: `الوحدة_مبتتفترضش`. بورسلين بالمتر وخلاط بالقطعة،
والوحدة بتيجي من المورد. لو غابت، لازم يتقال -- مش يتحط "متر" افتراضًا.

صفر شبكة: كل النداءات متبدّلة برد ثابت.
"""

import services.supplier_prices as sp


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


PRODUCT_JSON = {
    "product": {
        "id": "1010014903",
        "productName": "Floor Porcelain Glow 60x120 cm IVORY marble",
        "available": True,
        "price": {
            "sales": {"value": 613.8, "currency": "EGP"},
            "list": {"value": 825, "currency": "EGP"},
        },
        "images": {"large": [{"url": "https://img.example/glow.jpg"}]},
        "attributes": [{"attributes": [
            {"label": "Brand", "value": ["Celeopatra"]},
            {"label": "Size", "value": ["60x120 CM"]},
            {"label": "Grade", "value": ["First"]},
            {"label": "Unit Of Measure", "value": ["Meter"]},
            {"label": "Production Country", "value": ["Egypt"]},
        ]}],
    }
}

SEARCH_HTML = (
    '<a href="...Product-ShowQuickView?pid=1010014903">x</a>'
    '<a href="...Product-ShowQuickView?pid=1010014904">y</a>'
    '<a href="...Product-ShowQuickView?pid=1010014903">dup</a>'
)


class _Resp:
    def __init__(self, text="", payload=None, status=200):
        self.text = text
        self._payload = payload
        self.status_code = status

    def json(self):
        if self._payload is None:
            raise ValueError("مش JSON")
        return self._payload


def _fake_net(search=None, product=None, boom=None):
    """يبدّل _get برد ثابت. بيرجّع دالة الاستعادة."""
    original = sp._get

    def fake(url, params):
        if boom:
            raise boom
        if url == sp._SEARCH_URL:
            return search if search is not None else _Resp(text=SEARCH_HTML)
        return product if product is not None else _Resp(payload=PRODUCT_JSON)

    sp._get = fake
    return lambda: setattr(sp, "_get", original)


def main():
    results = []

    # ---------- استخراج الأصناف ----------

    def البحث_بيرجع_أصناف_من_غير_تكرار():
        restore = _fake_net()
        try:
            ids = sp.search_product_ids("porcelain 60x120", limit=5)
        finally:
            restore()
        assert ids == ["1010014903", "1010014904"], ids

    def السقف_بيتحترم():
        restore = _fake_net()
        try:
            assert len(sp.search_product_ids("x", limit=1)) == 1
            # طلب أكبر من MAX_LIMIT مبيكسرش -- بيتقص للحد
            assert len(sp.search_product_ids("x", limit=99)) <= sp.MAX_LIMIT
        finally:
            restore()

    def بحث_فاضي_مبيضربش_الشبكة():
        called = {"n": 0}
        original = sp._get
        sp._get = lambda url, params: called.__setitem__("n", called["n"] + 1)
        try:
            assert sp.search_product_ids("") == []
        finally:
            sp._get = original
        assert called["n"] == 0, "ضرب الشبكة على بحث فاضي"

    def الموقع_لما_يقع_بيتقال_مش_بيتبلع():
        restore = _fake_net(boom=RuntimeError("connection reset"))
        try:
            try:
                sp.search_product_ids("porcelain")
                raise AssertionError("المفروض يرمي SupplierError")
            except sp.SupplierError as e:
                assert "مقدرتش أوصل" in str(e), str(e)
        finally:
            restore()

    def HTTP_مش_200_بيترمي():
        restore = _fake_net(search=_Resp(text="", status=503))
        try:
            try:
                sp.search_product_ids("porcelain")
                raise AssertionError("المفروض يرمي")
            except sp.SupplierError as e:
                assert "503" in str(e), str(e)
        finally:
            restore()

    # ---------- قراءة الصنف ----------

    def الصنف_بيترجع_بكل_حقوله():
        restore = _fake_net()
        try:
            item = sp.fetch_product("1010014903")
        finally:
            restore()
        assert item["name"].startswith("Floor Porcelain Glow"), item
        assert item["price"] == 613.8 and item["list_price"] == 825, item
        assert item["unit"] == "Meter", item
        assert item["brand"] == "Celeopatra" and item["grade"] == "First", item
        assert item["available"] is True
        assert item["image"] == "https://img.example/glow.jpg", item

    def السعر_من_غير_خصم_مفيهوش_سعر_قديم_وهمي():
        """لو مفيش خصم، مايتعرضش 'قبل الخصم' بنفس الرقم."""
        payload = {"product": dict(PRODUCT_JSON["product"],
                                   price={"sales": {"value": 500, "currency": "EGP"},
                                          "list": {"value": 500, "currency": "EGP"}})}
        restore = _fake_net(product=_Resp(payload=payload))
        try:
            item = sp.fetch_product("1")
        finally:
            restore()
        assert item["price"] == 500 and item["list_price"] is None, item

    def صنف_بايظ_بيرجع_None_مش_بيوقّع_الباقي():
        restore = _fake_net(product=_Resp(payload={"product": {}}))
        try:
            assert sp.fetch_product("1") is None
        finally:
            restore()

    # ---------- العرض ----------

    def الوحدة_مبتتفترضش():
        """بورسلين بالمتر وخلاط بالقطعة -- غياب الوحدة لازم يتقال."""
        no_unit = {"name": "Mixer X", "brand": None, "size": None, "grade": None,
                   "country": None, "unit": None, "price": 3500, "list_price": None,
                   "currency": "EGP", "available": True, "image": None}
        out = sp.format_comparison("mixer", [no_unit], [], "2026-08-08")
        assert "الوحدة مش مذكورة" in out, out
        assert "/ متر" not in out, "افترض إنه سعر متر: " + out

    def سعر_أحمد_بيتعرض_الأول_وبيتقال_إنه_المرجع():
        mine = [{"item": "متر البورسلين 60×120", "price": "500-2000",
                 "unit": "متر مسطح", "updated_at": "2026-08-06 10:00"}]
        out = sp.format_comparison("porcelain", [], mine, "2026-08-08")
        assert out.index("سعرك المسجّل") < out.index("ماحجوب"), "سعر المورد اتعرض الأول"
        assert "هو المرجع في أي مقايسة" in out
        assert "2026-08-06" in out, "تاريخ آخر تحديث مش ظاهر"

    def التحذير_موجود_دايمًا():
        """أخطر حاجة: رقم المورد يتقري كسعر أحمد."""
        item = {"name": "X", "brand": None, "size": None, "grade": None, "country": None,
                "unit": "Meter", "price": 600, "list_price": None, "currency": "EGP",
                "available": True, "image": None}
        for products, mine in [([item], []), ([], []), ([item], [{"item": "أ", "price": "5"}])]:
            out = sp.format_comparison("q", products, mine, "2026-08-08")
            assert "أسعار بيع للجمهور" in out, out
            assert "سعر أحمد المسجّل" in out, out

    def مفيش_سعر_مسجّل_بيتقال_صراحة():
        out = sp.format_comparison("q", [], [], "2026-08-08")
        assert "مفيش سعر مسجّل عندك" in out, out
        assert "مرجع سوق مش سعرك" in out, out

    def تاريخ_الجلب_بيتعرض():
        """رقم من غير تاريخ بيبقى صالح للأبد في دماغ اللي بيقراه."""
        out = sp.format_comparison("q", [], [], "2026-08-08")
        assert "2026-08-08" in out, out

    def عدم_التوفر_بيبان():
        item = {"name": "X", "brand": None, "size": None, "grade": None, "country": None,
                "unit": "Meter", "price": 600, "list_price": None, "currency": "EGP",
                "available": False, "image": None}
        out = sp.format_comparison("q", [item], [], "2026-08-08")
        assert "مش متوفر" in out, out

    # ---------- المسار كامل ----------

    def البند_العربي_بيلاقي_سعر_أحمد():
        """العيب اللي اتكشف في أول تشغيلة: البحث إنجليزي والبنود عربي."""
        seen = {}
        original = sp._my_prices
        sp._my_prices = lambda q: (seen.setdefault("queries", []).append(q),
                                   [{"item": "متر البورسلين 60×120", "price": "500-2000",
                                     "unit": "متر مسطح", "updated_at": "2026-08-06"}]
                                   if q == "متر البورسلين 60×120" else [])[1]
        restore = _fake_net()
        try:
            out = sp.check_supplier_price("porcelain 60x120", limit=1,
                                          my_item="متر البورسلين 60×120")
        finally:
            restore()
            sp._my_prices = original
        assert "500-2000" in out, out
        assert "متر البورسلين 60×120" in seen["queries"], seen

    def الأداة_مسجلة_في_الخمس_أماكن():
        from services import claude_service as cs, capabilities_registry as reg
        src = open(cs.__file__, encoding="utf-8").read()
        prompt = src.split('"name": "', 1)[0]
        assert "check_supplier_price" in {t["name"] for t in cs.TOOLS}, "مش في TOOLS"
        assert 'tool_name == "check_supplier_price"' in src, "مفيش تنفيذ"
        assert "check_supplier_price" in reg._TOOL_METADATA, "مش في السجل"
        assert "check_supplier_price" in prompt, "مش موصوفة في البرومبت"
        assert prompt.count("check_supplier_price") >= 2, "مفيش قاعدة توجيه"

    def الوصف_بيقول_إنجليزي_وإنه_مش_سعر_أحمد():
        from services import claude_service as cs
        desc = next(t for t in cs.TOOLS if t["name"] == "check_supplier_price")["description"]
        assert "إنجليزي" in desc, desc
        assert "مش سعر شرا أحمد" in desc, desc

    for name, fn in [
        ("البحث بيرجع أصناف من غير تكرار", البحث_بيرجع_أصناف_من_غير_تكرار),
        ("السقف بيتحترم", السقف_بيتحترم),
        ("بحث فاضي مبيضربش الشبكة", بحث_فاضي_مبيضربش_الشبكة),
        ("الموقع لما يقع بيتقال", الموقع_لما_يقع_بيتقال_مش_بيتبلع),
        ("HTTP مش 200 بيترمي", HTTP_مش_200_بيترمي),
        ("الصنف بيترجع بكل حقوله", الصنف_بيترجع_بكل_حقوله),
        ("من غير خصم مفيش سعر قديم وهمي", السعر_من_غير_خصم_مفيهوش_سعر_قديم_وهمي),
        ("صنف بايظ مبيوقّعش الباقي", صنف_بايظ_بيرجع_None_مش_بيوقّع_الباقي),
        ("الوحدة مبتتفترضش", الوحدة_مبتتفترضش),
        ("سعر أحمد بيتعرض الأول", سعر_أحمد_بيتعرض_الأول_وبيتقال_إنه_المرجع),
        ("التحذير موجود دايمًا", التحذير_موجود_دايمًا),
        ("مفيش سعر مسجّل بيتقال صراحة", مفيش_سعر_مسجّل_بيتقال_صراحة),
        ("تاريخ الجلب بيتعرض", تاريخ_الجلب_بيتعرض),
        ("عدم التوفر بيبان", عدم_التوفر_بيبان),
        ("البند العربي بيلاقي سعر أحمد", البند_العربي_بيلاقي_سعر_أحمد),
        ("الأداة مسجلة في الخمس أماكن", الأداة_مسجلة_في_الخمس_أماكن),
        ("الوصف بيقول إنجليزي ومش سعر أحمد", الوصف_بيقول_إنجليزي_وإنه_مش_سعر_أحمد),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
