# -*- coding: utf-8 -*-
"""
Tests First -- ملف المشروع المستمر (الفجوة 1، قرار أحمد 2026-08-04).

الفحوصات حتمية بحتة على المنطق الـ pure (حل الاسم، الـ id الحتمي،
التنسيق) والتسجيل في الأدوات وقواعد الـ prompt -- صفر Firestore وصفر
LLM. الاسترجاع الحي الفعلي بيتأكد بتجربة أحمد على مشروع Rock Eden
الحقيقي بعد النشر.
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
    from services.project_file_service import (
        CATEGORIES,
        computed_area,
        format_project_file,
        project_id_for_name,
        resolve_project_name,
    )

    results = []
    existing = ["Rock Eden - essam farag", "شقة جاردينيا", "فيلا التجمع"]

    # ---------- الـ id الحتمي (درس HOPE: نفس الاسم = نفس الملف دايمًا) ----------

    def same_name_same_id_across_sessions():
        assert project_id_for_name("Rock Eden") == project_id_for_name("rock eden")
        assert project_id_for_name("  Rock   Eden ") == project_id_for_name("Rock Eden")
        assert project_id_for_name("Rock Eden") != project_id_for_name("شقة جاردينيا")

    # ---------- حل الاسم ----------

    def exact_match_wins():
        status, matches = resolve_project_name("rock eden - ESSAM farag", existing)
        assert status == "exact" and matches == ["Rock Eden - essam farag"]

    def partial_match_resolves_uniquely():
        status, matches = resolve_project_name("essam", existing)
        assert status == "resolved" and matches == ["Rock Eden - essam farag"], (status, matches)

    def query_containing_the_name_also_resolves():
        status, matches = resolve_project_name("مشروع شقة جاردينيا بتاع الأسبوع اللي فات", existing)
        assert status == "resolved" and matches == ["شقة جاردينيا"], (status, matches)

    def ambiguity_is_asked_not_guessed():
        names = ["شقة مدينة نصر", "فيلا مدينة نصر"]
        status, matches = resolve_project_name("مدينة نصر", names)
        assert status == "ambiguous" and len(matches) == 2, (status, matches)

    def name_fragment_inside_long_sentence_resolves():
        # الفشل الوحيد في اختبار الحجم (30 مشروع): مقطع الاسم المركب
        # جوه جملة طبيعية -- "بالظبط الطريقة اللي بكلمك بيها عادي"
        status, matches = resolve_project_name(
            "مشروع essam farag اللي كلمتك عنه", existing
        )
        assert (status, matches) == ("resolved", ["Rock Eden - essam farag"]), (status, matches)

    def fragment_tie_between_two_clients_asks():
        names = ["شقة جاردينيا - محمد سعيد", "فيلا العبور - محمد سعيد تاني"]
        status, matches = resolve_project_name(
            "عايز أراجع شغل محمد سعيد", names
        )
        assert status == "ambiguous" and len(matches) == 2, (status, matches)

    def unknown_name_returns_none():
        status, matches = resolve_project_name("مشروع مجهول تمامًا", existing)
        assert status == "none" and matches == []

    def empty_query_returns_none():
        assert resolve_project_name("   ", existing) == ("none", [])

    # ---------- الحساب المشتق من الأبعاد المكتوبة (الفجوة 2 -- الشريحة الرخيصة) ----------

    def area_computed_from_written_dims_only():
        # ضرب حتمي في بايثون -- مش حساب ذهني من الموديل
        assert computed_area("7.70×5.99 م") == 46.12
        assert computed_area("5.00x3.78") == 18.9
        assert computed_area("3.70 × 3.85 متر") == 14.25

    def arabic_indic_digits_compute_too():
        assert computed_area("٣.٧٠×٣.٨٥") == 14.25

    def no_written_dims_means_no_area():
        # الفخ المتفق نتجنبه: فراغ من غير رقم مكتوب = غير محسوب، مش تخمين
        assert computed_area("واسع وبيطل على الحديقة") is None
        assert computed_area("مش واضح في البلان") is None
        assert computed_area("") is None
        # رقم واحد مش أبعاد -- متضربش في حاجة متخيلة
        assert computed_area("46 م²") is None

    # ---------- التنسيق ----------

    def formatting_shows_categories_and_values():
        doc = {
            "display_name": "Rock Eden - essam farag",
            "facts": {
                "فراغات": {"الريسبشن": {"value": "7.70×5.99 م"}},
                "قرارات": {"الستايل": {"value": "Scandinavian-Bohemian"}},
                "ميزانية": {},
            },
        }
        text = format_project_file(doc)
        assert "Rock Eden - essam farag" in text
        assert "فراغات" in text and "الريسبشن: 7.70×5.99 م" in text
        assert "قرارات" in text and "Scandinavian-Bohemian" in text
        assert "ميزانية" not in text, "الفئة الفاضية متتعرضش"
        # البُعد المكتوب بيظهر معاه المساحة المحسوبة حتميًا بمصدرها
        assert "46.12 م²" in text and "محسوبة من الأبعاد المكتوبة" in text, text

    def empty_file_says_so():
        assert "لسه مفيهوش" in format_project_file({"display_name": "جديد", "facts": {}})

    # ---------- التسجيل والـ prompt ----------

    def both_tools_registered_with_structured_categories():
        save_tool = next(t for t in TOOLS if t["name"] == "save_project_fact")
        get_tool = next(t for t in TOOLS if t["name"] == "get_project_file")
        enum = save_tool["input_schema"]["properties"]["category"]["enum"]
        assert tuple(enum) == CATEGORIES, enum
        assert set(save_tool["input_schema"]["required"]) == {
            "project_name", "category", "key", "value"
        }
        assert get_tool["input_schema"]["required"] == ["project_name"]

    def prompt_teaches_auto_recall():
        static_part, _ = build_system_prompt_parts()
        assert "قاعدة ملفات المشاريع" in static_part
        assert "get_project_file فورًا" in static_part

    def prompt_forbids_visual_estimation():
        # قرار أحمد: رقم غلط أسوأ من رقم ناقص -- الفراغ من غير رقم
        # مكتوب يتعلّم "غير محسوب" ولا يتقدّرش من شكل الرسم أبدًا
        static_part, _ = build_system_prompt_parts()
        assert "غير محسوب" in static_part
        assert "المحسوبة في الملف" in static_part

    for name, fn in [
        ("نفس الاسم = نفس الملف عبر الجلسات", same_name_same_id_across_sessions),
        ("التطابق الكامل بيكسب", exact_match_wins),
        ("التطابق الجزئي الوحيد بيتحل", partial_match_resolves_uniquely),
        ("الاسم جوه جملة أطول بيتحل", query_containing_the_name_also_resolves),
        ("الغموض بيتسأل عنه مش بيتخمن", ambiguity_is_asked_not_guessed),
        ("مقطع الاسم جوه جملة طويلة بيتحل", name_fragment_inside_long_sentence_resolves),
        ("تعادل المقاطع بيسأل مش بيخمن", fragment_tie_between_two_clients_asks),
        ("الاسم المجهول بيرجع none", unknown_name_returns_none),
        ("الطلب الفاضي none", empty_query_returns_none),
        ("المساحة بتتحسب من الأبعاد المكتوبة بس", area_computed_from_written_dims_only),
        ("الأرقام الهندية بتتحسب برضه", arabic_indic_digits_compute_too),
        ("مفيش رقم مكتوب = مفيش مساحة", no_written_dims_means_no_area),
        ("التنسيق بالفئات والقيم", formatting_shows_categories_and_values),
        ("الملف الفاضي بيقول كده", empty_file_says_so),
        ("الأداتين متسجلين بفئات منظمة", both_tools_registered_with_structured_categories),
        ("الـ prompt بيعلّم الاسترجاع التلقائي", prompt_teaches_auto_recall),
        ("الـ prompt بيمنع التقدير البصري", prompt_forbids_visual_estimation),
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
