# -*- coding: utf-8 -*-
"""
Tests First -- الـ Mood Board (2c من دمج دور HOPE، ADR 0006).

توجيه أحمد الحاكم (2026-08-04): "المود بورد لازم تبقى مفيدة -- الخامات
والـ color palette، والستايل واضح" -- وثيقة شغل مش صورة حلوة. الفحوصات
هنا حتمية بحتة: بنية الـ prompt والتسجيل في الأدوات. جودة الصور الفعلية
اتأكدت بتجربة حية اعتمدها أحمد قبل الكود ده.
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
    from services.claude_service import TOOLS
    from services.moodboard_service import build_moodboard_prompt

    results = []
    prompt = build_moodboard_prompt(
        "Scandinavian-Bohemian",
        ["warm greige", "soft mint", "muted mango"],
        ["light oak", "rattan", "linen"],
    )

    # ---------- بنية "وثيقة الشغل" (توجيه أحمد) ----------

    def palette_swatches_are_labeled():
        assert "labeled paint color palette" in prompt
        assert "named" in prompt
        assert "warm greige, soft mint, muted mango" in prompt

    def materials_are_the_star():
        assert "dominant content" in prompt
        assert "more prominent than any accessory" in prompt
        assert "light oak, rattan, linen" in prompt

    def style_is_clearly_expressed():
        assert "Scandinavian-Bohemian" in prompt
        assert "clearly expressed" in prompt

    def no_text_except_palette_labels():
        assert "no text anywhere except the palette labels" in prompt

    def accessories_stay_minimal():
        assert "never crowding the materials" in prompt

    def notes_are_woven_in():
        with_notes = build_moodboard_prompt("Modern", "beige", "oak", "ركز على الأرضيات")
        assert "ركز على الأرضيات" in with_notes
        assert build_moodboard_prompt("Modern", "beige", "oak") == build_moodboard_prompt(
            "Modern", "beige", "oak", ""
        )

    def string_and_list_inputs_both_work():
        as_str = build_moodboard_prompt("Modern", "beige, white", "oak, brass")
        assert "beige, white" in as_str and "oak, brass" in as_str

    # ---------- التسجيل ----------

    def tool_is_registered_with_required_params():
        tool = next(t for t in TOOLS if t["name"] == "generate_mood_board")
        required = tool["input_schema"]["required"]
        assert set(required) == {"style", "colors", "materials"}, required
        assert "notes" in tool["input_schema"]["properties"]

    def tool_description_teaches_memory_first():
        tool = next(t for t in TOOLS if t["name"] == "generate_mood_board")
        assert "ذاكرتك" in tool["description"], (
            "الوصف لازم يوجّه الموديل يستخدم بيانات المشروع المحفوظة الأول"
        )

    for name, fn in [
        ("شريط palette مُسمّى", palette_swatches_are_labeled),
        ("الخامات بطلة اللوحة", materials_are_the_star),
        ("الستايل واضح من التكوين", style_is_clearly_expressed),
        ("مفيش كتابة غير أسامي الألوان", no_text_except_palette_labels),
        ("الأكسسوارات مش بتزاحم", accessories_stay_minimal),
        ("التوجيهات الإضافية بتتحاك", notes_are_woven_in),
        ("نص أو قايمة، الاتنين شغالين", string_and_list_inputs_both_work),
        ("الأداة متسجلة بالمطلوب الصح", tool_is_registered_with_required_params),
        ("الوصف بيوجّه للذاكرة الأول", tool_description_teaches_memory_first),
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
