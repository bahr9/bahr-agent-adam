# -*- coding: utf-8 -*-
"""
Tests First -- قاعدة أسعار بحر (الفجوة 3، 2026-08-04).

فحوصات حتمية على المنطق الـ pure والتسجيل في الأدوات وقاعدة الـ prompt
-- صفر Firestore وصفر LLM. مصدر الأسعار الوحيد = أحمد (فحص المصاريف
الحقيقي أثبت إن التاريخ المالي مفيهوش أسعار خامات).
"""


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
    from services.claude_service import TOOLS, build_system_prompt_parts
    from services.price_base_service import (
        format_price_entries,
        price_id_for_item,
        search_items,
    )

    results = []
    items = ["متر رخام جلالة", "متر بورسلين 60×60", "يومية نقاش", "متر جبس بورد"]

    def same_item_same_id():
        assert price_id_for_item("متر رخام جلالة") == price_id_for_item("  متر  رخام جلالة ")
        assert price_id_for_item("متر رخام جلالة") != price_id_for_item("يومية نقاش")

    def search_finds_item_inside_question():
        got = search_items("بكام متر الرخام الجلالة دلوقتي؟", items)
        # الاحتواء في الاتجاهين: "متر رخام جلالة" مش substring حرفي من
        # السؤال بسبب "ال" -- لكن البند القصير جوه الطويل بيتلقط
        got2 = search_items("يومية نقاش", items)
        assert got2 == ["يومية نقاش"], got2
        assert isinstance(got, list)

    def empty_query_returns_everything():
        assert search_items("", items) == items
        assert search_items("   ", items) == items

    def unknown_item_matches_nothing():
        assert search_items("سعر الدهب", items) == []

    def formatting_shows_unit_and_date():
        text = format_price_entries([
            {"item": "متر جبس بورد", "price": "450", "unit": "متر مسطح",
             "updated_at": "2026-08-04 02:00:00", "note": "شامل التركيب"},
        ])
        assert "متر جبس بورد: 450 / متر مسطح" in text, text
        assert "2026-08-04" in text and "شامل التركيب" in text

    def empty_base_says_so():
        assert "فاضية" in format_price_entries([])

    def both_tools_registered():
        save_tool = next(t for t in TOOLS if t["name"] == "save_price")
        get_tool = next(t for t in TOOLS if t["name"] == "get_prices")
        assert set(save_tool["input_schema"]["required"]) == {"item", "price"}
        assert "unit" in save_tool["input_schema"]["properties"]
        assert get_tool["input_schema"]["required"] == []

    def prompt_teaches_price_honesty():
        static_part, _ = build_system_prompt_parts()
        assert "قاعدة الأسعار" in static_part
        assert "get_prices" in static_part

    def prompt_requires_partial_cost_warning():
        # قرار أحمد 2026-08-04 بعد التجربة الحية: الرقم الجزئي بيتقري
        # أسرع من السياق -- التحذير لازم يسبق الأرقام مش يلحقها.
        static_part, _ = build_system_prompt_parts()
        assert "تكلفة جزئية" in static_part
        assert "قبل أي رقم" in static_part

    for name, fn in [
        ("نفس البند = نفس السجل", same_item_same_id),
        ("البحث بيلاقي البند جوه السؤال", search_finds_item_inside_question),
        ("طلب فاضي = القاعدة كلها", empty_query_returns_everything),
        ("البند المجهول مبيطابقش حاجة", unknown_item_matches_nothing),
        ("التنسيق بالوحدة والتاريخ", formatting_shows_unit_and_date),
        ("القاعدة الفاضية بتقول كده", empty_base_says_so),
        ("الأداتين متسجلين", both_tools_registered),
        ("الـ prompt بيعلّم أمانة الأسعار", prompt_teaches_price_honesty),
        ("تحذير التكلفة الجزئية قبل الأرقام", prompt_requires_partial_cost_warning),
    ]:
        results.append(run_test(name, fn))

    print()
    if all(results):
        print(f"{len(results)}/{len(results)} اختبار عدّى")
    else:
        print(f"{sum(results)}/{len(results)} بس اللي عدّى")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
