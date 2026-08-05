# -*- coding: utf-8 -*-
"""
Tests First -- أمان المسار المالي للأقساط (أوديت 2026-08-05).

باگين اتغطّوا هنا:

1) fail-open في القراءة: get_loan_paid_map كان بيرجع {} سواء القراءة نجحت
   وملقتش حاجة، أو فشلت خالص. فأثناء أي عطل لحظي في Firestore الملخص كان
   بيحسب "مدفوع = صفر" لكل برنامج ويعرضها كحقيقة -- يعني بيقول لأحمد إنه
   مدين بالإجمالي كامل شامل شهور دفعها فعلاً.

2) نافذة المتأخرات: get_overdue_installments كانت بتبص على الشهر اللي فات
   **بس**، فقسط يونيو مدفعش كان بيختفي أول ما أغسطس يبدأ.

كله بـ paid_map مزيّف -- صفر Firestore.
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
    import services.firebase_service as fs
    from services import loan_service
    from services.loan_service import LoanDataUnavailable

    original_getter = fs.get_loan_paid_map
    original_current_month = loan_service.get_current_month_key

    def with_map(value):
        fs.get_loan_paid_map = lambda: value

    def restore():
        fs.get_loan_paid_map = original_getter
        loan_service.get_current_month_key = original_current_month

    results = []

    # ---------- 1) فشل القراءة لازم يوقف ----------
    def overview_refuses_on_read_failure():
        """الحارس الأساسي: ممنوع يطلّع أرقام مالية والقراءة فشلت."""
        with_map(None)
        try:
            loan_service.get_overview()
        except LoanDataUnavailable:
            return
        finally:
            restore()
        raise AssertionError("طلّع ملخص مالي رغم إن القراءة فشلت")

    def overdue_refuses_on_read_failure():
        with_map(None)
        try:
            loan_service.get_overdue_installments()
        except LoanDataUnavailable:
            return
        finally:
            restore()
        raise AssertionError("طلّع متأخرات رغم إن القراءة فشلت")

    def is_paid_refuses_on_read_failure():
        with_map(None)
        try:
            loan_service.is_paid("ca", 0)
        except LoanDataUnavailable:
            return
        finally:
            restore()
        raise AssertionError("رجّع حالة دفع رغم إن القراءة فشلت")

    def month_installments_refuses_on_read_failure():
        with_map(None)
        try:
            loan_service.get_month_installments("01/08/2026")
        except LoanDataUnavailable:
            return
        finally:
            restore()
        raise AssertionError("رجّع أقساط شهر رغم إن القراءة فشلت")

    # ---------- الفراغ الحقيقي لازم يعدّي ----------
    def genuinely_empty_map_is_not_an_error():
        """مفيش أقساط اتسجلت لسه = حالة صحيحة، مش عطل."""
        with_map({})
        try:
            overview = loan_service.get_overview()
            assert overview["total_paid"] == 0, overview
            assert overview["total_remaining"] > 0, overview
        finally:
            restore()

    def paid_installments_are_counted():
        program = loan_service._find_program("فاليو")
        first_amount = program["installments"][0]["amount"]
        with_map({"valu_0": True})
        try:
            overview = loan_service.get_overview()
            assert overview["total_paid"] == first_amount, overview["total_paid"]
        finally:
            restore()

    # ---------- 2) نافذة المتأخرات ----------
    def overdue_covers_more_than_one_past_month():
        """الحارس: قسط من شهرين فاتوا لازم يفضل ظاهر."""
        loan_service.get_current_month_key = lambda: "01/10/2026"
        with_map({})
        try:
            items, total, earliest = loan_service.get_overdue_installments()
            months = {i["date"] for i in items}
            assert len(months) >= 3, f"غطّى {len(months)} شهر بس: {sorted(months)}"
            assert "01/07/2026" in months, sorted(months)
            assert total > 0
        finally:
            restore()

    def overdue_excludes_current_and_future():
        loan_service.get_current_month_key = lambda: "01/09/2026"
        with_map({})
        try:
            items, _, _ = loan_service.get_overdue_installments()
            for item in items:
                assert item["date"] not in ("01/09/2026", "01/10/2026"), item
        finally:
            restore()

    def overdue_skips_paid_ones():
        loan_service.get_current_month_key = lambda: "01/09/2026"
        with_map({})
        try:
            before, _, _ = loan_service.get_overdue_installments()
        finally:
            restore()

        loan_service.get_current_month_key = lambda: "01/09/2026"
        with_map({"valu_0": True})
        try:
            after, _, _ = loan_service.get_overdue_installments()
        finally:
            restore()

        assert len(after) == len(before) - 1, f"{len(before)} -> {len(after)}"

    def overdue_items_carry_their_month():
        loan_service.get_current_month_key = lambda: "01/10/2026"
        with_map({})
        try:
            items, _, _ = loan_service.get_overdue_installments()
            assert all(i.get("date") for i in items), "فيه عنصر من غير تاريخ"
        finally:
            restore()

    def overdue_is_sorted_oldest_first():
        loan_service.get_current_month_key = lambda: "01/10/2026"
        with_map({})
        try:
            items, _, earliest = loan_service.get_overdue_installments()
            keys = [loan_service._month_sort_key(i["date"]) for i in items]
            assert keys == sorted(keys), "المتأخرات مش مرتبة من الأقدم"
            assert earliest == items[0]["date"], earliest
        finally:
            restore()

    for name, fn in [
        ("الملخص بيرفض يشتغل والقراءة فشلت (الحارس الأساسي)", overview_refuses_on_read_failure),
        ("المتأخرات بترفض تشتغل والقراءة فشلت", overdue_refuses_on_read_failure),
        ("is_paid بترفض ترد والقراءة فشلت", is_paid_refuses_on_read_failure),
        ("أقساط الشهر بترفض ترد والقراءة فشلت", month_installments_refuses_on_read_failure),
        ("الخريطة الفاضية الحقيقية مش عطل", genuinely_empty_map_is_not_an_error),
        ("الأقساط المدفوعة بتتحسب صح", paid_installments_are_counted),
        ("المتأخرات بتغطي أكتر من شهر (الحارس التاني)", overdue_covers_more_than_one_past_month),
        ("المتأخرات مابتشملش الشهر الحالي ولا الجاي", overdue_excludes_current_and_future),
        ("المتأخرات بتستثني المدفوع", overdue_skips_paid_ones),
        ("كل قسط متأخر شايل شهره", overdue_items_carry_their_month),
        ("المتأخرات مرتبة من الأقدم", overdue_is_sorted_oldest_first),
    ]:
        results.append(run_test(name, fn))

    restore()

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
