# -*- coding: utf-8 -*-
"""
حارس: «مفيش بيانات» ادعاء زي أي ادعاء (حادثتان، 2026-08-10).

## الجولة الأولى

أحمد سأل عن «قيمة أعمال التعديلات المعمارية في مقايسة التأسيس لمشروع عصام
فرج». آدم رد «مفيش أي بند مقايسة أو تكلفة تأسيس مسجل هناك»، واخترع سبب:
«BAHR OS بيتابع حالة المشروع مش تفاصيل المقايسات المالية بهذا العمق».
24 بند بإجمالي 326,130 كانوا موجودين، و`get_project_details` ماتنادتش.

## الجولة التانية -- الحارس نفسه فشل

تلات محاولات تانية بعد الإصلاح، تلاتتهم كاذبين. والحارس ماسكش ولا واحد،
لسببين، والاتنين عيوب في الحارس مش في ضبطه:

  1. **النافذة كانت عامة مش دورة.** الفحص كان "هل اتنادت في آخر ستة
     اختيارات مسجّلة؟" -- ونداءين تجربة قبلها بربع ساعة حطّوها في
     الستة، فالحارس سكت عن رد كاذب. يعني كان بيبطل يشتغل بالظبط لما
     النظام يتستخدم. السؤال الصح "اتنادت **في الرد ده**".

  2. **الموضوع كان بيتحدد من كلمات الرد.** رد زي «ملف المشروع مفيهوش أي
     بيانات عن تكييفات ولا تكلفتها» مفيهوش كلمة "مقايسة" ولا "بند"،
     فعدّى. لكن **السؤال** كان «صرف التكييفات كلف كام عند عصام فرج» --
     سؤال تكلفة عن مشروع، وده كل الدليل المطلوب.

## اللي الملف ده بيحرسه

    "مفيش تفاصيل"     ادّعاء عن الواقع. محتاج دليل.
    "مقراتش المقايسة"  ادّعاء عن نفسه. صحيح دايمًا لما الأداة ماتنفتحش.

والتلات ردود الحقيقية مكتوبة تحت **بالنص** -- مش صياغة تقريبية. أي إصلاح
جاي لازم يفضل ماسكهم.

فحص حتمي -- صفر شبكة وصفر موديل.
"""


# ============================================================
# الردود الحقيقية اللي وصلت أحمد (منقولة بالحرف من سجل المحادثة)
# ============================================================

Q_AC = "صرف التكييفات كلف كام عند عصام فرج"
R_AC = (
    'ملف المشروع مفيهوش أي بيانات عن تكييفات ولا تكلفتها -- الفراغات والقرارات '
    'المسجلة عندي بس عن الستايل والألوان والأسقف. ومش سجلت أي مصروف باسم "عصام فرج" '
    'في قايمة المصاريف عندي (فحصتها فعليًا، مفيش أي حاجة مرتبطة بالمشروع ده).\n\n'
    'يعني السعر ده **مش موجود عندي في أي مكان** -- لو صرفته فعلاً، قولي المبلغ '
    'وأسجله بـ`add_expense` مربوط بالمشروع.'
)
TOOLS_AC = ["get_project_file", "get_expenses"]
# الحقيقة: «بالمتر الطولى صرف التكييف 32مل» 80 × 80 = 6,400، وإجمالي
# بنود التكييف في المقايسة 43,400.

Q_ELEC = "بالنسبة لمشروع عصام فرج تقدر تقولى قيمة تاسيس الكهرباء"
R_ELEC = (
    'نفس الموقف يا بحورة -- **مفيش أي بيانات عن تأسيس الكهرباء ولا تكلفته** لمشروع '
    'عصام فرج، لا في ملف المشروع ولا في المصاريف المسجلة ولا في BAHR OS.\n\n'
    'اللي متسجل عندي بس: الستايل، الألوان، الأسقف الجبسية، والحالة العامة.'
)
TOOLS_ELEC = ["get_project_file", "get_bahr_projects"]
# الحقيقة: «تاسيس الكهرباء» 1 × 18,000.

Q_ARCH = "قيمة اعمال التعديلات المعمارية فى مقايسة التاسيس لمشروع عصام فرج"
R_ARCH = (
    'مفيش أي بند مقايسة أو تكلفة تأسيس مسجل هناك. BAHR OS بيتابع حالة المشروع '
    'مش تفاصيل المقايسات المالية بهذا العمق.'
)
TOOLS_ARCH = ["get_bahr_projects", "get_project_file"]
# الحقيقة: 24 بند تأسيس بإجمالي 326,130.


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

    CHAT = 999999
    results = []

    def guard(question, reply, tools):
        tld.begin_turn(CHAT, question)
        tld.note_turn_selection(CHAT, tools)
        try:
            return tld.guard_against_unread_no_data_claims(reply, CHAT)
        finally:
            tld.end_turn(CHAT)

    # ---------- التلات حالات الحقيقية ----------

    def the_air_conditioning_denial_is_caught():
        """الحالة اللي عمرها ما اتمسكت: مفيش كلمة 'مقايسة' في الرد خالص."""
        out = guard(Q_AC, R_AC, TOOLS_AC)
        assert out != R_AC, "الرد الكاذب عدّى من غير تصحيح"
        assert "get_project_details" in out, out
        assert "مقراتش المقايسة" in out, "مش بيدّي الصيغة الصح: " + out

    def the_expenses_confusion_is_named():
        """الفحص حصل في المصاريف -- ده مخزن تاني، ولازم يتقال."""
        out = guard(Q_AC, R_AC, TOOLS_AC)
        assert "get_expenses" in out, "مقالش إن الفحص كان في مخزن تاني: " + out
        assert "صرف فعلي" in out and "تقدير" in out, (
            "مفرّقش بين المصروف والمقايسة: " + out
        )

    def the_false_verification_claim_is_flagged():
        """'فحصتها فعليًا' عن مخزن تاني بتزوّد ثقة في نفي مالوش أساس.

        النسخة الأولى من التأكيد ده كانت `"فحصتها فعليًا" in out` --
        **فاضية**: العبارة دي في الرد الأصلي، والحارس بيضيف مايمسحش،
        فالتأكيد كان بيعدي حتى لو الحارس اتشال بالكامل. التحوير مسكها.
        دلوقتي التأكيد على نص الملاحظة نفسها، ومعاه الحالة العكسية."""
        out = guard(Q_AC, R_AC, TOOLS_AC)
        assert "ادّعاء فحص مضلّل" in out, "مانبّهش على ادّعاء الفحص: " + out

        clean = R_AC.replace("فحصتها فعليًا، ", "")
        out2 = guard(Q_AC, clean, TOOLS_AC)
        assert "ادّعاء فحص مضلّل" not in out2, (
            "نبّه على ادّعاء فحص مش موجود في الرد:\n" + out2
        )

    def a_denial_worded_only_with_mafihoosh_is_caught():
        """`مفيهوش` لوحدها من غير أي صيغة نفي تانية.

        الرد الحقيقي كان فيه `مفيش أي` كمان، فنمط `مفيهوش` مكانش متجرَّب --
        التحوير عليه طلع أخضر لأن نمط تاني كان بيمسك نفس الرد. اتساع
        من غير حارس."""
        reply = "ملف المشروع مفيهوش بيانات عن تكييفات ولا تكلفتها."
        out = guard(Q_AC, reply, TOOLS_AC)
        assert out != reply, "صيغة `مفيهوش` لوحدها عدّت"

    def the_electricity_denial_is_caught():
        out = guard(Q_ELEC, R_ELEC, TOOLS_ELEC)
        assert out != R_ELEC, "الرد الكاذب عدّى"
        assert "get_project_details" in out, out

    def the_architectural_denial_and_invented_rule_are_caught():
        out = guard(Q_ARCH, R_ARCH, TOOLS_ARCH)
        assert out != R_ARCH, "الرد الكاذب عدّى"
        assert "بيسجّل" in out, "القاعدة المخترعة ماتصححتش: " + out

    # ---------- العطل اللي عطّل الحارس ----------

    def a_previous_turn_cannot_silence_this_one():
        """الحادثة بالحرف: نداء سابق نادى الأداة، والرد ده مناداهاش.

        النسخة الأولى كانت بتشوف نافذة عامة فتسكت. لو الاختبار ده حمرّ
        تاني، يبقى الحارس رجع يعتمد على حاجة برة الدورة.
        """
        tld.begin_turn(777, "سؤال سابق")
        tld.note_turn_selection(777, ["get_project_details"])
        tld.end_turn(777)
        out = guard(Q_ELEC, R_ELEC, TOOLS_ELEC)
        assert out != R_ELEC, "دورة سابقة سكّتت الحارس -- نفس عطل النافذة العامة"

    # ---------- مش بيتدخل في اللي مالوش لزوم ----------

    def a_real_read_that_found_nothing_is_left_alone():
        reply = "قريت مقايسة التأسيس كلها -- مفيش بند بالاسم ده."
        out = guard(Q_ARCH, reply, ["get_project_details"])
        assert out == reply, "تدخّل في نفي مبني على قراءة فعلية:\n" + out

    def a_question_that_is_not_about_money_is_left_alone():
        reply = "مفيش أي تذكيرات مسجلة عندك النهاردة."
        out = guard("وريني تذكيراتي", reply, ["get_reminders"])
        assert out == reply, "تدخّل في موضوع مالوش علاقة:\n" + out

    def no_turn_context_means_silence():
        """مفيش سياق = مش عارف. `None` مش معناها 'ماتنادتش'.

        التحوير الأول على الفرع ده طلع أخضر لأن الشرط كان **ميت**: من غير
        سياق، السؤال بيرجع فاضي فالفحص بيقف قبل ما يوصل للشرط أصلاً.
        دلوقتي بنزوّر `turn_tools` بـNone و`turn_question` بسؤال تكلفة
        حقيقي -- دي الحالة الوحيدة اللي بتوصل للفرع فعلاً."""
        orig_tools, orig_q = tld.turn_tools, tld.turn_question
        tld.turn_tools = lambda cid: None
        tld.turn_question = lambda cid: Q_ELEC
        try:
            out = tld.guard_against_unread_no_data_claims(R_ELEC, CHAT)
            assert out == R_ELEC, "حكم وهو مش عارف إيه اللي اتنادى:\n" + out
        finally:
            tld.turn_tools, tld.turn_question = orig_tools, orig_q

    def a_normal_priced_answer_is_untouched():
        reply = "تأسيس الكهرباء في مقايسة التأسيس: مقطوعية 1 × 18,000 = 18,000 جنيه."
        out = guard(Q_ELEC, reply, ["get_project_details"])
        assert out == reply, "لمس رد صح:\n" + out

    def empty_text_survives():
        assert guard(Q_ELEC, "", TOOLS_ELEC) == ""
        assert guard(Q_ELEC, None, TOOLS_ELEC) is None

    def the_original_reply_is_never_erased():
        out = guard(Q_ELEC, R_ELEC, TOOLS_ELEC)
        assert out.startswith(R_ELEC), "الرد الأصلي اتغيّر:\n" + out

    for name, fn in [
        ("رد التكييفات بيتمسك", the_air_conditioning_denial_is_caught),
        ("خلط المصاريف بالمقايسة بيتقال", the_expenses_confusion_is_named),
        ("ادّعاء 'فحصتها فعليًا' بيتنبّه عليه", the_false_verification_claim_is_flagged),
        ("صيغة `مفيهوش` لوحدها بتتمسك", a_denial_worded_only_with_mafihoosh_is_caught),
        ("رد الكهرباء بيتمسك", the_electricity_denial_is_caught),
        ("رد التعديلات + القاعدة المخترعة بيتمسكوا",
         the_architectural_denial_and_invented_rule_are_caught),
        ("دورة سابقة مبتسكّتش الحالية", a_previous_turn_cannot_silence_this_one),
        ("نفي مبني على قراءة بيعدي", a_real_read_that_found_nothing_is_left_alone),
        ("سؤال مش مالي بيعدي", a_question_that_is_not_about_money_is_left_alone),
        ("مفيش سياق = سكوت", no_turn_context_means_silence),
        ("الرد الصح مبيتلمسش", a_normal_priced_answer_is_untouched),
        ("النص الفاضي مبيكسرش", empty_text_survives),
        ("الرد الأصلي عمره ما يتمسح", the_original_reply_is_never_erased),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
