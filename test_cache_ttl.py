# -*- coding: utf-8 -*-
"""
مدة صلاحية الكاش: مصدر واحد، ومقاسة مش مقدّرة.

الخلفية (2026-08-08): قياس من جدول api_usage في الإنتاج قال إن **كتابة
الكاش 74% من الفاتورة كلها**. وقياس تاني من أوقات النداءات قال إن 92% من
النداءات المتتالية بتحصل خلال 5 دقايق، و5% بس في النافذة اللي الساعة
بتفيد فيها (5-60 دقيقة).

يعني كنا بندفع علاوة الساعة (2× بدل 1.25×) على **كل** كتابة عشان نخدم 5%
منها. التغيير لـ 5 دقايق متوقع يوفر ~20% من الإجمالي.

الملف ده بيحرس حاجتين:
  ١. المدة مصدرها مكان واحد -- تلات أماكن كانت بتكتب الـ dict بإيدها،
     وأي واحد فيهم يتنسى في تغيير جاي = كاش بمدد مختلفة من غير ما حد ياخد باله.
  ٢. شكل العلامة يفضل مطابق لما الـ API بيقبله.

**مش** بيحرس القيمة نفسها (5m مقابل 1h) -- دي قرار اقتصادي لأحمد يتغير
بسطر واحد لما البيانات تتغير.

صفر شبكة، صفر Firestore.
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
    from services import claude_service as cs

    SRC_PATH = cs.__file__

    def there_is_exactly_one_ttl_in_the_source():
        """أي dict كاش مكتوب بالإيد = مدة تانية ممكن تتنسى في أي تغيير جاي."""
        src = open(SRC_PATH, encoding="utf-8").read()
        # بيمسك الشكلين: نص مكتوب بالإيد ("1h") والثابت المشترك (CACHE_TTL).
        # لو مسكنا النص بس، رجوع أي حد لـ dict بالإيد هيعدي من غير ما يبان.
        hits = re.findall(r'"ttl"\s*:\s*(?:"[^"]+"|CACHE_TTL)', src)
        assert len(hits) == 1, (
            f"لقيت {len(hits)} مكان بيحدد ttl بدل واحد: {hits}. "
            "كل مكان بيكاش لازم ينادي _cache_marker()."
        )
        assert "CACHE_TTL" in hits[0], (
            f"المكان الوحيد بيكتب المدة نصًا بدل الثابت: {hits[0]}"
        )

    def every_cache_site_uses_the_shared_marker():
        src = open(SRC_PATH, encoding="utf-8").read()
        manual = re.findall(r'"cache_control"\s*:\s*\{[^}]*"type"\s*:\s*"ephemeral"', src)
        assert not manual, (
            f"فيه {len(manual)} علامة cache_control مكتوبة بالإيد -- استخدم _cache_marker(): {manual}"
        )

    def the_marker_has_the_shape_the_api_accepts():
        m = cs._cache_marker()
        assert m["type"] == "ephemeral", m
        assert m["ttl"] == cs.CACHE_TTL, m
        assert set(m) == {"type", "ttl"}, f"حقول زيادة هتترفض من الـ API: {m}"

    def the_ttl_is_a_value_the_api_knows():
        """الـ API بيقبل 5m أو 1h بس. أي حاجة تانية = 400 وقت التشغيل."""
        assert cs.CACHE_TTL in ("5m", "1h"), (
            f"مدة مش مدعومة: {cs.CACHE_TTL!r} -- الـ API بيقبل '5m' أو '1h' بس"
        )

    def marking_a_string_message_wraps_it_correctly():
        msg = {"role": "user", "content": "نص عادي"}
        cs._mark_message_cached(msg)
        assert isinstance(msg["content"], list), msg
        block = msg["content"][0]
        assert block["text"] == "نص عادي", block
        assert block["cache_control"] == cs._cache_marker(), block

    def marking_a_block_list_marks_only_the_last_block():
        msg = {"role": "user", "content": [
            {"type": "text", "text": "أول"},
            {"type": "text", "text": "تاني"},
        ]}
        cs._mark_message_cached(msg)
        assert "cache_control" not in msg["content"][0], "علامة على بلوك مش الأخير"
        assert msg["content"][-1]["cache_control"] == cs._cache_marker()

    def non_dict_messages_are_left_alone():
        """بلوكات الـ SDK مش dict -- لمسها بيكسر الرد."""
        class SdkBlock:
            pass
        obj = SdkBlock()
        cs._mark_message_cached(obj)          # لازم يعدي من غير استثناء
        assert not hasattr(obj, "content")

    def the_one_hour_beta_header_is_still_sent():
        """الرجوع لساعة لازم يفضل سطر واحد -- الهيدر مايتشالش مع تغيير المدة."""
        src = open(SRC_PATH, encoding="utf-8").read()
        assert "extended-cache-ttl-2025-04-11" in src, (
            "هيدر مدة الساعة اتشال -- الرجوع لـ 1h مش هيشتغل بتغيير الثابت لوحده"
        )

    results = [
        run_test("المدة متحددة في مكان واحد بس", there_is_exactly_one_ttl_in_the_source),
        run_test("مفيش علامة كاش مكتوبة بالإيد", every_cache_site_uses_the_shared_marker),
        run_test("شكل العلامة مطابق للـ API", the_marker_has_the_shape_the_api_accepts),
        run_test("المدة قيمة الـ API بيعرفها", the_ttl_is_a_value_the_api_knows),
        run_test("رسالة نصية بتتغلف صح", marking_a_string_message_wraps_it_correctly),
        run_test("العلامة على آخر بلوك بس", marking_a_block_list_marks_only_the_last_block),
        run_test("بلوكات الـ SDK مبتتلمسش", non_dict_messages_are_left_alone),
        run_test("هيدر الساعة لسه موجود للرجوع", the_one_hour_beta_header_is_still_sent),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
