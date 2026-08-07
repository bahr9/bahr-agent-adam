# -*- coding: utf-8 -*-
"""
UI Channel -- قناة adam-ui (CONTRACT_V1)
=====================================================
تنفيذ جانب آدم لعقد `adam-ui/docs/execution/CONTRACT_V1.md`
(المجمّد بوسم contract-v1-freeze بتاريخ 2026-08-07):

    GET  /ui/events   -- SSE: كل رسالة = حدث JSON واحد في حقل data
    POST /ui/command  -- أمر JSON واحد، الرد 202 = "استُلم"، والنتيجة أحداث

القاعدة الحاكمة: آدم بوت تليجرام أولًا -- القناة دي **إضافة جانبية**:
  - مفيش أي استيراد من هنا في مسار تليجرام. العكس بس: claude_service
    بينده خطافين (on_tool_started/on_tool_finished) وهما no-op تام لو
    الثريد الحالي مش شغّال جولة UI (يعني: كل رسايل تليجرام).
  - أي فشل جوه القناة بيتسجل في اللوج وميرفعش استثناء لبرة.

الأمان: توكن واحد مشترك من env var اسمه ADAM_TOKEN، بيتفحص على كل طلب
(Authorization: Bearer). توكن غلط/غايب = 401 بدون تفاصيل (نص العقد).
ADAM_TOKEN نفسه مش متظبط في البيئة = 503 fail-closed -- نفس قاعدة
أوديت 2026-08-04 المطبقة على باقي الـ endpoints (سر غايب = رفض مش فتح).

نطاق الشريحة الأولى (أصغر إثبات):
  - أمر text: جولة كاملة بنفس بايبلاين تليجرام (Runtime -> EB ->
    verified_expression) مع الأحداث بالتسلسل الإلزامي:
    thinking -> executing -> tool.* -> stage.push -> streaming -> turn.completed
  - أمر cancel: يقفل الجولة بـ turn.failed (نص العقد).
  - قاعدة الاستبدال (supersede): أمر جديد وجولة شغالة = القديمة تتقفل
    بـ turn.completed، وممنوع أي حدث بعدها يحمل turnId القديم.
  - بطاقة الأقساط (evidence + جدول قابل للاختيار) بتتدفع **قبل** بث النص
    (عرف التأليف الإلزامي في قسم 6 من العقد).
  - أوامر intent/confirm معرّفة بالعقد لكن تنفيذها مؤجل للشريحة الجاية --
    بنرد عليها بأحداث حقيقية (turn.failed, retryable: false) مش صمت.

ملاحظة بث: البث حاليًا تقطيع للرد النهائي (chunking) مش token streaming
حقيقي من الموديل -- التسلسل والعقد محترمين بالحرف، والترقية لبث حقيقي
تعديل داخلي هنا مش خرق عقد.
"""

import hmac
import json
import os
import queue
import re
import threading
import uuid
import time

from flask import Blueprint, Response, jsonify, request

from utils.logger import logger

# ============================================================
# ثوابت قابلة للضبط (الاختبارات بتصفّر التأخير)
# ============================================================

STREAM_CHUNK_SIZE = 40      # حروف لكل stream.delta -- تقطيع حرفي يحافظ على النص كما هو
STREAM_DELAY_SECONDS = 0.03 # إحساس البث؛ الاختبارات بتخليه 0
SSE_KEEPALIVE_SECONDS = 15  # تعليق keepalive لما مفيش أحداث
SUBSCRIBER_QUEUE_MAX = 1000 # مشترك بطيء لحد كده = بنرمي الحدث ليه (القناة stateless بالعقد)

# ============================================================
# Event Bus -- نشر الأحداث لكل مشتركي الـ SSE
# ============================================================

_subscribers = []
_subs_lock = threading.Lock()


def subscribe():
    """اشتراك جديد (اتصال SSE واحد). بيرجع Queue بيوصلها كل حدث من لحظة الاشتراك."""
    q = queue.Queue(maxsize=SUBSCRIBER_QUEUE_MAX)
    with _subs_lock:
        _subscribers.append(q)
    return q


def unsubscribe(q):
    with _subs_lock:
        if q in _subscribers:
            _subscribers.remove(q)


def publish(event):
    """
    نشر حدث لكل المشتركين. ممنوع يرمي استثناء أبدًا -- ده بينده من جوه
    بايبلاين حقيقي وأي عطل هنا ميأثرش عليه (قاعدة "تليجرام ميتلمسش").
    """
    try:
        with _subs_lock:
            subs = list(_subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                # القناة stateless بالعقد: اللي فاته حدث مش بيتعاد.
                logger.warning("UI channel: مشترك بطيء -- حدث اترمى (" + str(event.get("type")) + ")")
    except Exception as e:
        logger.error("UI channel publish error: " + str(e))


# ============================================================
# الجولة (Turn) -- ربط أحداث "أمر -> رد" بـ turnId واحد
# ============================================================

class _Turn:
    """
    جولة واحدة. القفل بيضمن قاعدة الاستبدال حرفيًا: بعد إغلاق الجولة
    (active=False) ممنوع يطلع أي حدث بيحمل turnId بتاعها.
    """

    def __init__(self):
        self.id = "t-" + uuid.uuid4().hex[:8]
        self.lock = threading.Lock()
        self.active = True
        self.cancelled = False
        self.tools_seen = []      # أسماء الأدوات اللي اتنفذت فعليًا في الجولة
        self.tool_counter = 0
        self.executing_sent = False

    def emit(self, event):
        """نشر حدث تابع للجولة -- بيتسقط صامت لو الجولة اتقفلت (supersede/cancel)."""
        with self.lock:
            if not self.active:
                return False
            publish(event)
            return True

    def close(self, closing_event):
        """إغلاق الجولة بحدثها الختامي (turn.completed أو turn.failed) مرة واحدة بس."""
        with self.lock:
            if not self.active:
                return False
            self.active = False
            publish(closing_event)
            return True


_state_lock = threading.Lock()
_current_turn = None
_tls = threading.local()

# بيتظبطوا في register_ui_channel -- من غيرهم أمر text بيرد 503
_runtime_call = None     # (text, chat_id) -> str  : نفس بايبلاين تليجرام
_chat_id_getter = None   # () -> Optional[int]


# ============================================================
# خطافات claude_service -- no-op تام خارج جولة UI
# ============================================================

def on_tool_started(tool_name):
    """
    بينده من لوب الأدوات في ask_claude_agentic قبل تنفيذ أداة.
    لمسار تليجرام (مفيش جولة UI على الثريد ده) = بيرجع None فورًا.
    """
    turn = getattr(_tls, "turn", None)
    if turn is None:
        return None
    try:
        turn.tool_counter += 1
        call_id = "c-" + str(turn.tool_counter)
        turn.tools_seen.append(tool_name)
        if not turn.executing_sent:
            turn.executing_sent = True
            turn.emit({"type": "orb.state", "state": "executing", "turnId": turn.id, "label": tool_name})
        turn.emit({"type": "tool.started", "turnId": turn.id, "toolCallId": call_id, "toolName": tool_name})
        return call_id
    except Exception as e:
        logger.error("UI channel on_tool_started: " + str(e))
        return None


def on_tool_finished(call_id, tool_name, result_text):
    """
    بينده بعد تنفيذ الأداة بنتيجتها النصية. التمييز نجاح/فشل heuristic
    على بادئات رسائل الفشل الفعلية في _execute_tool ("حصل خطأ أثناء
    التنفيذ:" للاستثناءات، و"❌" لفشل معلن) -- والفشل الحقيقي التقني
    بيوصل برضه من مسار الاستثناءات فوق.
    """
    turn = getattr(_tls, "turn", None)
    if turn is None or call_id is None:
        return
    try:
        text = (result_text or "").strip()
        summary = text.splitlines()[0][:120] if text else ""
        failed = text.startswith("حصل خطأ أثناء التنفيذ:") or text.startswith("❌")
        if failed:
            turn.emit({
                "type": "tool.failed", "turnId": turn.id, "toolCallId": call_id,
                "reason": summary or "فشل تنفيذ الأداة", "retryable": True,
            })
        else:
            turn.emit({
                "type": "tool.succeeded", "turnId": turn.id, "toolCallId": call_id,
                "summary": summary or ("اتنفذت " + tool_name),
            })
    except Exception as e:
        logger.error("UI channel on_tool_finished: " + str(e))


# ============================================================
# بطاقة الأقساط -- evidence واحد (ممنوع أنواع باسم الكيانات، قسم 5)
# ============================================================

def _read_installments():
    """
    قراءة فقط من نفس مصدر بيانات الأدوات (loan_service). الاختبارات
    بتستبدل الدالة دي بالكامل -- ممنوع أي لمس لبيانات الإنتاج هناك.
    """
    from services import loan_service

    month_key = loan_service.get_current_month_key()
    items, total = loan_service.get_month_installments(month_key)
    overdue, overdue_total, earliest_month = loan_service.get_overdue_installments()
    return {
        "month_key": month_key,
        "items": items,
        "total": total,
        "overdue": overdue,
        "overdue_total": overdue_total,
        "earliest_overdue_month": earliest_month,
    }


def _fmt_amount(amount):
    try:
        return "{:,} ج.م".format(int(amount))
    except Exception:
        return str(amount) + " ج.م"


def _build_installments_card():
    """
    بيبني محتوى evidence لبطاقة الأقساط من القراءة المباشرة.
    بيرجع (content, has_overdue) أو (None, False) لو القراءة فشلت --
    فشل البطاقة مش بيكسر الجولة (النص بيكمّل عادي).

    القلق بالحالة مش الموضوع: severity بتبقى warning **بس** لو فيه قسط
    متأخر فعليًا -- أقساط ماشية في معادها = info ورد هادي.
    """
    try:
        data = _read_installments()
    except Exception as e:
        logger.error("UI channel: قراءة الأقساط للبطاقة فشلت -- البطاقة بتتعدى: " + str(e))
        return None, False

    overdue = data.get("overdue") or []
    items = data.get("items") or []
    has_overdue = len(overdue) > 0

    rows = []
    for inst in overdue:
        rows.append({
            "id": str(inst.get("program_id", "")) + "-" + str(inst.get("index", "")),
            "program": inst.get("program", ""),
            "amount": _fmt_amount(inst.get("amount", 0)),
            "date": str(inst.get("date", "")),
            "status": "متأخر",
        })
    for inst in items:
        rows.append({
            "id": str(inst.get("program_id", "")) + "-" + str(inst.get("index", "")),
            "program": inst.get("program", ""),
            "amount": _fmt_amount(inst.get("amount", 0)),
            "date": data.get("month_key", ""),
            "status": "مدفوع" if inst.get("paid") else "مستحق",
        })

    unpaid_this_month = [i for i in items if not i.get("paid")]

    facts = [
        {"label": "أقساط الشهر", "value": str(len(items)), "nature": "direct"},
        {"label": "إجمالي الشهر", "value": _fmt_amount(data.get("total", 0)), "nature": "direct"},
        {"label": "المتبقي من الشهر", "value": str(len(unpaid_this_month)) + " قسط", "nature": "derived"},
    ]
    if has_overdue:
        facts.append({
            "label": "متأخر",
            "value": str(len(overdue)) + " قسط بإجمالي " + _fmt_amount(data.get("overdue_total", 0)),
            "nature": "derived",
            "severity": "warning",
        })
        interpretation = ("فيه " + str(len(overdue)) + " قسط متأخر من "
                          + str(data.get("earliest_overdue_month", "")) + " محتاج يتقفل قبل أقساط الشهر.")
        recommendation = "ابدأ بالمتأخر الأقدم (" + (overdue[0].get("program", "") if overdue else "") + ")."
    else:
        interpretation = "كل الأقساط ماشية في معادها -- مفيش حاجة متأخرة."
        recommendation = None

    try:
        from utils.time_utils import now_cairo
        updated_at = "من لحظتها (" + now_cairo().strftime("%H:%M") + ")"
    except Exception:
        updated_at = "من لحظتها"

    content = {
        "kind": "evidence",
        "entity": {"type": "installments", "id": "installments", "label": "الأقساط"},
        "severity": "warning" if has_overdue else "info",
        "facts": facts,
        "table": {
            "columns": [
                {"key": "program", "label": "الجهة"},
                {"key": "amount", "label": "المبلغ", "align": "end"},
                {"key": "date", "label": "الاستحقاق"},
                {"key": "status", "label": "الحالة"},
            ],
            "rows": rows,
            "selectableBy": "id",
        },
        "interpretation": interpretation,
        "provenance": {"source": "دفتر الأقساط", "updatedAt": updated_at, "demo": False},
    }
    if recommendation:
        content["recommendation"] = recommendation
    return content, has_overdue


# الأدوات اللي تنفيذها في الجولة بيطلّع بطاقة الأقساط
_LOAN_TOOL_PREFIX = "loan_"


# ============================================================
# تشغيل الجولة
# ============================================================

def _chunks(text, size=None):
    """تقطيع حرفي بالفهارس -- delta تُلحق كما هي، مفيش لمس للمسافات (قسم 3.2)."""
    size = size or STREAM_CHUNK_SIZE
    return [text[i:i + size] for i in range(0, len(text), size)]


# ============================================================
# تحويل نص تليجرام لنص واجهة
# ============================================================
#
# الرد بيتولد لتليجرام، وتليجرام بيرندر Markdown. الواجهة لأ: العقد بيقول
# إن الـ delta "تُلحق كما هي" (قسم 3.2)، يعني أي `**` أو `|` بيوصل بيتعرض
# للمستخدم حرف بحرف. لازم النص يتنضف هنا -- عند حدود القناة -- مش في
# مولّد الرد، عشان مسار تليجرام ميتلمسش خالص.

_MD_PIPE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_MD_PIPE_SEP = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")
_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_MD_FENCE = re.compile(r"^\s*```")
_MD_LINK = re.compile(r"\[([^\]\n]+)\]\((?:[^)\s]+)(?:\s+\"[^\"]*\")?\)")
_MD_BOLD_ITALIC = re.compile(r"(\*{1,3}|_{2,3})(?=\S)(.+?)(?<=\S)\1", re.S)
_MD_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_MD_BULLET = re.compile(r"^(\s*)[*+-]\s+")


def _drop_markdown_tables(text):
    """شيل بلوكات جداول الماركداون بالكامل.

    الجدول بيتبعت أصلاً كبطاقة evidence عبر stage.push (عرف التأليف في
    قسم 6). لو سيبناه في النص كمان، المستخدم بيشوف نفس البيانات مرتين --
    مرة بطاقة مرتبة ومرة أنابيب وشرط خام. البطاقة هي النسخة الصحيحة.

    بنشيل البلوك **بس** لو فيه سطر فاصل (|---|---|) -- ده اللي بيفرّق
    الجدول الحقيقي عن سطر عادي صادف إنه بادئ ومنتهي بـ |.
    """
    lines = text.split("\n")
    out, block = [], []

    def _flush():
        if block and any(_MD_PIPE_SEP.match(b) for b in block):
            return                      # جدول حقيقي -- بيتشال بالكامل
        out.extend(block)

    for line in lines:
        if _MD_PIPE_ROW.match(line):
            block.append(line)
            continue
        _flush()
        block = []
        out.append(line)
    _flush()

    return "\n".join(out)


def _to_plain_text(text):
    """نص تليجرام (Markdown) -> نص عادي للواجهة.

    بيشيل التنسيق ويسيب المحتوى: النجوم والشرط السفلي والباك-تِك وعناوين #
    والروابط بتتحول لنصها. الجداول بتتشال خالص (بطاقة evidence بتغطيها).
    """
    if not text:
        return text

    text = _drop_markdown_tables(text)

    lines = []
    in_fence = False
    for line in text.split("\n"):
        if _MD_FENCE.match(line):
            in_fence = not in_fence
            continue                    # سور الكود نفسه مش محتوى
        if in_fence:
            lines.append(line)          # جوه الكود: النص زي ما هو بالظبط
            continue
        line = _MD_HEADING.sub("", line)
        line = _MD_BULLET.sub(r"\1• ", line)
        line = _MD_LINK.sub(r"\1", line)
        line = _MD_INLINE_CODE.sub(r"\1", line)
        line = _MD_BOLD_ITALIC.sub(r"\2", line)
        lines.append(line)

    # الجداول المشالة بتسيب فراغات -- بنلم أكتر من سطرين فاضيين في واحد
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return cleaned.strip()


def _new_message_id():
    """معرّف فريد لكل رد.

    كان ثابتًا "m-1"، فكل رد في كل جولة كان بيوصل بنفس المعرّف والواجهة
    اضطرت تركّب مفتاح محلي من turnId/messageId عشان تفرّق بينهم. العقد
    (قسم 3.2) بيلزم بوجود الحقل ومبيقيّدش قيمته -- فبناخد نفس شكل turnId.
    """
    return "m-" + uuid.uuid4().hex[:8]


def _aborted(turn):
    with turn.lock:
        return not turn.active


def _run_turn(turn, text):
    """
    جسم الجولة -- بيشتغل في thread مستقل عن تليجرام تمامًا.
    التسلسل: thinking -> (executing/tool.* من الخطافات أثناء التنفيذ)
    -> stage.push قبل البث -> speaking + stream.start/delta*/end
    -> success|warning -> turn.completed.
    """
    global _current_turn
    _tls.turn = turn
    try:
        turn.emit({"type": "orb.state", "state": "thinking", "turnId": turn.id})

        chat_id = None
        if _chat_id_getter is not None:
            try:
                chat_id = _chat_id_getter()
            except Exception as e:
                logger.warning("UI channel: chat_id getter فشل -- الجولة بتكمّل من غيره: " + str(e))

        reply = _runtime_call(text, chat_id)
        # الرد اتولد لتليجرام (Markdown). الواجهة بتعرض الـ delta حرفيًا،
        # فبنحوّله لنص عادي هنا عند حدود القناة -- مسار تليجرام ميتلمسش.
        reply = _to_plain_text(reply or "")
        reply = reply.strip() or "تمام."

        if _aborted(turn):
            return

        # عرف التأليف الإلزامي (قسم 6): الدليل يتدفع **قبل** الكلام عنه
        has_overdue = False
        if any(name.startswith(_LOAN_TOOL_PREFIX) for name in turn.tools_seen):
            content, has_overdue = _build_installments_card()
            if content:
                turn.emit({
                    "type": "stage.push",
                    "turnId": turn.id,
                    "itemId": "installments",
                    "mode": "workspace",
                    "title": "الأقساط",
                    "content": content,
                })

        turn.emit({"type": "orb.state", "state": "speaking", "turnId": turn.id})
        message_id = _new_message_id()
        turn.emit({"type": "stream.start", "turnId": turn.id, "messageId": message_id})
        for chunk in _chunks(reply):
            if _aborted(turn):
                return
            turn.emit({"type": "stream.delta", "turnId": turn.id, "messageId": message_id, "delta": chunk})
            if STREAM_DELAY_SECONDS:
                time.sleep(STREAM_DELAY_SECONDS)
        turn.emit({"type": "stream.end", "turnId": turn.id, "messageId": message_id})

        # warning ≠ error (قاعدة صلبة): متأخرات حقيقية = warning وبتفضل
        # بعد turn.completed. غير كده success (ومضة ثم idle على الواجهة).
        final_state = "warning" if has_overdue else "success"
        turn.emit({"type": "orb.state", "state": final_state, "turnId": turn.id})
        turn.close({"type": "turn.completed", "turnId": turn.id})

    except Exception as e:
        # عطل تقني فعلي بس هو اللي بيتقال error (قاعدة العقد الصلبة)
        logger.error("UI channel turn failed [" + turn.id + "]: " + str(e))
        turn.emit({"type": "orb.state", "state": "error", "turnId": turn.id})
        turn.close({"type": "turn.failed", "turnId": turn.id,
                    "reason": "حصل عطل تقني أثناء تنفيذ الجولة", "retryable": True})
    finally:
        _tls.turn = None
        with _state_lock:
            if _current_turn is turn:
                _current_turn = None


def _start_turn(text):
    """
    بدء جولة جديدة مع تطبيق قاعدة الاستبدال: الجولة القديمة (لو شغالة)
    بتتقفل بـ turn.completed -- مقاطعة المستخدم فعل مقصود مش عطل.
    الـ thread القديم بيكتشف الإغلاق عند أقرب checkpoint ويسكت (أحداثه
    بتتسقط بقفل الجولة، فقاعدة "ممنوع حدث بالـ turnId القديم" مضمونة).
    """
    global _current_turn
    with _state_lock:
        old = _current_turn
        turn = _Turn()
        _current_turn = turn
    if old is not None:
        old.close({"type": "turn.completed", "turnId": old.id})
    threading.Thread(target=_run_turn, args=(turn, text), daemon=True, name="ui-turn-" + turn.id).start()
    return turn.id


def _cancel_turn(turn_id=None):
    """
    cancel الصريح = الاستثناء الوحيد اللي بيقفل بـ turn.failed (نص العقد).
    بيرجع True لو فيه جولة اتلغت فعلًا.
    """
    with _state_lock:
        turn = _current_turn
    if turn is None:
        return False
    if turn_id and turn.id != turn_id:
        return False
    turn.cancelled = True
    closed = turn.close({"type": "turn.failed", "turnId": turn.id,
                         "reason": "اتوقفت بأمر إيقاف صريح من أحمد", "retryable": True})
    if closed:
        # orb بترجع idle -- من غير turnId عشان الجولة اتقفلت خلاص
        publish({"type": "orb.state", "state": "idle"})
    return closed


# ============================================================
# HTTP -- Blueprint
# ============================================================

ui_blueprint = Blueprint("ui_channel", __name__)


def _check_bearer():
    """
    فحص Authorization: Bearer <ADAM_TOKEN> على كل طلب.
    بيرجع None لو نجح، أو (response, status) لو اترفض.
    401 بدون تفاصيل (نص العقد) -- و503 fail-closed لو السر نفسه مش
    متظبط في البيئة (قاعدة أوديت 2026-08-04، نفس باقي الـ endpoints).
    """
    secret = os.getenv("ADAM_TOKEN", "")
    if not secret:
        logger.error("🔒 ADAM_TOKEN مش متظبط -- قناة الـUI مرفوضة (fail-closed)")
        return jsonify({"status": "unavailable", "message": "server secret not configured"}), 503

    auth = request.headers.get("Authorization", "")
    provided = auth[len("Bearer "):] if auth.startswith("Bearer ") else ""
    if not provided or not hmac.compare_digest(provided, secret):
        return jsonify({"status": "unauthorized"}), 401
    return None


@ui_blueprint.route("/ui/events", methods=["GET"])
def ui_events():
    """قناة الأحداث SSE -- stateless: بتعرض من لحظة الاتصال، مفيش إعادة إرسال."""
    denied = _check_bearer()
    if denied:
        return denied

    def stream():
        q = subscribe()
        try:
            # إعادة الاتصال مسؤولية الواجهة (backoff) -- بنقترح فاصل أولي بس
            yield "retry: 3000\n\n"
            while True:
                try:
                    event = q.get(timeout=SSE_KEEPALIVE_SECONDS)
                except queue.Empty:
                    yield ": keepalive\n\n"
                    continue
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        finally:
            unsubscribe(q)

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@ui_blueprint.route("/ui/command", methods=["POST"])
def ui_command():
    """
    استقبال أوامر الواجهة (قسم 4 من العقد). الرد 202 = "استُلم" --
    النتيجة الفعلية بتوصل كأحداث على قناة الـ SSE.
    """
    denied = _check_bearer()
    if denied:
        return denied

    try:
        data = request.get_json(force=True, silent=True) or {}
        cmd_type = data.get("type", "")

        if cmd_type == "text":
            text = (data.get("text") or "").strip()
            if not text:
                return jsonify({"status": "error", "message": "text مطلوب"}), 400
            if _runtime_call is None:
                logger.error("UI channel: أمر text وصل قبل تهيئة runtime_call")
                return jsonify({"status": "unavailable", "message": "ui channel not initialized"}), 503
            turn_id = _start_turn(text)
            return jsonify({"status": "accepted", "turnId": turn_id}), 202

        if cmd_type == "cancel":
            _cancel_turn(data.get("turnId"))
            return jsonify({"status": "accepted"}), 202

        if cmd_type in ("intent", "confirm"):
            # معرّفين بالعقد -- تنفيذهم في الشريحة الجاية. بنرد بأحداث
            # حقيقية مش صمت: جولة بتفشل فورًا بسبب واضح وretryable: false
            # (الواجهة مش هتعرض "حاول تاني" لحاجة مش هتنجح).
            turn_id = "t-" + uuid.uuid4().hex[:8]
            publish({
                "type": "turn.failed", "turnId": turn_id,
                "reason": "أوامر " + cmd_type + " لسه مش مدعومة في جانب آدم (الشريحة الأولى من V1)",
                "retryable": False,
            })
            logger.info("UI channel: أمر " + cmd_type + " وصل -- مرفوض بأدب (مش مدعوم في الشريحة دي)")
            return jsonify({"status": "accepted", "turnId": turn_id}), 202

        if cmd_type == "voice":
            # معرَّف ومحجوز بالعقد -- **لا يُرسل في V1** (المايك معطّل)
            return jsonify({"status": "error", "message": "voice محجوز ولا يُرسل في V1"}), 400

        return jsonify({"status": "error", "message": "نوع أمر غير معروف"}), 400

    except Exception as e:
        logger.error("UI command error: " + str(e))
        return jsonify({"status": "error", "message": "internal error"}), 500


def register_ui_channel(flask_app, runtime_call, chat_id_getter=None):
    """
    ربط القناة بتطبيق الـ Flask الموجود.

    runtime_call(text, chat_id) -> str : لازم يكون نفس بايبلاين تليجرام
    (Runtime -> EB -> verified_expression) عشان الردين يفضلوا حاجة واحدة.
    """
    global _runtime_call, _chat_id_getter
    _runtime_call = runtime_call
    _chat_id_getter = chat_id_getter
    flask_app.register_blueprint(ui_blueprint)
