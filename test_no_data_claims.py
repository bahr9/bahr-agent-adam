# -*- coding: utf-8 -*-
"""
حارس: «مفيش بيانات» ادعاء زي أي ادعاء (حادثة 2026-08-10).

أحمد سأل عن «قيمة أعمال التعديلات المعمارية في مقايسة التأسيس لمشروع
عصام فرج». آدم رد:

    «مفيش أي بند مقايسة أو تكلفة تأسيس مسجل هناك»
    «BAHR OS بيتابع حالة المشروع مش تفاصيل المقايسات المالية بهذا العمق»

الاتنين غلط. 24 بند تأسيس بإجمالي 326,130 كانوا موجودين في نفس اللحظة،
و`get_project_details` بترجّعهم. سجل `tool_lifecycle` بيقول التسلسل:

    get_bahr_projects -> end_turn -> get_project_file -> end_turn

`get_project_details` **عمرها ما اتنادت**.

الفرق اللي الملف ده بيحرسه:

    "مفيش تفاصيل"     ادّعاء عن الواقع. محتاج دليل.
    "مقراتش التفاصيل"  ادّعاء عن نفسه. صحيح دايمًا لما الأداة ماتنفتحش.

والجملة التانية (اختراع قاعدة عن BAHR OS) هي النمط المعروف: الموديل
بيبرّر نتيجة غلط بقاعدة بيألّفها. مفيش أي مصدر آدم يعرف منه إيه اللي
BAHR OS بيسجّله.

فحص حتمي -- صفر شبكة وصفر موديل.
"""


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


def main():
    from services import tool_lifecycle_diagnostics as tld

    original = tld._recently_selected
    results = []

    def with_selection(state):
        """state: True اتنادت / False ماتنادتش / None مفيش دليل"""
        tld._recently_selected = lambda name, lookback=50: state

    # ---------- (1) الحادثة الأصلية ----------
    def the_original_incident_is_caught():
        with_selection(False)
        reply = "مفيش أي بند مقايسة أو تكلفة تأسيس مسجل هناك."
        out = tld.guard_against_unread_no_data_claims(reply)
        assert out != reply, "الادّعاء عدّى من غير تصحيح"
        assert "get_project_details" in out, out
        assert "مقراتش التفاصيل" in out, "التصحيح مش بيدّي الصيغة الصح: " + out

    def the_invented_capability_rule_is_caught():
        with_selection(True)      # حتى لو الأداة اتنادت، الاختراع اختراع
        reply = "BAHR OS بيتابع حالة المشروع مش تفاصيل المقايسات المالية بهذا العمق."
        out = tld.guard_against_unread_no_data_claims(reply)
        assert out != reply, "قاعدة مخترعة عدّت"
        assert "بيسجّل" in out, out

    # ---------- (2) مش بيتدخل في اللي مالوش لزوم ----------
    def a_real_read_that_found_nothing_is_left_alone():
        """لو الأداة اتنادت فعلًا ورجعت فاضي، 'مفيش' إجابة صحيحة."""
        with_selection(True)
        reply = "قريت تفاصيل المشروع -- مفيش أي بنود مقايسة متسجلة عليه لسه."
        out = tld.guard_against_unread_no_data_claims(reply)
        assert out == reply, "تدخّل في نفي مبني على قراءة فعلية:\n" + out

    def an_unrelated_denial_is_left_alone():
        """'مفيش تذكيرات' مالهاش علاقة بالمقايسات."""
        with_selection(False)
        reply = "مفيش أي تذكيرات مسجلة عندك النهاردة."
        out = tld.guard_against_unread_no_data_claims(reply)
        assert out == reply, "تدخّل في موضوع تاني خالص:\n" + out

    def an_empty_lifecycle_log_does_not_trigger():
        """None = مفيش دليل خالص. مانتعاملش معاها كـ'ماتنادتش'."""
        with_selection(None)
        reply = "مفيش أي بند مقايسة مسجل."
        out = tld.guard_against_unread_no_data_claims(reply)
        assert out == reply, "طلّع ملاحظة على سجل فاضي:\n" + out

    def a_normal_answer_is_untouched():
        with_selection(False)
        reply = "مقايسة التأسيس فيها 24 بند بإجمالي 326,130 جنيه."
        assert tld.guard_against_unread_no_data_claims(reply) == reply

    def empty_text_survives():
        with_selection(False)
        assert tld.guard_against_unread_no_data_claims("") == ""
        assert tld.guard_against_unread_no_data_claims(None) is None

    # ---------- (3) الحارس بيضيف مايمسحش ----------
    def the_original_reply_is_never_erased():
        """نفس فلسفة الحارس التاني: إضافة، مش محو."""
        with_selection(False)
        reply = "مفيش أي بند مقايسة مسجل هناك."
        out = tld.guard_against_unread_no_data_claims(reply)
        assert out.startswith(reply), "الرد الأصلي اتغيّر:\n" + out

    try:
        for name, fn in [
            ("الحادثة الأصلية بتتمسك", the_original_incident_is_caught),
            ("القاعدة المخترعة بتتمسك", the_invented_capability_rule_is_caught),
            ("نفي مبني على قراءة بيعدي", a_real_read_that_found_nothing_is_left_alone),
            ("نفي في موضوع تاني بيعدي", an_unrelated_denial_is_left_alone),
            ("سجل فاضي مش بيولّد ملاحظة", an_empty_lifecycle_log_does_not_trigger),
            ("الرد العادي مبيتلمسش", a_normal_answer_is_untouched),
            ("النص الفاضي مبيكسرش", empty_text_survives),
            ("الرد الأصلي عمره ما يتمسح", the_original_reply_is_never_erased),
        ]:
            results.append(run_test(name, fn))
    finally:
        tld._recently_selected = original

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
