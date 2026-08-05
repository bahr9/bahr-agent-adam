# -*- coding: utf-8 -*-
"""
Tests First -- تقطيع الرسايل عند حد تليجرام (أوديت 2026-08-05).

الباگ: مفيش أي منطق تقسيم في المشروع كله. تقرير DXF فيه 100+ قياس أو رد
طويل من كلود بيعدّي 4096 حرف -> ApiTelegramException -> المعالج بيمسكه
ويقول "الملف متشفر أو تالف" وهو سليم، أو الرد بيضيع خالص.

الاختبارات على الدالة الصافية split_message + غلاف الإرسال -- بلا شبكة.
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
    from bot import split_message, _with_auto_split, TELEGRAM_MAX_MESSAGE

    LIMIT = TELEGRAM_MAX_MESSAGE
    results = []

    def short_text_stays_one_piece():
        assert split_message("سلام") == ["سلام"]

    def empty_text_gives_nothing():
        assert split_message("") == []
        assert split_message(None) == []

    def exactly_at_the_limit_is_not_split():
        text = "أ" * LIMIT
        assert len(split_message(text)) == 1

    def one_over_the_limit_is_split():
        text = "أ" * (LIMIT + 1)
        assert len(split_message(text)) == 2

    def no_chunk_exceeds_the_limit():
        """الشرط اللي لو اتكسر تليجرام هيرفض -- أهم اختبار هنا."""
        text = ("سطر تقرير فيه قياسات ومقاسات وتفاصيل كتير. " * 400)
        for chunk in split_message(text):
            assert len(chunk) <= LIMIT, f"قطعة طولها {len(chunk)} -- فوق الحد"

    def nothing_is_lost_when_splitting():
        text = "\n".join(f"سطر رقم {i} في التقرير" for i in range(600))
        joined = "".join(split_message(text))
        stripped_original = "".join(text.split())
        stripped_joined = "".join(joined.split())
        assert stripped_joined == stripped_original, "ضاع أو اتكرر نص أثناء التقسيم"

    def prefers_paragraph_breaks():
        para = "فقرة كاملة فيها كلام. " * 150      # ~3000 حرف
        text = para + "\n\n" + para
        chunks = split_message(text)
        assert len(chunks) == 2, f"المفروض جزئين، طلعوا {len(chunks)}"
        assert chunks[0].endswith("."), "القطع محصلش عند نهاية الفقرة"

    def falls_back_to_hard_cut_when_no_separator():
        """نص متصل من غير أي مسافة -- لازم يتقطع خام مش يفضل أطول من الحد."""
        text = "ا" * (LIMIT * 2 + 50)
        chunks = split_message(text)
        assert all(len(c) <= LIMIT for c in chunks)
        assert len(chunks) == 3, len(chunks)

    def very_long_text_splits_into_many():
        text = "كلمة " * 5000                       # ~25000 حرف
        chunks = split_message(text)
        assert len(chunks) >= 6, len(chunks)
        assert all(len(c) <= LIMIT for c in chunks)

    # ---------- غلاف الإرسال ----------
    def wrapper_sends_short_text_once():
        sent = []
        wrapped = _with_auto_split(lambda target, text, **kw: sent.append(text))
        wrapped(123, "رد قصير")
        assert sent == ["رد قصير"], sent

    def wrapper_sends_long_text_in_pieces():
        sent = []
        wrapped = _with_auto_split(lambda target, text, **kw: sent.append(text))
        wrapped(123, "تقرير طويل. " * 1000)
        assert len(sent) > 1, "مقسمش الرسالة الطويلة"
        assert all(len(piece) <= LIMIT for piece in sent)

    def wrapper_passes_kwargs_through():
        seen = []
        wrapped = _with_auto_split(lambda target, text, **kw: seen.append(kw))
        wrapped(123, "نص " * 3000, parse_mode="Markdown")
        assert all(kw.get("parse_mode") == "Markdown" for kw in seen), seen
        assert len(seen) > 1

    def wrapper_keeps_target_for_every_piece():
        targets = []
        wrapped = _with_auto_split(lambda target, text, **kw: targets.append(target))
        wrapped("CHAT-9", "نص " * 3000)
        assert set(targets) == {"CHAT-9"}, targets

    for name, fn in [
        ("النص القصير بيفضل قطعة واحدة", short_text_stays_one_piece),
        ("النص الفاضي مابيرجعش حاجة", empty_text_gives_nothing),
        ("عند الحد بالظبط مابيتقسمش", exactly_at_the_limit_is_not_split),
        ("حرف واحد فوق الحد بيتقسم", one_over_the_limit_is_split),
        ("ولا قطعة بتعدي الحد (الحارس الأساسي)", no_chunk_exceeds_the_limit),
        ("مفيش نص بيضيع في التقسيم", nothing_is_lost_when_splitting),
        ("بيفضّل القطع عند الفقرات", prefers_paragraph_breaks),
        ("نص متصل بيتقطع خام", falls_back_to_hard_cut_when_no_separator),
        ("النص الضخم بيتقسم لأجزاء كتير", very_long_text_splits_into_many),
        ("الغلاف بيبعت القصير مرة واحدة", wrapper_sends_short_text_once),
        ("الغلاف بيبعت الطويل على أجزاء", wrapper_sends_long_text_in_pieces),
        ("الغلاف بيمرّر الـ kwargs لكل جزء", wrapper_passes_kwargs_through),
        ("الغلاف بيبعت كل الأجزاء لنفس الوجهة", wrapper_keeps_target_for_every_piece),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
