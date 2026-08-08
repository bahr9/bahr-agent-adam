# -*- coding: utf-8 -*-
"""
📄 معالج الملفات (Documents)
- يستقبل ملفات PDF / DOCX / HTML / TXT من تليجرام
- يستخرج النص
- يبعته لـ ask_claude_agentic زي أي رسالة عادية
"""

import os
import tempfile
from bot import bot, set_chat_id, send_error_message, safe_typing
from utils.logger import logger
from services.claude_service import ask_claude_agentic, format_history_for_claude
from services.firebase_service import get_conversation_history, save_conversation
from services.memory_service import get_memory, update_memory


# ============================================================
# استخراج النص من الملف
# ============================================================

def _extract_text_from_docx(file_path):
    """استخراج النص من ملف DOCX"""
    from docx import Document
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _extract_text_from_pdf(file_path):
    """استخراج النص من ملف PDF"""
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


def _extract_text_from_html(file_path):
    """استخراج النص من ملف HTML"""
    try:
        from bs4 import BeautifulSoup
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        # إزالة scripts و styles
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)
    except ImportError:
        # fallback لو beautifulsoup4 مش متاحة
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        import re
        clean = re.sub(r"<[^>]+>", " ", content)
        return " ".join(clean.split())


def _extract_text_from_txt(file_path):
    """قراءة ملف نصي عادي"""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


# ============================================================
# قراءة البلانات (2b -- دمج دور HOPE، ADR 0006)
# ============================================================

# الأنواع المدعومة في المسار (الـ DXF بيتقري رياضيًا مش نصيًا)
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".html", ".htm", ".txt", ".dxf")

# كلمات في اسم الملف أو التعليق بتقول "ده بلان مش مستند نصي".
_PLAN_KEYWORDS = (
    "plan", "model", "layout", "arch", "furniture", "asbuilt", "as built",
    "as bulit",  # الغلطة الإملائية دي موجودة فعلًا في ملفات تصدير حقيقية
    "بلان", "مخطط", "لوحة", "فرش", "مسقط", "اسبيلت",
)
# بلان CAD متصدّر نصه الخطي شحيح جدًا (أرقام أبعاد متناثرة) --
# مستند حقيقي بيبقى فيه فقرات. الحد محسوب بهامش واسع بين الحالتين.
_SPARSE_TEXT_CHARS = 400


def looks_like_plan(file_name, caption, extracted_text):
    """هل الـ PDF ده بلان معماري يستاهل مسار الـ vision بدل مسار النص؟"""
    haystack = (file_name + " " + (caption or "")).lower()
    if any(keyword in haystack for keyword in _PLAN_KEYWORDS):
        return True
    return len((extracted_text or "").strip()) < _SPARSE_TEXT_CHARS


def extract_text(file_path, file_name):
    """
    يحدد نوع الملف ويستخرج النص منه.
    بيرجع (text, file_type) أو يـرفع Exception لو النوع مش مدعوم.
    """
    name_lower = file_name.lower()

    if name_lower.endswith(".docx"):
        return _extract_text_from_docx(file_path), "DOCX"
    elif name_lower.endswith(".pdf"):
        return _extract_text_from_pdf(file_path), "PDF"
    elif name_lower.endswith(".html") or name_lower.endswith(".htm"):
        return _extract_text_from_html(file_path), "HTML"
    elif name_lower.endswith(".txt"):
        return _extract_text_from_txt(file_path), "TXT"
    else:
        raise ValueError(f"نوع الملف مش مدعوم: {file_name}")


# ============================================================
# Handler الرئيسي
# ============================================================

def handle_document_message(message):
    """معالجة الملفات المرسلة على تليجرام"""
    chat_id = message.chat.id
    set_chat_id(chat_id)
    safe_typing(chat_id)

    doc = message.document
    file_name = doc.file_name or "document"

    logger.info("📄 ملف من " + str(chat_id) + " | " + file_name + " (" + str(doc.file_size) + " bytes)")

    # ===== فحص الحجم (أقصى 20MB — حد تليجرام) =====
    MAX_SIZE_MB = 20
    if doc.file_size and doc.file_size > MAX_SIZE_MB * 1024 * 1024:
        bot.reply_to(message, "الملف كبير جداً (أكتر من 20MB) — بعتلي نسخة أصغر.")
        return

    # ===== فحص النوع =====
    if not any(file_name.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
        bot.reply_to(message, "نوع الملف ده مش مدعوم دلوقتي.\nالأنواع المدعومة: PDF, DOCX, HTML, TXT, DXF")
        return

    # ===== تنزيل الملف =====
    tmp_path = None
    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)

        suffix = os.path.splitext(file_name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(downloaded)
            tmp_path = tmp.name

        # ===== مسار DXF: قراءة رياضية حتمية + فحص اتساق تلقائي =====
        if file_name.lower().endswith(".dxf"):
            from services.dxf_service import analyze_dxf_for_ahmed

            logger.info("📐 ملف DXF -- قراءة رياضية: " + file_name)
            reply = analyze_dxf_for_ahmed(tmp_path)
            bot.reply_to(message, reply)
            logger.info("✅ تم قراءة الـ DXF والرد على " + str(chat_id))

            conversation_text = "[لوحة DXF] " + file_name
            if message.caption:
                conversation_text += " - " + message.caption
            save_conversation(chat_id, conversation_text, reply)
            try:
                update_memory(chat_id, conversation_text, reply)
            except Exception as e:
                logger.warning("Memory (dxf) error: " + str(e))
            return

        # ===== استخراج النص =====
        text, file_type = extract_text(tmp_path, file_name)

    except ValueError as ve:
        bot.reply_to(message, str(ve))
        return
    except Exception as e:
        logger.error("❌ خطأ في استخراج النص: " + str(e))
        bot.reply_to(message, "حصلت مشكلة في قراءة الملف — تأكد إنه مش متشفر أو تالف.")
        return
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    # ===== تحديد الـ caption (لو بعت رسالة مع الملف) =====
    user_caption = message.caption or ""

    # ===== مسار البلانات (2b): PDF شكله بلان يروح للـ vision مش للنص =====
    # ده بيشمل تلقائيًا حالة الـ PDF اللي مفيهوش نص خالص (CAD/سكان) --
    # اللي كانت زمان بتترد بـ "مقدرتش أستخرج نص".
    if file_type == "PDF" and looks_like_plan(file_name, user_caption, text):
        try:
            import base64

            from services.claude_service import analyze_plan_pdf

            logger.info("📐 بلان PDF متعرف عليه -- رايح لمسار القراءة البصرية: " + file_name)
            pdf_b64 = base64.standard_b64encode(downloaded).decode()
            reply = analyze_plan_pdf(pdf_b64, user_caption, memory_summary=get_memory(chat_id))
        except Exception as e:
            logger.error("❌ خطأ في قراءة البلان: " + str(e))
            bot.reply_to(message, "حصلت مشكلة وأنا بقرا البلان — جرب تبعته تاني أو ابعته كصورة.")
            return

        plan_reading = reply          # النص الخام قبل أي تعديل -- ده اللي بيتمسك

        try:
            from services import verified_expression
            reply = verified_expression.verify_and_finalize(chat_id, reply)
        except Exception:
            pass

        bot.reply_to(message, reply)
        logger.info("✅ تم قراءة البلان والرد على " + str(chat_id))

        # ===== إمساك البلان (2026-08-08): اللي اتقرا يفضل موجود =====
        # بيجي **بعد** ما الرد يتبعت عن قصد: الحفظ فيه نداء وكتابة، ومحصلش
        # إنه يأخّر القراءة اللي أحمد مستنيها. ومعزول في try عشان أي عطل في
        # المسك ميمسّش القراءة اللي وصلت خلاص.
        try:
            from services import plan_capture
            note = plan_capture.capture_plan(plan_reading, user_caption)
            if note:
                bot.send_message(chat_id, note)
        except Exception as e:
            logger.error("❌ إمساك البلان فشل (القراءة وصلت عادي): " + str(e)[:100])

        conversation_text = "[بلان PDF] " + file_name
        if user_caption:
            conversation_text += " - " + user_caption
        save_conversation(chat_id, conversation_text, reply)
        # خلاصة البلان معلومة مشروع تستاهل الذاكرة الدائمة دايمًا.
        try:
            update_memory(chat_id, conversation_text, reply)
        except Exception as e:
            logger.warning("Memory (plan) error: " + str(e))
        return

    # ===== فحص إن فيه نص فعلاً (للمستندات غير البلانات) =====
    if not text or not text.strip():
        bot.reply_to(message, "مقدرتش أستخرج نص من الملف ده — ممكن يكون ملف صور (scanned) أو فاضي.")
        return

    # ===== بناء الرسالة اللي هتروح لـ Claude =====
    MAX_CHARS = 12000  # حد معقول عشان ما نتخطاش الـ context
    truncated = False
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        truncated = True

    prompt_parts = [
        "[ملف " + file_type + ": " + file_name + "]"
    ]
    if user_caption:
        prompt_parts.append("تعليق أحمد: " + user_caption)
    if truncated:
        prompt_parts.append("(ملحوظة: الملف طويل، ده أول " + str(MAX_CHARS) + " حرف منه)")
    prompt_parts.append("")
    prompt_parts.append(text)

    full_prompt = "\n".join(prompt_parts)

    # ===== جيب السياق والذاكرة =====
    from config import CONVERSATION_CONTEXT_WINDOW
    # نافذة بمرساة ثابتة من المخزن -- بدون قص إضافي (اقتصاد الكاش 2026-08-06)
    stored_history = get_conversation_history(chat_id, limit=CONVERSATION_CONTEXT_WINDOW)
    recent_history = format_history_for_claude(stored_history)
    memory_summary = get_memory(chat_id)

    # ===== ارسل لـ Claude =====
    reply = ask_claude_agentic(
        full_prompt,
        chat_id,
        conversation_history=recent_history,
        memory_summary=memory_summary
    )

    # ===== Verbatim Match Validator (Stage 6/7) =====
    try:
        from services import verified_expression
        reply = verified_expression.verify_and_finalize(chat_id, reply)
    except Exception:
        pass

    bot.reply_to(message, reply)
    logger.info("✅ تم معالجة الملف والرد على " + str(chat_id))

    # ===== حفظ في الذاكرة =====
    conversation_text = "[ملف " + file_type + "] " + file_name
    if user_caption:
        conversation_text += " - " + user_caption
    save_conversation(chat_id, conversation_text, reply)
    try:
        from services.claude_service import should_store_in_memory
        if should_store_in_memory(conversation_text, reply):
            update_memory(chat_id, conversation_text, reply)
    except Exception as e:
        logger.warning("LearningDecision (document) error: " + str(e))
        update_memory(chat_id, conversation_text, reply)  # افتراضي آمن -- أحسن تتحفظ من تتفوت
