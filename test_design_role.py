# -*- coding: utf-8 -*-
"""
Tests First -- الدور الاستشاري التصميمي (دمج دور HOPE في آدم، ADR 0006
في مستودع Archiducer، بقرار أحمد 2026-08-03).

الفحص هنا حتمي بحت: بنية الـ system prompt بعد إضافة الدور --
(1) كتلة الدور موجودة وبالمحتوى الجوهري (خطة محددة مش مبادئ،
    البناء على الحقائق، حرية الرأي التصميمي مقابل التحفظ في أرقام
    الأكواد، الحفظ عبر save_memory_note)،
(2) قواعد الأمانة الأصلية لسه موجودة بعد الإضافة زي ما هي،
(3) الفصل static/dynamic لسه سليم.

مفيش LLM هنا خالص -- جودة الردود الفعلية بتتقاس بمحادثة حية مع أحمد
(زي كل مراحل الدمج)، مش هنا.
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
    from services.claude_service import build_system_prompt_parts

    static_part, dynamic_part = build_system_prompt_parts()
    results = []

    def role_block_present():
        assert "دورك التاني" in static_part, "كتلة الدور مش موجودة"
        assert "استشاري التصميم الداخلي" in static_part

    def role_demands_concrete_plans():
        assert "خطة أو توزيع أو اقتراح محدد" in static_part
        assert "مش مبادئ عامة" in static_part

    def role_builds_on_facts():
        assert "ابني على الحقائق" in static_part

    def role_separates_judgment_from_codes():
        assert "كود بناء" in static_part
        assert "محتاج أتأكد من الاشتراطات" in static_part

    def role_uses_existing_memory_tool():
        assert "حقائق مشاريع العملاء" in static_part
        assert static_part.count("save_memory_note") >= 2, (
            "الدور لازم يوجّه لأداة الذاكرة الموجودة أصلًا"
        )

    def reasoned_objection_rule_present():
        # قرار أحمد 2026-08-04 (نقطة 5): اعتراض مُسبَّب في الحكم
        # المهني -- يعترض بقوة وبأسباب، يصرّح بحدود معرفته، والقرار
        # النهائي لأحمد. وخطوط الأمانة الصلبة بتفضل رفض كامل.
        assert "الاعتراض المُسبَّب" in static_part
        assert "القرار النهائي قرار أحمد دايمًا" in static_part
        assert "مش شايف الموقع فعليًا" in static_part
        assert "بتفضل رفض كامل زي ما هي مهما أصر أحمد" in static_part

    def honesty_rules_untouched():
        assert "قواعد الأمانة (مهمة جداً):" in static_part
        assert "فرّق دايماً بين \"أنا متأكد\" و\"أنا بفتكر\" و\"مش عارف\"." in static_part
        assert "ممنوع تمامًا تقول إنك \"جرّبت\"" in static_part

    def role_sits_before_honesty_rules():
        assert static_part.index("دورك التاني") < static_part.index(
            "قواعد الأمانة (مهمة جداً):"
        )

    def static_dynamic_split_intact():
        assert "الوقت الحالي بالظبط" in dynamic_part
        assert "الوقت الحالي بالظبط" not in static_part

    for name, fn in [
        ("كتلة الدور موجودة", role_block_present),
        ("الدور بيطلب خطط محددة", role_demands_concrete_plans),
        ("الدور بيبني على الحقائق", role_builds_on_facts),
        ("فصل الرأي الحر عن أرقام الأكواد", role_separates_judgment_from_codes),
        ("الحفظ عبر أداة الذاكرة الموجودة", role_uses_existing_memory_tool),
        ("الاعتراض المُسبَّب موجود ومفصول عن خطوط الأمانة", reasoned_objection_rule_present),
        ("قواعد الأمانة زي ما هي", honesty_rules_untouched),
        ("الدور قبل قواعد الأمانة", role_sits_before_honesty_rules),
        ("فصل static/dynamic سليم", static_dynamic_split_intact),
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
