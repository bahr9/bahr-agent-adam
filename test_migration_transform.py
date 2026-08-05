# -*- coding: utf-8 -*-
"""
Tests First -- دوال تحويل الهجرة (Firestore -> Postgres).

كل دالة صافية، فالاختبارات دي صفر شبكة وصفر قاعدة بيانات.

المبدأ اللي بيتحرس هنا: **الغموض بيوقف الاستيراد مابيتحلش بتخمين.**
أغلب الاختبارات دي بتتأكد إن القيمة الملتبسة **بترمي** -- مش إنها بتتحول
لـ NULL بهدوء. قيمة سعر ضايعة بصمت في عمود مالي أسوأ بكتير من استيراد
بيقف ويسأل.
"""

from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    CAIRO = ZoneInfo("Africa/Cairo")
except Exception:
    CAIRO = None


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
    from migration_transform import (
        TransformError, to_timestamptz, correct_server_naive_time,
        extract_deadline, to_numeric, split_gps, blank_to_none,
        rename_arabic_fields, assign_positions,
    )

    def raises(fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except TransformError:
            return True
        return False

    results = []

    # ---------- الوقت: الخمس صيغ ----------
    def all_five_shapes_land_on_the_same_instant():
        """نفس اللحظة بخمس صيغ -- لازم تدي نفس النتيجة."""
        target = datetime(2026, 8, 5, 14, 23, 11, tzinfo=CAIRO)
        epoch_ms = int(target.timestamp() * 1000)

        shapes = {
            "epoch رقم":     epoch_ms,
            "epoch كنص":     str(epoch_ms),
            "ISO بـ T":      target.isoformat(),
            "ISO بمسافة":    str(target),
        }
        for label, value in shapes.items():
            got = to_timestamptz(value, label)
            assert abs((got - target).total_seconds()) < 1, f"{label}: {got} != {target}"

    def naive_string_uses_the_assumed_zone():
        got = to_timestamptz("2026-08-05 14:23", assume_tz=CAIRO)
        assert got.utcoffset().total_seconds() == 3 * 3600, got.utcoffset()

    def empty_time_is_none_not_an_error():
        assert to_timestamptz(None) is None
        assert to_timestamptz("") is None
        assert to_timestamptz("   ") is None

    def unreadable_time_stops_the_import():
        assert raises(to_timestamptz, "مش وقت خالص")
        assert raises(to_timestamptz, True)
        assert raises(to_timestamptz, ["list"])

    def seconds_mistaken_for_millis_is_caught():
        """أشهر غلطة في الهجرات -- لازم ترمي مش تعدي."""
        seconds_not_ms = 1785490887          # ثواني، لو اتقسمت على 1000 تدي 1970
        assert raises(to_timestamptz, seconds_not_ms, "created_at")

    def millis_mistaken_for_micros_is_caught():
        micros = 1785490887553000            # لو اتعاملت كميلي تدي سنة بعيدة جدًا
        assert raises(to_timestamptz, micros, "created_at")

    def a_plausible_epoch_passes():
        got = to_timestamptz(1785490887553, "created_at")
        assert got.year == 2026, got

    # ---------- انحراف توقيت السيرفر ----------
    def server_naive_time_is_read_as_utc_not_cairo():
        """expenses.date اتكتب بـ datetime.now() على حاوية UTC."""
        as_utc = correct_server_naive_time("2026-08-05 22:30", "expenses.date")
        assert as_utc.utcoffset().total_seconds() == 0, as_utc.utcoffset()
        # نفس اللحظة بتوقيت القاهرة = بعدها بـ 3 ساعات في الصيف
        in_cairo = as_utc.astimezone(CAIRO)
        assert in_cairo.hour == 1 and in_cairo.day == 6, in_cairo

    def the_offset_is_not_hardcoded():
        """شتاءً الفرق ساعتين مش تلاتة -- الإزاحة مابتتحسبش يدوي."""
        winter = correct_server_naive_time("2026-01-15 22:30").astimezone(CAIRO)
        summer = correct_server_naive_time("2026-08-15 22:30").astimezone(CAIRO)
        assert winter.hour == 0, winter      # +2
        assert summer.hour == 1, summer      # +3

    # ---------- الموعد المدفون في النص ----------
    def deadline_is_pulled_out_of_the_text():
        text, deadline = extract_deadline("تسليم مشروع البحر [Deadline: 2026-09-15]")
        assert text == "تسليم مشروع البحر", repr(text)
        assert deadline.isoformat() == "2026-09-15", deadline

    def text_without_a_deadline_is_untouched():
        text, deadline = extract_deadline("ملاحظة عادية")
        assert text == "ملاحظة عادية" and deadline is None

    def a_broken_deadline_stops_the_import():
        assert raises(extract_deadline, "حاجة [Deadline: 2026-13-45]")

    def empty_note_is_safe():
        assert extract_deadline("") == ("", None)
        assert extract_deadline(None) == (None, None)

    # ---------- الأرقام المتخزنة كنصوص ----------
    def price_strings_become_numbers():
        assert to_numeric("1500") == 1500.0
        assert to_numeric("1,500.50") == 1500.5
        assert to_numeric(" 250 ") == 250.0
        assert to_numeric(3000) == 3000.0

    def arabic_digits_are_handled():
        assert to_numeric("١٥٠٠") == 1500.0

    def currency_suffix_is_stripped():
        assert to_numeric("1500 جنيه") == 1500.0
        assert to_numeric("1500 EGP") == 1500.0

    def an_unparseable_price_stops_the_import():
        """الحارس الأساسي: ممنوع سعر يضيع بصمت."""
        assert raises(to_numeric, "حسب المقاس", "price")
        assert raises(to_numeric, "", "price")
        assert raises(to_numeric, None, "price")

    def empty_is_allowed_only_when_asked():
        assert to_numeric("", allow_empty=True) is None
        assert to_numeric(None, allow_empty=True) is None

    # ---------- الإحداثيات ----------
    def gps_string_splits_into_two_numbers():
        lat, lng = split_gps("30.123456, 31.234567")
        assert (lat, lng) == (30.123456, 31.234567)

    def empty_gps_is_none():
        assert split_gps("") == (None, None)
        assert split_gps(None) == (None, None)

    def malformed_gps_stops_the_import():
        assert raises(split_gps, "30.12")                  # جزء واحد
        assert raises(split_gps, "مش أرقام, خالص")
        assert raises(split_gps, "999, 31.2")              # خارج المدى

    # ---------- الفراغ ----------
    def blank_becomes_none():
        assert blank_to_none("") is None
        assert blank_to_none("   ") is None
        assert blank_to_none(None) is None
        assert blank_to_none("قيمة") == "قيمة"
        assert blank_to_none(0) == 0        # صفر مش فراغ

    # ---------- الأسماء العربية ----------
    def arabic_keys_are_renamed():
        got = rename_arabic_fields({"نص": "اشتري لبن", "تم": False, "created_at": 1})
        assert got == {"text": "اشتري لبن", "done": False, "created_at": 1}, got

    # ---------- الترتيب والتبعية ----------
    def positions_capture_the_parent_child_relation():
        """التبعية معتمدة على الترتيب بالكامل -- مفيش مفتاح بيربطهم."""
        items = [
            {"desc": "أعمال الكهرباء", "sub": False},
            {"desc": "  تأسيس",        "sub": True},
            {"desc": "  تشطيب",        "sub": True},
            {"desc": "أعمال السباكة",  "sub": False},
            {"desc": "  مواسير",       "sub": True},
        ]
        rows = assign_positions(items)
        assert [r["position"] for r in rows] == [0, 1, 2, 3, 4]
        assert [r["parent_position"] for r in rows] == [None, 0, 0, None, 3]

    def a_leading_sub_item_has_no_parent():
        """حالة حدّية: فرعي من غير أب قبله."""
        rows = assign_positions([{"desc": "يتيم", "sub": True}])
        assert rows[0]["parent_position"] is None

    def empty_item_list_is_safe():
        assert assign_positions([]) == []
        assert assign_positions(None) == []

    for name, fn in [
        ("الخمس صيغ بتدي نفس اللحظة", all_five_shapes_land_on_the_same_instant),
        ("النص بلا إزاحة بياخد المنطقة المفترضة", naive_string_uses_the_assumed_zone),
        ("الوقت الفاضي = None مش خطأ", empty_time_is_none_not_an_error),
        ("وقت مش مقروء بيوقف الاستيراد", unreadable_time_stops_the_import),
        ("ثواني متحسوبة كميلي بتتمسك (الحارس الأساسي)", seconds_mistaken_for_millis_is_caught),
        ("ميكرو متحسوبة كميلي بتتمسك", millis_mistaken_for_micros_is_caught),
        ("epoch معقول بيعدّي", a_plausible_epoch_passes),
        ("وقت السيرفر بيتقرا UTC مش القاهرة", server_naive_time_is_read_as_utc_not_cairo),
        ("الإزاحة مش مكتوبة يدوي (شتا/صيف)", the_offset_is_not_hardcoded),
        ("الموعد بيتطلع من جوه النص", deadline_is_pulled_out_of_the_text),
        ("نص بلا موعد مابيتلمسش", text_without_a_deadline_is_untouched),
        ("موعد باظ بيوقف الاستيراد", a_broken_deadline_stops_the_import),
        ("ملاحظة فاضية آمنة", empty_note_is_safe),
        ("أسعار نصية بتبقى أرقام", price_strings_become_numbers),
        ("الأرقام العربية بتتقرا", arabic_digits_are_handled),
        ("لاحقة العملة بتتشال", currency_suffix_is_stripped),
        ("سعر مش مفهوم بيوقف الاستيراد (الحارس الأساسي)", an_unparseable_price_stops_the_import),
        ("الفراغ مسموح بس لما نطلبه", empty_is_allowed_only_when_asked),
        ("الإحداثيات بتتقسم لرقمين", gps_string_splits_into_two_numbers),
        ("إحداثيات فاضية = None", empty_gps_is_none),
        ("إحداثيات باظت بتوقف الاستيراد", malformed_gps_stops_the_import),
        ("الفراغ بيبقى NULL", blank_becomes_none),
        ("المفاتيح العربية بتتسمّى إنجليزي", arabic_keys_are_renamed),
        ("الترتيب بيحفظ علاقة الأب بالفرعي", positions_capture_the_parent_child_relation),
        ("فرعي من غير أب مالوش parent", a_leading_sub_item_has_no_parent),
        ("ليستة عناصر فاضية آمنة", empty_item_list_is_safe),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
