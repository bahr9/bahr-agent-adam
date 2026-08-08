# -*- coding: utf-8 -*-
"""
حارس التسجيل الكامل لأي أداة: **خمس أماكن، مش واحد.**

الحادثة اللي القاعدة دي اتحطت بعدها (كوميت 0895eb3): "آدم ناقض نفسه عن
أكشن شغال -- ليستة اتحدّثت وتوأمها لأ". أداة اتسجلت في مكان ونُسيت في
التاني، فآدم قال لأحمد معلومة غلط عن نفسه.

الأماكن الخمسة:
  1. `TOOLS`                        -- الـ schema اللي بيتبعت للموديل
  2. `_execute_tool`                -- التنفيذ الفعلي
  3. `capabilities_registry`        -- التصنيف (ده الوحيد اللي check_drift بيمسكه)
  4. قايمة الأدوات في البرومبت      -- وصف الأداة اللي الموديل بيقراه
  5. قواعد التوجيه في البرومبت      -- إمتى يستخدمها

`check_drift` بيمسك رقم 3 بس. الأربعة التانية كانت بتتنسى بصمت -- الملف ده
بيقفل الباب ده.

فحص سورس -- صفر شبكة، صفر Firestore، صفر موديل.
"""

import re


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
    from services import claude_service, capabilities_registry

    SRC = open(claude_service.__file__, encoding="utf-8").read()
    TOOL_NAMES = {t["name"] for t in claude_service.TOOLS}

    # الجزء اللي فيه البرومبت (وصف الأدوات + قواعد التوجيه) قبل تعريفات
    # الـ TOOLS نفسها -- بنقص عنده عشان مانخلطش وصف البرومبت بالـ schema.
    prompt_region = SRC.split('"name": "', 1)[0]

    def every_tool_in_the_schema_is_dispatched():
        """أداة في الـ schema من غير تنفيذ = الموديل بينداها وبيجيله خطأ."""
        missing = [n for n in TOOL_NAMES
                   if f'tool_name == "{n}"' not in SRC and f"tool_name == '{n}'" not in SRC]
        # أدوات السيرفر (زي web_search) بتتنفذ عند Anthropic مش عندنا
        server_side = {"web_search"}
        missing = [n for n in missing if n not in server_side]
        assert not missing, f"أدوات في TOOLS من غير تنفيذ في _execute_tool: {missing}"

    def every_dispatched_tool_is_in_the_schema():
        """تنفيذ من غير schema = كود ميت الموديل عمره ما هيوصله."""
        dispatched = set(re.findall(r'tool_name\s*==\s*"([a-z_0-9]+)"', SRC))
        orphan = sorted(dispatched - TOOL_NAMES)
        assert not orphan, f"تنفيذ لأدوات مش في TOOLS: {orphan}"

    def every_tool_is_classified_in_the_registry():
        """نفس فحص check_drift، بس بيفشل هنا كمان عشان يبان في السويت."""
        drift = capabilities_registry.check_drift()
        assert drift["missing_from_metadata"] == [], (
            f"أدوات من غير تصنيف: {drift['missing_from_metadata']}"
        )
        assert drift["stale_in_metadata"] == [], (
            f"تصنيف لأدوات مش موجودة: {drift['stale_in_metadata']}"
        )

    def the_self_state_tools_are_described_in_the_prompt():
        """الأدوات اللي آدم بيختار يناديها بنفسه لازم تكون موصوفة له.

        مش كل أداة محتاجة وصف في البرومبت (فيه أدوات بتتنادى في سياق ضيق)،
        بس مجموعة الحالة/المتابعة دي بالذات الموديل بيقرر يستخدمها من
        الوصف -- فغيابها معناه إنها موجودة وعمرها ما هتتنادى.
        """
        must_be_described = {
            "get_adam_self_state",
            "get_tools_health_status",
            "get_open_threads",
        }
        missing = sorted(n for n in must_be_described if n not in prompt_region)
        assert not missing, (
            f"أدوات حالة موجودة في TOOLS ومفيهاش وصف في البرومبت: {missing}. "
            "الموديل مش هيعرف إمتى يستخدمها."
        )

    def the_new_thread_tool_has_a_routing_rule():
        """الوصف بيقول 'بتعمل إيه'؛ قاعدة التوجيه بتقول 'إمتى'."""
        assert "get_open_threads" in prompt_region, "الأداة مش مذكورة في البرومبت خالص"
        # لازم تظهر مرتين على الأقل: مرة في قايمة الأدوات ومرة في التوجيه
        assert prompt_region.count("get_open_threads") >= 2, (
            "get_open_threads مذكورة مرة واحدة بس -- ناقصها قاعدة توجيه (إمتى تستخدمها)"
        )

    def the_thread_tool_warns_against_inventing_durations():
        """قاعدة الأمانة لازم توصل للموديل، مش تفضل في الكود بس."""
        schema = next(t for t in claude_service.TOOLS if t["name"] == "get_open_threads")
        desc = schema["description"]
        assert "مش معروفة" in desc or "ممنوع تخترع" in desc, (
            f"وصف الأداة مفيهوش تحذير من اختراع المدد: {desc}"
        )

    results = [
        run_test("كل أداة في الـ schema ليها تنفيذ", every_tool_in_the_schema_is_dispatched),
        run_test("كل تنفيذ ليه أداة في الـ schema", every_dispatched_tool_is_in_the_schema),
        run_test("كل أداة مصنّفة في السجل", every_tool_is_classified_in_the_registry),
        run_test("أدوات الحالة موصوفة في البرومبت", the_self_state_tools_are_described_in_the_prompt),
        run_test("أداة الخيط ليها قاعدة توجيه", the_new_thread_tool_has_a_routing_rule),
        run_test("وصف الأداة بيحذّر من اختراع المدد", the_thread_tool_warns_against_inventing_durations),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
