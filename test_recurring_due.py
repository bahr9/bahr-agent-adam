# -*- coding: utf-8 -*-
"""
Tests First -- استحقاق التذكيرات المتكررة (أوديت 2026-08-05).

الباگ: الشرط كان `now.minute == scheduled_minute` بالظبط، والـ job متسجل
`'interval', minutes=15`. البوت بيبدأ الساعة 10:07 مثلاً فالفحص بيحصل
:07/:22/:37/:52 للأبد -- وتذكير "يوميًا 08:00" محتاج الدقيقة تساوي 0،
يعني عمره ما كان بيضرب. وكمان التوقيت كان متكتب ثابت UTC+3 بينما مصر
UTC+2 في الشتا.

الاختبارات دي كلها على الدالة الصافية is_reminder_due -- صفر شبكة.
"""

from datetime import datetime, timedelta

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
    from services.recurring_reminders_service import is_reminder_due, DAILY_CATCHUP_MINUTES

    assert CAIRO is not None, "zoneinfo مش متاح -- الاختبار محتاجه"

    def at(year, month, day, hour, minute):
        return datetime(year, month, day, hour, minute, tzinfo=CAIRO)

    def ms(dt):
        return int(dt.timestamp() * 1000)

    def daily(hour, minute=0, last_sent=None):
        return {
            "id": "r1", "text": "اشرب مية",
            "interval_type": "daily",
            "scheduled_hour": hour, "scheduled_minute": minute,
            "last_sent": last_sent,
        }

    results = []

    # ---------- الحارس الأساسي ----------
    def fires_on_a_fifteen_minute_poll_offset():
        """ده اللي كان مستحيل قبل الإصلاح: الفحص بييجي :07 والميعاد 08:00."""
        now = at(2026, 8, 5, 8, 7)
        assert is_reminder_due(daily(8, 0), now, ms(now)) is True, \
            "تذكير 08:00 مضربش عند فحص الساعة 08:07 -- ده نفس الباگ الأصلي"

    def fires_exactly_on_time():
        now = at(2026, 8, 5, 8, 0)
        assert is_reminder_due(daily(8, 0), now, ms(now)) is True

    def does_not_fire_before_time():
        now = at(2026, 8, 5, 7, 59)
        assert is_reminder_due(daily(8, 0), now, ms(now)) is False

    # ---------- نافذة اللحاق ----------
    def catches_up_after_downtime_inside_window():
        """البوت كان واقف 08:00، رجع 09:00 -- لازم يلحق التذكير."""
        now = at(2026, 8, 5, 9, 0)
        assert is_reminder_due(daily(8, 0), now, ms(now)) is True

    def does_not_fire_long_after_the_window():
        """تذكير يومي جديد اتعمل 11:00 لميعاد 08:00 مايضربش فورًا وقت الإنشاء."""
        now = at(2026, 8, 5, 11, 0)
        assert is_reminder_due(daily(8, 0), now, ms(now)) is False

    def window_boundary_is_respected():
        target = at(2026, 8, 5, 8, 0)
        inside = target + timedelta(minutes=DAILY_CATCHUP_MINUTES - 1)
        outside = target + timedelta(minutes=DAILY_CATCHUP_MINUTES + 1)
        assert is_reminder_due(daily(8, 0), inside, ms(inside)) is True
        assert is_reminder_due(daily(8, 0), outside, ms(outside)) is False

    # ---------- مرة واحدة في اليوم ----------
    def does_not_resend_after_sending_today():
        now = at(2026, 8, 5, 8, 20)
        sent = ms(at(2026, 8, 5, 8, 1))
        assert is_reminder_due(daily(8, 0, last_sent=sent), now, ms(now)) is False

    def fires_again_the_next_day():
        now = at(2026, 8, 6, 8, 2)
        sent = ms(at(2026, 8, 5, 8, 0))
        assert is_reminder_due(daily(8, 0, last_sent=sent), now, ms(now)) is True

    def repeated_polls_send_only_once():
        """محاكاة فحص كل دقيقة -- لازم إرسال واحد بس في اليوم."""
        reminder = daily(8, 0)
        sends = 0
        for minute in range(0, 60):
            now = at(2026, 8, 5, 8, minute)
            if is_reminder_due(reminder, now, ms(now)):
                sends += 1
                reminder["last_sent"] = ms(now)
        assert sends == 1, f"اتبعت {sends} مرة بدل مرة واحدة"

    # ---------- التوقيت الصيفي ----------
    def winter_uses_utc_plus_two():
        """مصر UTC+2 في الشتا -- الكود القديم كان مثبّت +3 غصب."""
        winter = at(2026, 1, 15, 8, 5)
        assert winter.utcoffset() == timedelta(hours=2), winter.utcoffset()
        assert is_reminder_due(daily(8, 0), winter, ms(winter)) is True

    def summer_uses_utc_plus_three():
        summer = at(2026, 8, 5, 8, 5)
        assert summer.utcoffset() == timedelta(hours=3), summer.utcoffset()
        assert is_reminder_due(daily(8, 0), summer, ms(summer)) is True

    # ---------- الأنواع التانية ----------
    def hourly_respects_its_interval():
        now = at(2026, 8, 5, 12, 0)
        base = {"id": "h", "text": "x", "interval_type": "hourly", "scheduled_hour": None}
        just_sent = dict(base, last_sent=ms(now) - 59 * 60 * 1000)
        long_ago = dict(base, last_sent=ms(now) - 61 * 60 * 1000)
        assert is_reminder_due(just_sent, now, ms(now)) is False
        assert is_reminder_due(long_ago, now, ms(now)) is True

    def custom_minutes_respects_its_interval():
        now = at(2026, 8, 5, 12, 0)
        base = {"id": "c", "text": "x", "interval_type": "custom_minutes",
                "interval_value": 5, "scheduled_hour": None}
        assert is_reminder_due(dict(base, last_sent=ms(now) - 4 * 60 * 1000), now, ms(now)) is False
        assert is_reminder_due(dict(base, last_sent=ms(now) - 6 * 60 * 1000), now, ms(now)) is True

    def never_sent_interval_reminder_fires():
        now = at(2026, 8, 5, 12, 0)
        r = {"id": "n", "text": "x", "interval_type": "weekly",
             "scheduled_hour": None, "last_sent": None}
        assert is_reminder_due(r, now, ms(now)) is True

    def daily_without_scheduled_hour_uses_interval():
        now = at(2026, 8, 5, 12, 0)
        r = {"id": "d", "text": "x", "interval_type": "daily",
             "scheduled_hour": None, "last_sent": ms(now) - 23 * 60 * 60 * 1000}
        assert is_reminder_due(r, now, ms(now)) is False

    for name, fn in [
        ("بيضرب مع فحص على دقيقة :07 (الحارس الأساسي)", fires_on_a_fifteen_minute_poll_offset),
        ("بيضرب في الميعاد بالظبط", fires_exactly_on_time),
        ("مابيضربش قبل الميعاد", does_not_fire_before_time),
        ("بيلحق التذكير بعد توقف قصير", catches_up_after_downtime_inside_window),
        ("مابيضربش بعد ما تعدي نافذة اللحاق", does_not_fire_long_after_the_window),
        ("حدود نافذة اللحاق مظبوطة", window_boundary_is_respected),
        ("مابيعيدش الإرسال بعد ما بعت النهارده", does_not_resend_after_sending_today),
        ("بيضرب تاني بكرة", fires_again_the_next_day),
        ("فحص كل دقيقة = إرسال واحد بس", repeated_polls_send_only_once),
        ("الشتا UTC+2 والتذكير بيضرب صح", winter_uses_utc_plus_two),
        ("الصيف UTC+3 والتذكير بيضرب صح", summer_uses_utc_plus_three),
        ("hourly بيحترم الفاصل بتاعه", hourly_respects_its_interval),
        ("custom_minutes بيحترم الفاصل بتاعه", custom_minutes_respects_its_interval),
        ("تذكير متبعتش قبل كده بيضرب", never_sent_interval_reminder_fires),
        ("daily من غير ميعاد بيرجع لمنطق الفاصل", daily_without_scheduled_hour_uses_interval),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
