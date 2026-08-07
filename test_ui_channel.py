# -*- coding: utf-8 -*-
"""
اختبارات قناة adam-ui (CONTRACT_V1) -- services/ui_channel.py

بتشتغل على Flask test client محليًا -- صفر شبكة وصفر production:
  - الـ runtime مزيف بالكامل (مفيش Claude ولا EB حقيقي)
  - قراءة الأقساط للبطاقة مستبدلة بدالة مزيفة (مفيش Firestore/Supabase)
  - مفيش استيراد لـ main.py خالص (القناة blueprint مستقل بالتصميم)

اللي بيتثبت هنا هو نص العقد المجمّد (contract-v1-freeze):
  - الأمان: ADAM_TOKEN غايب = 503 fail-closed، توكن غلط/غايب = 401 بدون تفاصيل
  - تسلسل الجولة: thinking -> executing -> tool.* -> stage.push (قبل البث)
    -> stream.start/delta*/end -> warning|success -> turn.completed
  - deltas متجمعة = النص الأصلي حرفيًا
  - قاعدة الاستبدال: القديمة تتقفل بـ turn.completed وممنوع أي حدث
    بالـ turnId القديم بعد الإغلاق
  - cancel الصريح = turn.failed
  - الخطافات no-op تام خارج جولة UI (حماية مسار تليجرام)
"""
import json
import os
import queue
import threading
import time

os.environ.setdefault("SKIP_BOT_POLLING", "1")

from flask import Flask

from services import ui_channel

TOKEN = "test-token-ui-channel"
AUTH = {"Authorization": "Bearer " + TOKEN}

# runtime مزيف قابل للتبديل بين الاختبارات
RUNTIME = {"fn": None}

FAKE_INSTALLMENTS_OVERDUE = {
    "month_key": "01/08/2026",
    "items": [
        {"program": "فاليو", "program_id": "valu", "index": 3, "amount": 5000, "paid": False},
        {"program": "سهولة", "program_id": "souhoola", "index": 2, "amount": 3000, "paid": True},
    ],
    "total": 8000,
    "overdue": [
        {"program": "فاليو", "program_id": "valu", "index": 2, "amount": 5000, "date": "01/07/2026", "paid": False},
    ],
    "overdue_total": 5000,
    "earliest_overdue_month": "01/07/2026",
}

FAKE_INSTALLMENTS_CLEAN = {
    "month_key": "01/08/2026",
    "items": [
        {"program": "فاليو", "program_id": "valu", "index": 3, "amount": 5000, "paid": True},
    ],
    "total": 5000,
    "overdue": [],
    "overdue_total": 0,
    "earliest_overdue_month": "01/07/2026",
}


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


def wait_for(q, event_type, turn_id=None, timeout=10, collected=None):
    """بيسحب من الـ queue لحد ما يلاقي الحدث المطلوب. بيرجع الحدث."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            event = q.get(timeout=max(0.05, deadline - time.time()))
        except queue.Empty:
            break
        if collected is not None:
            collected.append(event)
        if event.get("type") == event_type and (turn_id is None or event.get("turnId") == turn_id):
            return event
    raise AssertionError(f"مستنيش حدث {event_type} (turnId={turn_id}) في {timeout} ثانية")


def drain(q, seconds=0.3):
    """يلم كل الأحداث المتاحة خلال فترة قصيرة."""
    events = []
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            events.append(q.get(timeout=0.05))
        except queue.Empty:
            pass
    return events


def main():
    app = Flask(__name__)
    ui_channel.STREAM_DELAY_SECONDS = 0  # مفيش نوم في الاختبارات
    ui_channel.register_ui_channel(
        app,
        runtime_call=lambda text, chat_id: RUNTIME["fn"](text, chat_id),
        chat_id_getter=lambda: 12345,
    )
    client = app.test_client()
    results = []

    # ============================================================
    # 1) الأمان
    # ============================================================

    def missing_secret_refuses_with_503():
        old = os.environ.pop("ADAM_TOKEN", None)
        try:
            assert client.get("/ui/events").status_code == 503, "SSE من غير سر لازم 503"
            r = client.post("/ui/command", json={"type": "text", "text": "x"})
            assert r.status_code == 503, f"command رد {r.status_code} بدل 503 والسر غايب"
        finally:
            if old is not None:
                os.environ["ADAM_TOKEN"] = old

    def wrong_or_missing_token_is_401_without_details():
        os.environ["ADAM_TOKEN"] = TOKEN
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic abc"}):
            r = client.post("/ui/command", headers=headers, json={"type": "text", "text": "x"})
            assert r.status_code == 401, f"headers={headers} رد {r.status_code} بدل 401"
            body = r.get_json() or {}
            assert body == {"status": "unauthorized"}, f"401 لازم يكون بدون تفاصيل، جه: {body}"
            r2 = client.get("/ui/events", headers=headers)
            assert r2.status_code == 401, f"SSE headers={headers} رد {r2.status_code} بدل 401"

    def invalid_commands_are_400():
        os.environ["ADAM_TOKEN"] = TOKEN
        cases = [
            {"type": "voice", "action": "start"},   # محجوز -- لا يُرسل في V1
            {"type": "text", "text": "   "},        # text فاضي
            {"type": "something-else"},             # نوع مش معروف
            {},                                     # مفيش type
        ]
        for body in cases:
            r = client.post("/ui/command", headers=AUTH, json=body)
            assert r.status_code == 400, f"{body} رد {r.status_code} بدل 400"

    # ============================================================
    # 2) الجولة الكاملة -- سيناريو سؤال الأقساط
    # ============================================================

    REPLY = "عندك 7 أقساط الشهر ده، منهم قسط فاليو متأخر من الشهر اللي فات -- ده الأولوية."

    def full_installments_turn_sequence():
        os.environ["ADAM_TOKEN"] = TOKEN
        ui_channel._read_installments = lambda: FAKE_INSTALLMENTS_OVERDUE

        def fake_runtime(text, chat_id):
            # محاكاة بالظبط للي claude_service بيعمله في لوب الأدوات
            call_id = ui_channel.on_tool_started("loan_month_installments")
            ui_channel.on_tool_finished(call_id, "loan_month_installments", "أقساط 01/08/2026 (الإجمالي: 8000 جنيه)")
            return REPLY

        RUNTIME["fn"] = fake_runtime
        q = ui_channel.subscribe()
        try:
            r = client.post("/ui/command", headers=AUTH,
                            json={"type": "text", "text": "راجع الأقساط المتأخرة"})
            assert r.status_code == 202, f"command رد {r.status_code} بدل 202"
            turn_id = (r.get_json() or {}).get("turnId")
            assert turn_id, "الرد لازم يحمل turnId"

            events = []
            wait_for(q, "turn.completed", turn_id, collected=events)

            types = [e["type"] for e in events]

            # كل أحداث الجولة بنفس الـ turnId (اللي بيحمل turnId أصلًا)
            for e in events:
                if "turnId" in e:
                    assert e["turnId"] == turn_id, f"حدث بـ turnId غريب: {e}"

            # التسلسل الإلزامي
            assert types[0] == "orb.state" and events[0]["state"] == "thinking", f"أول حدث مش thinking: {events[0]}"
            assert types[-1] == "turn.completed", f"آخر حدث مش turn.completed: {events[-1]}"

            def idx(t, **match):
                for i, e in enumerate(events):
                    if e["type"] == t and all(e.get(k) == v for k, v in match.items()):
                        return i
                raise AssertionError(f"مفيش حدث {t} {match} -- الأنواع: {types}")

            i_exec = idx("orb.state", state="executing")
            i_tool_start = idx("tool.started")
            i_tool_ok = idx("tool.succeeded")
            i_stage = idx("stage.push")
            i_sstart = idx("stream.start")
            i_send = idx("stream.end")
            i_final = idx("orb.state", state="warning")

            assert i_exec < i_tool_start < i_tool_ok, "executing ثم tool.started ثم tool.succeeded"
            assert i_tool_ok < i_stage < i_sstart, "البطاقة لازم تتدفع بعد الأداة وقبل البث (عرف التأليف)"
            assert i_sstart < i_send < i_final, "البث قبل حالة الختام"

            # حقول الأدوات camelCase حرفيًا
            ts = events[i_tool_start]
            assert ts["toolCallId"] == "c-1" and ts["toolName"] == "loan_month_installments", f"tool.started: {ts}"
            assert events[i_tool_ok]["toolCallId"] == "c-1", "نفس toolCallId في النجاح"
            assert "summary" in events[i_tool_ok], "tool.succeeded لازم يحمل summary"

            # البطاقة
            stage = events[i_stage]
            assert stage["itemId"] == "installments" and stage["mode"] == "workspace", f"stage.push: {stage}"
            content = stage["content"]
            assert content["kind"] == "evidence", "البطاقة evidence -- ممنوع أنواع باسم الكيانات"
            assert content["severity"] == "warning", "فيه متأخر فعلي = warning (مش error أبدًا)"
            assert content["table"]["selectableBy"] == "id", "الجدول قابل للاختيار بـ id"
            assert any(row["status"] == "متأخر" for row in content["table"]["rows"]), "صف المتأخر موجود"
            natures = {f.get("nature") for f in content["facts"] if "nature" in f}
            assert "direct" in natures and "derived" in natures, "فصل direct/derived في الحقائق"

            # البث: تسلسل إلزامي وdelta تُلحق كما هي
            deltas = [e for e in events if e["type"] == "stream.delta"]
            assert deltas, "لازم فيه stream.delta"
            message_ids = {e["messageId"] for e in deltas} | {events[i_sstart]["messageId"], events[i_send]["messageId"]}
            assert len(message_ids) == 1, f"messageId واحد للرسالة: {message_ids}"
            assert "".join(e["delta"] for e in deltas) == REPLY, "الـ deltas المتجمعة لازم تساوي النص حرفيًا"
        finally:
            ui_channel.unsubscribe(q)

    def clean_installments_ends_with_success():
        os.environ["ADAM_TOKEN"] = TOKEN
        ui_channel._read_installments = lambda: FAKE_INSTALLMENTS_CLEAN

        def fake_runtime(text, chat_id):
            call_id = ui_channel.on_tool_started("loan_overview")
            ui_channel.on_tool_finished(call_id, "loan_overview", "كله مدفوع")
            return "كل الأقساط متسددة في معادها."

        RUNTIME["fn"] = fake_runtime
        q = ui_channel.subscribe()
        try:
            r = client.post("/ui/command", headers=AUTH, json={"type": "text", "text": "الأقساط عاملة إيه؟"})
            turn_id = (r.get_json() or {}).get("turnId")
            events = []
            wait_for(q, "turn.completed", turn_id, collected=events)
            stage = next(e for e in events if e["type"] == "stage.push")
            assert stage["content"]["severity"] == "info", "مفيش متأخر = رد هادي (القلق بالحالة مش الموضوع)"
            finals = [e for e in events if e["type"] == "orb.state" and e.get("state") in ("success", "warning")]
            assert finals and finals[-1]["state"] == "success", "الختام success مش warning"
        finally:
            ui_channel.unsubscribe(q)

    def tool_failure_emits_tool_failed():
        os.environ["ADAM_TOKEN"] = TOKEN

        def fake_runtime(text, chat_id):
            call_id = ui_channel.on_tool_started("create_reminder")
            ui_channel.on_tool_finished(call_id, "create_reminder", "حصل خطأ أثناء التنفيذ: انتهت مهلة الاتصال")
            return "معرفتش أعمل التذكير."

        RUNTIME["fn"] = fake_runtime
        q = ui_channel.subscribe()
        try:
            r = client.post("/ui/command", headers=AUTH, json={"type": "text", "text": "فكرني بكرة"})
            turn_id = (r.get_json() or {}).get("turnId")
            events = []
            wait_for(q, "turn.completed", turn_id, collected=events)
            failed = [e for e in events if e["type"] == "tool.failed"]
            assert failed, "لازم يطلع tool.failed"
            assert failed[0]["retryable"] is True, "retryable إلزامي في الفشل"
            assert "reason" in failed[0], "tool.failed لازم يحمل reason"
        finally:
            ui_channel.unsubscribe(q)

    # ============================================================
    # 3) الاستبدال والإلغاء
    # ============================================================

    def supersede_closes_old_turn_with_completed():
        os.environ["ADAM_TOKEN"] = TOKEN
        gate = threading.Event()

        def blocking_runtime(text, chat_id):
            gate.wait(timeout=10)
            return "خلصت متأخر"

        RUNTIME["fn"] = blocking_runtime
        q = ui_channel.subscribe()
        try:
            r1 = client.post("/ui/command", headers=AUTH, json={"type": "text", "text": "الأولى"})
            old_id = (r1.get_json() or {}).get("turnId")
            wait_for(q, "orb.state", old_id)  # الجولة الأولى بدأت فعلًا

            RUNTIME["fn"] = lambda text, chat_id: "رد الجولة الجديدة"
            r2 = client.post("/ui/command", headers=AUTH, json={"type": "text", "text": "التانية"})
            new_id = (r2.get_json() or {}).get("turnId")
            assert new_id != old_id, "الجولة الجديدة لازم بـ turnId جديد"

            # القديمة اتقفلت بـ turn.completed (المقاطعة فعل مقصود مش عطل)
            wait_for(q, "turn.completed", old_id)
            # والجديدة كملت عادي
            wait_for(q, "turn.completed", new_id)

            # بعد إغلاق القديمة: الثريد القديم بيصحى ويحاول يبث -- ممنوع
            # أي حدث بالـ turnId القديم يوصل
            gate.set()
            leaked = [e for e in drain(q, 0.5) if e.get("turnId") == old_id]
            assert not leaked, f"أحداث بالـ turnId القديم بعد الإغلاق: {leaked}"
        finally:
            gate.set()
            ui_channel.unsubscribe(q)

    def explicit_cancel_closes_with_turn_failed():
        os.environ["ADAM_TOKEN"] = TOKEN
        gate = threading.Event()

        def blocking_runtime(text, chat_id):
            gate.wait(timeout=10)
            return "مش المفروض توصل"

        RUNTIME["fn"] = blocking_runtime
        q = ui_channel.subscribe()
        try:
            r = client.post("/ui/command", headers=AUTH, json={"type": "text", "text": "شغلة طويلة"})
            turn_id = (r.get_json() or {}).get("turnId")
            wait_for(q, "orb.state", turn_id)

            rc = client.post("/ui/command", headers=AUTH, json={"type": "cancel", "turnId": turn_id})
            assert rc.status_code == 202, f"cancel رد {rc.status_code} بدل 202"

            failed = wait_for(q, "turn.failed", turn_id)
            assert "reason" in failed and "retryable" in failed, f"turn.failed ناقص حقول: {failed}"

            gate.set()
            leaked = [e for e in drain(q, 0.5) if e.get("turnId") == turn_id]
            assert not leaked, f"أحداث بعد الإلغاء: {leaked}"
        finally:
            gate.set()
            ui_channel.unsubscribe(q)

    def intent_and_confirm_fail_politely():
        os.environ["ADAM_TOKEN"] = TOKEN
        q = ui_channel.subscribe()
        try:
            for cmd in ({"type": "intent", "intent": "installments.pay"},
                        {"type": "confirm", "intent": "x", "confirmed": True}):
                r = client.post("/ui/command", headers=AUTH, json=cmd)
                assert r.status_code == 202, f"{cmd['type']} رد {r.status_code} بدل 202"
                turn_id = (r.get_json() or {}).get("turnId")
                failed = wait_for(q, "turn.failed", turn_id)
                assert failed["retryable"] is False, "مش مدعوم = مفيش 'حاول تاني'"
        finally:
            ui_channel.unsubscribe(q)

    # ============================================================
    # 4) حماية مسار تليجرام + شكل الـ SSE
    # ============================================================

    def hooks_are_noop_outside_ui_turn():
        # ده بالظبط اللي بيحصل لأي رسالة تليجرام: مفيش جولة UI على الثريد
        q = ui_channel.subscribe()
        try:
            call_id = ui_channel.on_tool_started("loan_overview")
            assert call_id is None, "برة جولة UI لازم يرجع None"
            ui_channel.on_tool_finished(call_id, "loan_overview", "نتيجة")
            ui_channel.on_tool_finished(None, "loan_overview", "نتيجة")
            assert drain(q, 0.2) == [], "ممنوع أي حدث يطلع من الخطافات برة جولة UI"
        finally:
            ui_channel.unsubscribe(q)

    def sse_wire_format():
        os.environ["ADAM_TOKEN"] = TOKEN
        rv = client.get("/ui/events", headers=AUTH)
        assert rv.status_code == 200, f"SSE رد {rv.status_code}"
        assert rv.mimetype == "text/event-stream", f"mimetype: {rv.mimetype}"
        it = iter(rv.response)

        def read_chunk():
            chunk = next(it)
            return chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk

        first = read_chunk()
        assert first.startswith("retry:"), f"أول سطر مش retry: {first!r}"

        ui_channel.publish({"type": "orb.state", "state": "idle", "label": "اختبار عربي"})
        data_line = read_chunk()
        assert data_line.startswith("data: "), f"شكل الرسالة: {data_line!r}"
        payload = json.loads(data_line[len("data: "):].strip())
        assert payload == {"type": "orb.state", "state": "idle", "label": "اختبار عربي"}, f"JSON: {payload}"
        assert "اختبار عربي" in data_line, "UTF-8 حرفي مش escaped"
        rv.close()  # بيقفل الجولة ويعمل unsubscribe جوه الـ generator

    for name, fn in [
        ("ADAM_TOKEN غايب = 503 رفض مش فتح", missing_secret_refuses_with_503),
        ("توكن غلط/غايب = 401 بدون تفاصيل", wrong_or_missing_token_is_401_without_details),
        ("أوامر غير صالحة = 400", invalid_commands_are_400),
        ("جولة الأقساط: التسلسل الإلزامي كامل", full_installments_turn_sequence),
        ("مفيش متأخر = info + success (مش warning)", clean_installments_ends_with_success),
        ("فشل أداة = tool.failed بـ retryable", tool_failure_emits_tool_failed),
        ("الاستبدال: القديمة turn.completed وصفر تسريب", supersede_closes_old_turn_with_completed),
        ("cancel الصريح = turn.failed", explicit_cancel_closes_with_turn_failed),
        ("intent/confirm = رفض مؤدب بأحداث حقيقية", intent_and_confirm_fail_politely),
        ("الخطافات no-op برة جولة UI (حماية تليجرام)", hooks_are_noop_outside_ui_turn),
        ("شكل الـ SSE على السلك", sse_wire_format),
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
