# -*- coding: utf-8 -*-
"""
Tests First -- صمود شبكي (إصلاح 2026-08-04 من لوج إنتاج حقيقي).

اللوج أثبت: كل سطر `ERROR Read timed out` مكانش وراه أي `Payload` --
يعني العطل حصل *قبل* نداء كلود، والنداء الوحيد هناك هو مؤشر "بيكتب".
يعني مؤشر تجميلي كان بيطيّر رسالة أحمد بالكامل ويرجّعله نص استثناء خام.

الاختبارات بتشتغل على تليجرام مزيّف -- صفر شبكة وصفر production.
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
    import bot as bot_module
    from bot import NETWORK_ERROR_REPLY, is_network_error, safe_reply, safe_typing

    results = []
    real_bot = bot_module.bot

    class FakeBot:
        """تليجرام مزيّف بيفشل بعدد مرات محدد."""

        def __init__(self, fail_times=0, error=None):
            self.fail_times = fail_times
            self.error = error or Exception(
                "HTTPSConnectionPool(host='api.telegram.org', port=443): "
                "Read timed out. (read timeout=30)"
            )
            self.sent = []
            self.calls = 0

        def _maybe_fail(self):
            self.calls += 1
            if self.calls <= self.fail_times:
                raise self.error

        def send_chat_action(self, chat_id, action):
            self._maybe_fail()

        def reply_to(self, message, text, **kwargs):
            self._maybe_fail()
            self.sent.append(text)

    def _with_fake(fake, fn):
        bot_module.bot = fake
        try:
            return fn()
        finally:
            bot_module.bot = real_bot

    # ---------- تصنيف الأعطال ----------

    def network_errors_are_recognized():
        assert is_network_error(
            "HTTPSConnectionPool(host='api.telegram.org', port=443): "
            "Read timed out. (read timeout=30)"
        )
        assert is_network_error("Connection aborted")
        assert not is_network_error("KeyError: 'project_id'"), (
            "الأخطاء الحقيقية متتصنفش شبكة عشان ما نخفيهاش"
        )

    # ---------- مؤشر الكتابة ----------

    def typing_failure_never_raises():
        fake = FakeBot(fail_times=99)
        _with_fake(fake, lambda: safe_typing(123))  # المفروض ميرميش استثناء
        assert fake.calls == 1

    # ---------- الرد ----------

    def reply_retries_then_succeeds():
        fake = FakeBot(fail_times=1)
        ok = _with_fake(fake, lambda: safe_reply(object(), "الرد الحقيقي", max_retries=2))
        assert ok is True and fake.sent == ["الرد الحقيقي"], (ok, fake.sent)

    def reply_gives_up_honestly():
        fake = FakeBot(fail_times=99)
        ok = _with_fake(fake, lambda: safe_reply(object(), "رد", max_retries=2))
        assert ok is False and fake.sent == []

    # ---------- رسالة الخطأ لأحمد ----------

    def raw_network_text_never_reaches_ahmed():
        fake = FakeBot()
        _with_fake(fake, lambda: bot_module.send_error_message(
            object(),
            "HTTPSConnectionPool(host='api.telegram.org', port=443): Read timed out. (read timeout=30)",
        ))
        assert fake.sent == [NETWORK_ERROR_REPLY], fake.sent
        assert "HTTPSConnectionPool" not in fake.sent[0]

    def real_errors_stay_visible():
        fake = FakeBot()
        _with_fake(fake, lambda: bot_module.send_error_message(object(), "KeyError: 'project_id'"))
        assert "KeyError" in fake.sent[0], fake.sent

    # ---------- الضبط والتوصيل ----------

    def timeouts_are_widened():
        from telebot import apihelper
        assert apihelper.READ_TIMEOUT >= 60, apihelper.READ_TIMEOUT
        assert apihelper.SESSION_TIME_TO_LIVE <= 120, apihelper.SESSION_TIME_TO_LIVE

    def no_bare_typing_calls_remain():
        import glob
        for path in ["main.py"] + glob.glob("handlers/*.py"):
            src = open(path, encoding="utf-8").read()
            assert "bot.send_chat_action" not in src, (
                path + ": لسه بينادي مؤشر الكتابة مباشرة -- ممكن يطيّر الرسالة"
            )

    for name, fn in [
        ("تصنيف أعطال الشبكة صح", network_errors_are_recognized),
        ("فشل مؤشر الكتابة مبيوقعش المعالج", typing_failure_never_raises),
        ("الرد بيعيد المحاولة وينجح", reply_retries_then_succeeds),
        ("الفشل النهائي بيتقال بصراحة", reply_gives_up_honestly),
        ("نص العطل الخام مبيوصلش لأحمد", raw_network_text_never_reaches_ahmed),
        ("الأخطاء الحقيقية بتفضل ظاهرة", real_errors_stay_visible),
        ("المهلات اتوسّعت", timeouts_are_widened),
        ("مفيش نداء مؤشر مكشوف في المعالجات", no_bare_typing_calls_remain),
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
