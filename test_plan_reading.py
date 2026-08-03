# -*- coding: utf-8 -*-
"""
Tests First -- قراءة البلانات (2b من دمج دور HOPE، ADR 0006).

التجربة الحية اللي سبقت الكود ده (2026-08-04، بلان عصام فرج الحقيقي):
الموديل قرا 8 فراغات بأسمائها (بما فيهم Noor/Adham bedroom) وأبعاد خطوط
القياس (7.70×5.99 للريسبشن، 5.00×3.78 للماستر...) وقال "مش واضح" بدل
التخمين -- وغلط غلطة إسناد واحدة: لزق تاريخ اللوحة (21 oct) في اسم
المشروع كأنه مدينة. الـprompt هنا مبني على النتيجة دي بالظبط: فصل خانات
الـtitle block + قاعدة "التواريخ مش أماكن".

الفحوصات هنا حتمية بحتة (صفر LLM): منطق "ده بلان ولا مستند؟" وبنية
الـprompt. جودة الاستخراج الفعلية بتتقاس على بلانات حقيقية بمعلوم أحمد
(زي تجربة عصام فرج).
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
    from handlers.document_handler import looks_like_plan
    from services.claude_service import PLAN_EXTRACTION_PROMPT, build_plan_prompt

    results = []

    # ---------- routing: what counts as a plan ----------

    def plan_filenames_route_to_vision():
        for name in (
            "furniture plan-Model.pdf essam farag.pdf",
            "AS BULIT gardenia-Model.pdf",
            "مخطط الشقة.pdf",
            "بلان الدور الاول.pdf",
            "unit-D10-layout.pdf",
        ):
            assert looks_like_plan(name, "", "نص طويل " * 200), name

    def plan_captions_route_to_vision():
        assert looks_like_plan("scan001.pdf", "اقرالي البلان ده", "نص " * 300)
        assert looks_like_plan("doc.pdf", "دي لوحة فرش لشقة", "نص " * 300)

    def sparse_text_pdf_routes_to_vision():
        # CAD exports carry almost no linear text -- pypdf gets scraps.
        assert looks_like_plan("scan-unit.pdf", "", "N sec1 2.40")
        assert looks_like_plan("empty.pdf", "", "")

    def text_documents_stay_on_the_text_path():
        contract_text = "عقد اتفاق بين الطرف الأول والطرف الثاني " * 40
        assert not looks_like_plan("عقد المقاولة.pdf", "", contract_text)
        assert not looks_like_plan("عرض سعر التشطيب.pdf", "شوف العرض ده", contract_text)

    # ---------- the extraction prompt discipline ----------

    def title_block_fields_are_separated():
        for field in ("اسم المشروع", "المدينة/الموقع", "تاريخ اللوحة", "رقم اللوحة"):
            assert field in PLAN_EXTRACTION_PROMPT, field

    def dates_are_not_places():
        assert "التاريخ مش مكان" in PLAN_EXTRACTION_PROMPT
        assert "6 أكتوبر" in PLAN_EXTRACTION_PROMPT  # المدينة-الفخ بالاسم

    def honesty_over_completeness():
        assert "مش واضح" in PLAN_EXTRACTION_PROMPT
        assert "متخمنش" in PLAN_EXTRACTION_PROMPT or "بدل ما تخمّن" in PLAN_EXTRACTION_PROMPT

    def partial_dims_nuance_present():
        assert "أبعاد جزئية" in PLAN_EXTRACTION_PROMPT

    def caption_is_woven_into_the_prompt():
        built = build_plan_prompt("ركز في اوضة الأطفال")
        assert PLAN_EXTRACTION_PROMPT in built
        assert "ركز في اوضة الأطفال" in built
        assert build_plan_prompt("") == PLAN_EXTRACTION_PROMPT

    for name, fn in [
        ("أسماء ملفات البلانات بتتوجه للـvision", plan_filenames_route_to_vision),
        ("الـcaption بيوجّه للـvision", plan_captions_route_to_vision),
        ("PDF نصه شحيح = بلان/سكان", sparse_text_pdf_routes_to_vision),
        ("المستندات النصية فاضلة على مسار النص", text_documents_stay_on_the_text_path),
        ("خانات الـtitle block منفصلة", title_block_fields_are_separated),
        ("التواريخ مش أماكن (درس 21 أكتوبر)", dates_are_not_places),
        ("مش واضح أشرف من التخمين", honesty_over_completeness),
        ("تمييز الأبعاد الجزئية", partial_dims_nuance_present),
        ("تعليق أحمد بيتحاك في الـprompt", caption_is_woven_into_the_prompt),
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
