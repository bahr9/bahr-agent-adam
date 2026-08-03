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

    def unknown_name_returns_none():
        status, matches = resolve_project_name("مشروع مجهول تمامًا", existing)
        assert status == "none" and matches == []

    def empty_query_returns_none():
        assert resolve_project_name("   ", existing) == ("none", [])

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

    for name, fn in [
        ("نفس الاسم = نفس الملف عبر الجلسات", same_name_same_id_across_sessions),
        ("التطابق الكامل بيكسب", exact_match_wins),
        ("التطابق الجزئي الوحيد بيتحل", partial_match_resolves_uniquely),
        ("الاسم جوه جملة أطول بيتحل", query_containing_the_name_also_resolves),
        ("الغموض بيتسأل عنه مش بيتخمن", ambiguity_is_asked_not_guessed),
        ("الاسم المجهول بيرجع none", unknown_name_returns_none),
        ("الطلب الفاضي none", empty_query_returns_none),
        ("التنسيق بالفئات والقيم", formatting_shows_categories_and_values),
        ("الملف الفاضي بيقول كده", empty_file_says_so),
        ("الأداتين متسجلين بفئات منظمة", both_tools_registered_with_structured_categories),
        ("الـ prompt بيعلّم الاسترجاع التلقائي", prompt_teaches_auto_recall),
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
