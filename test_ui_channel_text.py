# -*- coding: utf-8 -*-
"""
قناة الواجهة: معرّف الرسالة + تحويل نص تليجرام لنص عادي.

الحادثتين اللي ولّدوا الملف ده -- من تقرير أول تشغيل حقيقي للقناة
(adam-ui، 2026-08-07):

  1) كل رد كان بيوصل بـ messageId = "m-1" (نص ثابت مكتوب بالإيد، مش
     عدّاد بيتصفّر). الواجهة اضطرت تركّب مفتاح محلي من turnId/messageId
     عشان تفرّق بين الردود.

  2) الرد بيتولد لتليجرام اللي بيرندر Markdown، والواجهة بتلحق الـ delta
     "كما هي" (العقد، قسم 3.2) -- فالنجوم والجداول الخام كانت بتتعرض
     للمستخدم حرف بحرف.

بيشتغل من غير شبكة ومن غير Flask app -- بينادي الدوال مباشرة.
"""

from services import ui_channel


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
    plain = ui_channel._to_plain_text

    # ---------- معرّف الرسالة ----------

    def message_ids_are_unique_across_replies():
        """الباگ الأصلي: كل رد كان بياخد "m-1"."""
        seen = {ui_channel._new_message_id() for _ in range(200)}
        assert len(seen) == 200, f"معرّفات اتكررت -- {200 - len(seen)} تكرار"
        assert "m-1" not in seen, "لسه بيولّد المعرّف الثابت القديم"

    def message_id_keeps_the_contract_shape():
        """العقد بيلزم بوجود الحقل؛ بنحافظ على نفس شكل turnId (بادئة + hex)."""
        mid = ui_channel._new_message_id()
        assert mid.startswith("m-"), mid
        assert len(mid) == 10, f"الشكل اتغير: {mid}"
        int(mid[2:], 16)                      # لازم يكون hex صالح

    # ---------- الجداول ----------

    def markdown_tables_are_dropped_entirely():
        """الجدول بيتبعت كبطاقة evidence -- تكراره كنص خام عرض مزدوج."""
        text = (
            "دي أقساطك:\n"
            "| الشهر | المبلغ |\n"
            "|-------|--------|\n"
            "| يوليو | 13000 |\n"
            "| أغسطس | 13000 |\n"
            "وده كل اللي عندي."
        )
        out = plain(text)
        assert "|" not in out, f"أنبوبة فضلت في النص:\n{out}"
        assert "13000" not in out, f"صفوف الجدول فضلت:\n{out}"
        assert "دي أقساطك:" in out and "وده كل اللي عندي." in out, out

    def a_line_with_pipes_that_is_not_a_table_survives():
        """من غير سطر فاصل مفيش جدول -- ممنوع ناكل نص عادي."""
        text = "الاختيارات | المتاحة | كلها شغالة"
        assert plain(text) == text

    # ---------- التنسيق ----------

    def bold_and_italic_markers_are_removed_but_words_stay():
        assert plain("عندك **7 أقساط** متأخرة") == "عندك 7 أقساط متأخرة"
        assert plain("ده *مهم* جدًا") == "ده مهم جدًا"
        assert plain("__تنبيه__ مهم") == "تنبيه مهم"
        assert plain("***قوي جدًا***") == "قوي جدًا"

    def headings_lose_the_hashes_only():
        assert plain("## الملخص\nالتفاصيل تحت") == "الملخص\nالتفاصيل تحت"

    def links_collapse_to_their_text():
        assert plain("شوف [الموقع](https://bahr.design) دلوقتي") == "شوف الموقع دلوقتي"

    def inline_code_loses_the_backticks():
        assert plain("شغّل `git status` الأول") == "شغّل git status الأول"

    def bullets_become_real_bullets():
        assert plain("* أول\n* تاني") == "• أول\n• تاني"

    def arabic_text_is_never_mangled():
        """التنسيق بيتشال، الحروف والتشكيل والأرقام مبيتلمسوش."""
        text = "أهلاً يا أحمد، عندك ٣ أقساط بقيمة 82,646 جنيه."
        assert plain(text) == text

    def a_lone_star_is_not_treated_as_formatting():
        """نجمة واحدة من غير قافلة مش تنسيق -- ممنوع تتاكل."""
        text = "العلامة * معناها مطلوب"
        assert plain(text) == text

    def empty_and_none_are_safe():
        assert plain("") == ""
        assert plain(None) is None

    def the_real_shape_from_the_report():
        """الشكل اللي وصل الواجهة فعلاً: نجوم + جدول خام في رد واحد."""
        text = (
            "**ملخص الأقساط**\n\n"
            "| الشهر | الحالة |\n"
            "|---|---|\n"
            "| يوليو | مدفوع |\n\n"
            "الباقي **مستحق** الشهر الجاي."
        )
        out = plain(text)
        assert "*" not in out and "|" not in out, out
        assert "ملخص الأقساط" in out and "مستحق" in out, out

    results = [
        run_test("معرّف الرسالة فريد لكل رد", message_ids_are_unique_across_replies),
        run_test("شكل المعرّف متوافق مع العقد", message_id_keeps_the_contract_shape),
        run_test("جداول الماركداون بتتشال بالكامل", markdown_tables_are_dropped_entirely),
        run_test("سطر فيه أنابيب ومش جدول بيفضل زي ما هو", a_line_with_pipes_that_is_not_a_table_survives),
        run_test("علامات العريض والمائل بتتشال والكلام بيفضل", bold_and_italic_markers_are_removed_but_words_stay),
        run_test("العناوين بتفقد علامات # بس", headings_lose_the_hashes_only),
        run_test("الروابط بترجع لنصها", links_collapse_to_their_text),
        run_test("الكود السطري بيفقد الباك-تِك", inline_code_loses_the_backticks),
        run_test("النقط بتبقى نقط حقيقية", bullets_become_real_bullets),
        run_test("النص العربي مبيتخربش", arabic_text_is_never_mangled),
        run_test("نجمة وحيدة مش تنسيق", a_lone_star_is_not_treated_as_formatting),
        run_test("النص الفاضي وNone آمنين", empty_and_none_are_safe),
        run_test("الشكل الحقيقي من تقرير الواجهة", the_real_shape_from_the_report),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
