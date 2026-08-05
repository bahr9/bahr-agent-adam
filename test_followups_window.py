# -*- coding: utf-8 -*-
"""
Tests First -- نافذة متابعات العملاء (أوديت 2026-08-05).

الباگ: `datetime.fromisoformat("2026-08-07")` بيطلع naive، و `now_cairo()`
بيطلع aware (ZoneInfo). الطرح المباشر بينهم بيرمي:
    TypeError: can't subtract offset-naive and offset-aware datetimes
والكود كان بيبلعه بـ `except: pass` على كل سجل -- فأداة get_upcoming_followups
كانت بترد "مفيش متابعات" مهما كان عدد العملاء المستحقين، من غير أي أثر في اللوج.

الاختبارات دي بتستبدل Firestore بـ fake -- صفر شبكة وصفر كتابة على الإنتاج.
"""

from datetime import timedelta


class _FakeDoc:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def stream(self):
        return iter(self._docs)


class _FakeDB:
    """بيرد نفس المستندات لأي collection -- كفاية للاختبار ده."""

    def __init__(self, records):
        self._docs = [_FakeDoc(r) for r in records]

    def collection(self, name):
        return _FakeCollection(self._docs)


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
    import services.firebase_service as firebase_service
    from services.claude_service import _execute_tool
    from utils.time_utils import now_cairo

    today = now_cairo().date()

    def day(offset):
        return (today + timedelta(days=offset)).isoformat()

    original_db = firebase_service.firestore_db

    def followups_for(records, days=3):
        firebase_service.firestore_db = _FakeDB(records)
        try:
            return _execute_tool("get_upcoming_followups", {"days": days}, 0)
        finally:
            firebase_service.firestore_db = original_db

    results = []

    def client_due_today_is_returned():
        """الحارس الأساسي -- ده اللي كان بيفشل قبل الإصلاح."""
        out = followups_for([
            {"name": "محمد علي", "phone": "0100", "next_followup_date": day(0)},
        ])
        assert "محمد علي" in out, out
        assert "مفيش متابعات" not in out, "رجع 'مفيش' رغم وجود عميل مستحق النهارده -- " + out

    def client_inside_window_is_returned():
        out = followups_for([
            {"name": "سارة", "phone": "0101", "next_followup_date": day(2)},
        ])
        assert "سارة" in out, out

    def window_edge_is_inclusive():
        out = followups_for([
            {"name": "على الحافة", "phone": "0102", "next_followup_date": day(3)},
        ], days=3)
        assert "على الحافة" in out, out

    def client_outside_window_is_excluded():
        out = followups_for([
            {"name": "بعيد", "phone": "0103", "next_followup_date": day(9)},
        ], days=3)
        assert "بعيد" not in out and "مفيش متابعات" in out, out

    def past_date_is_excluded():
        out = followups_for([
            {"name": "فات ميعاده", "phone": "0104", "next_followup_date": day(-2)},
        ])
        assert "فات ميعاده" not in out, out

    def empty_date_is_skipped_quietly():
        """المستند الوهمي الحقيقي في الإنتاج شكله كده -- next_followup_date فاضي."""
        out = followups_for([
            {"name": "بدون تاريخ", "phone": "0105", "next_followup_date": ""},
        ])
        assert "مفيش متابعات" in out, out

    def broken_date_does_not_hide_valid_ones():
        """سجل واحد باظ ماينفعش يخفي باقي العملاء المستحقين."""
        out = followups_for([
            {"name": "تاريخ باظ", "phone": "0106", "next_followup_date": "مش تاريخ خالص"},
            {"name": "سليم", "phone": "0107", "next_followup_date": day(1)},
        ])
        assert "سليم" in out, "سجل باظ خفى عميل سليم -- " + out
        assert "تاريخ باظ" not in out, out

    def multiple_clients_all_listed():
        out = followups_for([
            {"name": "أول", "phone": "0108", "next_followup_date": day(0)},
            {"name": "تاني", "phone": "0109", "next_followup_date": day(1)},
            {"name": "تالت", "phone": "0110", "next_followup_date": day(3)},
        ], days=3)
        for name in ("أول", "تاني", "تالت"):
            assert name in out, name + " مش ظاهر -- " + out

    for name, fn in [
        ("عميل مستحق النهارده بيرجع (الحارس الأساسي)", client_due_today_is_returned),
        ("عميل جوه النافذة بيرجع", client_inside_window_is_returned),
        ("حافة النافذة داخلة", window_edge_is_inclusive),
        ("عميل بره النافذة مش بيرجع", client_outside_window_is_excluded),
        ("تاريخ فات مش بيرجع", past_date_is_excluded),
        ("تاريخ فاضي بيتخطى بهدوء", empty_date_is_skipped_quietly),
        ("تاريخ باظ مايخفيش العملاء السليمين", broken_date_does_not_hide_valid_ones),
        ("كذا عميل بيظهروا كلهم", multiple_clients_all_listed),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
