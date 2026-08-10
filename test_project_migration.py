# -*- coding: utf-8 -*-
"""
حارس تحويل نقل المشاريع لـSupabase (2026-08-10).

`build_payloads` دالة صافية بتحوّل مستند Firestore لصفوف الجداول
المفكوكة -- وهي الجزء الخطر في النقل: الكتابة نفسها upsert رفيع، لكن أي
غلطة هنا بتتكتب في الإنتاج وشكلها سليم.

التلات حاجات اللي لو اتكسرت مش هتبان في العدّ:

  1. **الترتيب.** البند `is_sub=true` تابع لأقرب بند قبله `is_sub=false`،
     ومفيش مفتاح بيربطهم. 95 صف بترتيب متبعتر بيدّي نفس الرقم بالظبط
     وهرم مختلف تمامًا.

  2. **الأبعاد الخام.** الوحدة هي اللي بتحدد أنهي بُعد له معنى. جمعهم في
     عمود كمية واحد بيدّي نفس عدد الصفوف ويمنع إعادة الحساب للأبد.

  3. **الوحدات.** التطبيع مسموح للترميز بس (`م2`->`م²`)، وممنوع لأي وحدة
     ليها معنى مختلف. تحويل `عدد` لـ`مقطوعية` عشان تعدّي من قيد السكيما
     بيزوّر رقم في مقايسة حقيقية.

صفر شبكة وصفر Firestore -- الدالة بتاخد الديكت جاهز.
"""

import copy


SOURCE = {
    "name": "مشروع اختبار",
    "client": "عميل",
    "area": 130,
    "level": "متوسط",
    "status": "delayed",
    "allowedSupervisors": ["a@b.com"],
    "note": "",
    "createdBy": "U5SoDaAk3ERpdbyjk3rYi9kZyUI2",
    "deadline": "2026-08-15",
    "completion": 40,
    "last_report": "2026-07-22",
    "updatedAt": 1786332174723,
    "last_updated": "2026-07-22T22:30:54.549816+03:00",
    "foundationdata": {
        "client": "عميل", "project": "مشروع", "area": 130,
        "items": [
            {"desc": "بند رئيسي", "unit": "مقطوعية", "qty": 1, "price": 8200, "sub": False},
            {"desc": "تابع ليه",  "unit": "م2",      "qty": 3, "price": 100,  "sub": True},
            {"desc": "رئيسي تاني", "unit": "عدد",    "qty": 9.5, "price": 2900, "sub": False},
        ],
    },
    "quantity": {
        "client": "عميل", "project": "مشروع", "area": 130,
        "items": [
            {"desc": "خرسانة", "unit": "م³", "length": 2, "width": 1.5,
             "height": 0.2, "count": 3, "wastage": 5, "phase": "", "sub": False,
             "images": []},
            {"desc": "إضاءة", "unit": "مقطوعية", "length": 1, "width": 1,
             "height": 1, "count": 12, "wastage": 0, "phase": "", "sub": False,
             "images": []},
        ],
    },
}


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
    from migrate_project_to_supabase import build_payloads, MigrationError

    def build(doc=None):
        return build_payloads("PRJ-TEST", doc or copy.deepcopy(SOURCE))

    def order_is_preserved_exactly():
        """الترتيب هو العلاقة -- لازم يطابق المصدر بند ببند."""
        _, phases, _, _ = build()
        items = phases[0]["items"]
        assert [i["position"] for i in items] == [0, 1, 2], items
        assert [i["description"] for i in items] == ["بند رئيسي", "تابع ليه", "رئيسي تاني"]
        assert [i["is_sub"] for i in items] == [False, True, False], (
            "علم التبعية اتغيّر -- الهرم بيتحدد بيه وبالترتيب بس"
        )

    def raw_dimensions_survive_untouched():
        """كل بُعد في عموده. مفيش تجميع ولا حساب."""
        _, _, quantity, _ = build()
        first = quantity["items"][0]
        assert (first["length"], first["width"], first["height"], first["count"]) == (2, 1.5, 0.2, 3), first
        assert first["wastage_pct"] == 5, first
        # الفخ اللي الاختبار ده موجود عشانه: عمود كمية واحد
        for forbidden in ("qty", "quantity", "amount", "total"):
            assert forbidden not in first, (
                "الأبعاد اتجمّعت في " + forbidden + " -- المراجعة بقت مستحيلة"
            )

    def a_count_of_one_is_not_defaulted_away():
        """`count` افتراضيه 1 مش 0 -- الصفر بيصفّر المقدار كله."""
        doc = copy.deepcopy(SOURCE)
        doc["quantity"]["items"][0].pop("count")
        _, _, quantity, _ = build(doc)
        assert quantity["items"][0]["count"] == 1, quantity["items"][0]

    def encoding_fixes_are_reported_by_name():
        """التطبيع مسموح، الصمت لأ."""
        _, phases, _, fixes = build()
        assert phases[0]["items"][1]["unit"] == "م²", "م2 ماتطبعتش"
        assert len(fixes) == 1, fixes
        where, before, after = fixes[0]
        assert before == "م2" and after == "م²", fixes
        assert "foundationdata[1]" == where, "التقرير مش بيقول أنهي بند: " + where

    def a_real_unit_is_never_converted():
        """`عدد` وحدة حقيقية -- بتعدي زي ما هي، مبتتحولش لمقطوعية."""
        _, phases, _, fixes = build()
        assert phases[0]["items"][2]["unit"] == "عدد", phases[0]["items"][2]
        assert not any(f[1] == "عدد" for f in fixes), "عدد اتحوّلت: " + str(fixes)

    def an_unknown_unit_stops_the_migration():
        """وحدة مش معروفة = وقفة، مش تخمين ولا تخطي."""
        doc = copy.deepcopy(SOURCE)
        doc["foundationdata"]["items"][0]["unit"] = "كرتونة"
        try:
            build(doc)
        except MigrationError as e:
            assert "كرتونة" in str(e), str(e)
            return
        raise AssertionError("وحدة مجهولة عدّت من غير ما توقف النقل")

    def a_stored_image_stops_the_migration():
        """الصور base64 مالهاش مسار رفع هنا -- النقل هيضيّعها."""
        doc = copy.deepcopy(SOURCE)
        doc["quantity"]["items"][0]["images"] = ["data:image/jpeg;base64,AAAA"]
        try:
            build(doc)
        except MigrationError as e:
            assert "صورة" in str(e), str(e)
            return
        raise AssertionError("صورة مخزّنة عدّت والنقل كمّل -- الصورة ضاعت في صمت")

    def the_two_timestamps_collapse_to_the_newer():
        """عمودين لنفس المعنى -> الأحدث. الأقدم مش معلومة زيادة."""
        _, _, _, _ = build()
        row, _, _, _ = build()
        assert row["updated_at"].startswith("2026-08-10"), (
            "أخد الأقدم: " + str(row["updated_at"])
        )

    def empty_phase_becomes_null_not_empty_string():
        """السكيما بترفض '' -- المعنى 'متجمّعش في أي مرحلة'."""
        _, _, quantity, _ = build()
        assert quantity["items"][0]["phase"] is None, quantity["items"][0]

    def completion_is_cast_to_text_not_left_as_int():
        """العمود نصي والمصدر بيكتب رقم -- التحويل صريح مش متروك لـPostgREST."""
        row, _, _, _ = build()
        assert row["completion"] == "40", repr(row["completion"])

    results = [
        run_test("الترتيب بيتحفظ حرفيًا", order_is_preserved_exactly),
        run_test("الأبعاد الخام بتعدي زي ما هي", raw_dimensions_survive_untouched),
        run_test("count الناقص بيبقى 1 مش 0", a_count_of_one_is_not_defaulted_away),
        run_test("تطبيع الترميز بيتقال بالاسم", encoding_fixes_are_reported_by_name),
        run_test("الوحدة الحقيقية عمرها ما تتحوّل", a_real_unit_is_never_converted),
        run_test("وحدة مجهولة بتوقف النقل", an_unknown_unit_stops_the_migration),
        run_test("صورة مخزّنة بتوقف النقل", a_stored_image_stops_the_migration),
        run_test("العمودين الزمنيين بياخدوا الأحدث", the_two_timestamps_collapse_to_the_newer),
        run_test("المرحلة الفاضية بتبقى NULL", empty_phase_becomes_null_not_empty_string),
        run_test("completion بيتحوّل لنص", completion_is_cast_to_text_not_left_as_int),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
