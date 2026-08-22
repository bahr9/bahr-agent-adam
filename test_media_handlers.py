# -*- coding: utf-8 -*-
"""
حارس معالجي الصور والصوت (أوديت 2026-08-17).

الأوديت قاس التغطية: `handlers/photo_handler.py` و`handlers/voice_handler.py`
عند **صفر بالمية**. والخدمات تحتهم مغطّاة 88-100%.

الفرق مهم: الخدمات "ورا الكواليس"، والـhandlers هي الطبقة اللي إيد أحمد
بتلمسها -- يبعت صورة، يبعت صوت، يكتب أمر. كل عطل وصله في اليوم اللي فات
كان في الطبقة دي أو في اللي بيوصلها، مش في الخدمات.

اللي بيتحرس هنا سلوك، مش تفاصيل تنفيذ:

  * نوع الصورة بيتحدد صح من الامتداد. الغلط هنا بيخلي Claude يرفض الصورة
    أو يقراها غلط، والرسالة اللي بتوصل أحمد "حصلت مشكلة" من غير سبب.
  * أعلى جودة بتتاخد (`photo[-1]`). لو بقت `[0]` أحمد هيبعت صورة واضحة
    ويتحلّل أصغر نسخة منها، **والرد هيفضل يبان طبيعي** -- عطل صامت.
  * الفولباك عند فشل قرار التخزين بيحفظ مش بيرمي. "أحسن تتحفظ من تتفوت"
    مكتوبة في الكود كقرار، ومحدش كان بيحرسها.
  * الصوت بيرد رسالة واضحة لما OpenAI مش متاح أو التفريغ فشل، **ومبيكملش**
    بنص فاضي لآدم.
  * الملف المؤقت بتاع الصوت بيتمسح.

صفر شبكة، صفر موديل، صفر Firestore -- كل الاعتماديات بتتحقن.
"""

import sys
import types


class _Msg:
    """رسالة تليجرام مزوّرة -- الحد الأدنى اللي الـhandlers بتقراه."""

    def __init__(self, caption=None, chat_id=777, message_id=1, kind="photo"):
        self.chat = types.SimpleNamespace(id=chat_id)
        self.from_user = types.SimpleNamespace(id=chat_id, first_name="Ahmed")
        self.caption = caption
        self.message_id = message_id
        self.text = None
        if kind == "photo":
            # تليجرام بيبعت كل المقاسات مرتبة تصاعديًا -- الأخير هو الأوضح
            self.photo = [
                types.SimpleNamespace(file_id="small"),
                types.SimpleNamespace(file_id="medium"),
                types.SimpleNamespace(file_id="largest"),
            ]
        else:
            self.voice = types.SimpleNamespace(file_id="voice-1")


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


def _patch(obj, **kw):
    """يرقّع سمات ويرجّع دالة إرجاع."""
    old = {k: getattr(obj, k) for k in kw}
    for k, v in kw.items():
        setattr(obj, k, v)
    return lambda: [setattr(obj, k, v) for k, v in old.items()]


def main():
    import bot as bot_module
    import handlers.photo_handler as ph
    import handlers.voice_handler as vh

    results = []

    # ============================================================
    # الصور
    # ============================================================

    def _run_photo(file_path, caption=None, vision=None, store=None):
        """بينفّذ المعالج بكل الاعتماديات مزوّرة. بيرجع اللي اتسجّل."""
        seen = {"vision": None, "replies": [], "saved": [], "errors": []}

        def fake_get_file(file_id):
            seen["file_id"] = file_id
            return types.SimpleNamespace(file_path=file_path)

        def fake_vision(image_base64, cap, media_type="image/jpeg", memory_summary=None):
            seen["vision"] = {"b64": image_base64, "caption": cap,
                              "media_type": media_type, "memory": memory_summary}
            if vision is not None:
                return vision
            return "تحليل الصورة"

        undo = [
            _patch(ph.bot, get_file=fake_get_file,
                   download_file=lambda p: b"\x89PNG-bytes",
                   reply_to=lambda m, t: seen["replies"].append(t)),
            _patch(ph, analyze_with_vision=fake_vision,
                   save_conversation=lambda c, u, a: seen["saved"].append((u, a)),
                   get_memory=lambda c: "ملخص",
                   update_memory=lambda c, u, a: seen.setdefault("mem", []).append(u),
                   set_chat_id=lambda c: None,
                   safe_typing=lambda c: None,
                   send_error_message=lambda m, t: seen["errors"].append(t)),
        ]
        cs = sys.modules["services.claude_service"]
        undo.append(_patch(cs, should_store_in_memory=(
            store if store is not None else (lambda u, a: True))))
        try:
            ph.handle_photo_message(_Msg(caption=caption))
        finally:
            for u in undo:
                u()
        return seen

    def png_is_sent_as_png():
        seen = _run_photo("photos/file_1.PNG")
        assert seen["vision"]["media_type"] == "image/png", seen["vision"]["media_type"]

    def webp_is_sent_as_webp():
        seen = _run_photo("photos/file_2.webp")
        assert seen["vision"]["media_type"] == "image/webp", seen["vision"]["media_type"]

    def anything_else_is_jpeg():
        for path in ("photos/a.jpg", "photos/b.jpeg", "photos/c"):
            seen = _run_photo(path)
            assert seen["vision"]["media_type"] == "image/jpeg", (path, seen["vision"])

    def the_highest_quality_photo_is_used():
        """عطل صامت لو اتكسر: الرد بيفضل يبان طبيعي والصورة أصغر نسخة."""
        seen = _run_photo("photos/x.jpg")
        assert seen["file_id"] == "largest", (
            "اتاخدت نسخة مش الأوضح: " + str(seen["file_id"])
        )

    def a_missing_caption_gets_a_real_prompt():
        seen = _run_photo("photos/x.jpg", caption=None)
        cap = seen["vision"]["caption"]
        assert cap and len(cap) > 20, "بعت caption فاضي للموديل: " + repr(cap)
        seen2 = _run_photo("photos/x.jpg", caption="إيه رأيك")
        assert seen2["vision"]["caption"] == "إيه رأيك", seen2["vision"]["caption"]

    def the_exchange_is_saved_with_a_photo_marker():
        seen = _run_photo("photos/x.jpg", caption="المطبخ")
        assert seen["saved"], "التبادل ماتحفظش"
        user_text, reply = seen["saved"][0]
        assert user_text.startswith("[صورة]"), user_text
        assert "المطبخ" in user_text, user_text
        assert reply == "تحليل الصورة", reply

    def a_failing_store_decision_still_saves():
        """قرار مكتوب في الكود: 'أحسن تتحفظ من تتفوت'. محدش كان بيحرسه."""
        def boom(u, a):
            raise RuntimeError("قرار التخزين وقع")
        seen = _run_photo("photos/x.jpg", store=boom)
        assert seen.get("mem"), "الفولباك ضيّع التبادل بدل ما يحفظه"

    def a_declined_store_decision_does_not_save():
        seen = _run_photo("photos/x.jpg", store=lambda u, a: False)
        assert not seen.get("mem"), "حفظ رغم إن القرار كان لأ"

    def a_vision_failure_reaches_ahmed_as_a_message():
        seen = {"errors": []}

        def boom(*a, **k):
            raise RuntimeError("Vision وقع")
        undo = [
            _patch(ph.bot, get_file=lambda f: types.SimpleNamespace(file_path="x.jpg"),
                   download_file=lambda p: b"bytes",
                   reply_to=lambda m, t: None),
            _patch(ph, analyze_with_vision=boom, get_memory=lambda c: "",
                   set_chat_id=lambda c: None, safe_typing=lambda c: None,
                   send_error_message=lambda m, t: seen["errors"].append(t)),
        ]
        try:
            ph.handle_photo_message(_Msg())      # ممنوع يرمي لبرة
        finally:
            for u in undo:
                u()
        assert seen["errors"], "الفشل ما وصلش أحمد -- الرسالة اختفت"
        assert "جرب تاني" in seen["errors"][0], seen["errors"][0]

    # ============================================================
    # الصوت
    # ============================================================

    def _run_voice(available=True, transcript="اكتبلي تذكير", agentic=None):
        seen = {"replies": [], "asked": [], "tmp": []}
        import os as _os

        def fake_open_write(path, mode="rb"):
            seen["tmp"].append(path)
            return open(path, mode)

        undo = [
            _patch(vh.bot, get_file=lambda f: types.SimpleNamespace(file_path="v.ogg"),
                   download_file=lambda p: b"ogg-bytes",
                   reply_to=lambda m, t: seen["replies"].append(t)),
            _patch(vh, is_openai_available=lambda: available,
                   transcribe_audio=lambda p, language="ar": (
                       seen.setdefault("transcribed", []).append(p) or transcript),
                   set_chat_id=lambda c: None, safe_typing=lambda c: None,
                   get_memory=lambda c: "", get_conversation_history=lambda c, limit=0: [],
                   format_history_for_claude=lambda h: [],
                   ask_claude_agentic=(agentic or (lambda t, c, **k: (
                       seen["asked"].append(t) or "رد آدم"))),
                   send_error_message=lambda m, t: seen.setdefault("errors", []).append(t)),
        ]
        try:
            vh.handle_voice_message(_Msg(kind="voice"))
        finally:
            for u in undo:
                u()
        return seen

    def openai_unavailable_says_so_and_stops():
        seen = _run_voice(available=False)
        assert seen["replies"], "سكت خالص"
        assert "مش مفعّلة" in seen["replies"][0], seen["replies"][0]
        assert not seen["asked"], "كمّل لآدم رغم إن التفريغ مش متاح"

    def an_empty_transcript_stops_instead_of_asking_with_nothing():
        """أخطر حالة: نص فاضي بيتبعت لآدم فيرد على لا حاجة."""
        for empty in ("", None):
            seen = _run_voice(transcript=empty)
            assert not seen["asked"], "بعت نص فاضي لآدم: " + repr(empty)
            assert seen["replies"] and "ما قدرتش أفهم" in seen["replies"][0], seen["replies"]

    def a_good_transcript_reaches_adam_verbatim():
        seen = _run_voice(transcript="فكرني بالاجتماع بكرة")
        assert seen["asked"] == ["فكرني بالاجتماع بكرة"], seen["asked"]

    def the_temp_voice_file_is_removed():
        import os
        seen = _run_voice(transcript="تمام")
        path = (seen.get("transcribed") or [None])[0]
        assert path, "ماحفظش ملف مؤقت أصلاً"
        assert not os.path.exists(path), "الملف المؤقت فضل موجود: " + str(path)

    for name, fn in [
        ("PNG بيتبعت PNG", png_is_sent_as_png),
        ("WEBP بيتبعت WEBP", webp_is_sent_as_webp),
        ("أي حاجة تانية JPEG", anything_else_is_jpeg),
        ("أعلى جودة هي المستخدمة", the_highest_quality_photo_is_used),
        ("صورة بلا تعليق بتاخد نص حقيقي", a_missing_caption_gets_a_real_prompt),
        ("التبادل بيتحفظ بعلامة [صورة]", the_exchange_is_saved_with_a_photo_marker),
        ("فشل قرار التخزين بيحفظ برضه", a_failing_store_decision_still_saves),
        ("رفض التخزين مبيحفظش", a_declined_store_decision_does_not_save),
        ("فشل التحليل بيوصل أحمد", a_vision_failure_reaches_ahmed_as_a_message),
        ("OpenAI مش متاح: رسالة ووقوف", openai_unavailable_says_so_and_stops),
        ("تفريغ فاضي مبيكملش لآدم", an_empty_transcript_stops_instead_of_asking_with_nothing),
        ("التفريغ بيوصل آدم بالحرف", a_good_transcript_reaches_adam_verbatim),
        ("الملف المؤقت بيتمسح", the_temp_voice_file_is_removed),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
