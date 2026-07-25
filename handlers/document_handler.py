# -*- coding: utf-8 -*-
"""
📄 معالج الملفات (Documents)
- يستقبل ملفات PDF / DOCX / HTML / TXT من تليجرام
- يستخرج النص
- يبعته لـ ask_claude_agentic زي أي رسالة عادية
"""

import os
import tempfile
from bot import bot, set_chat_id, send_error_message
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
    bot.send_chat_action(chat_id, 'typing')

    doc = message.document
    file_name = doc.file_name or "document"

    logger.info("📄 ملف من " + str(chat_id) + " | " + file_name + " (" + str(doc.file_size) + " bytes)")

    # ===== فحص الحجم (أقصى 20MB — حد تليجرام) =====
    MAX_SIZE_MB = 20
    if doc.file_size and doc.file_size > MAX_SIZE_MB * 1024 * 1024:
        bot.reply_to(message, "الملف كبير جداً (أكتر من 20MB) — بعتلي نسخة أصغر.")
        return

    # ===== فحص النوع =====
    supported = (".pdf", ".docx", ".html", ".htm", ".txt")
    if not any(file_name.lower().endswith(ext) for ext in supported):
        bot.reply_to(message, "نوع الملف ده مش مدعوم دلوقتي.\nالأنواع المدعومة: PDF, DOCX, HTML, TXT")
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

    # ===== فحص إن فيه نص فعلاً =====
    if not text or not text.strip():
        bot.reply_to(message, "مقدرتش أستخرج نص من الملف ده — ممكن يكون ملف صور (scanned) أو فاضي.")
        return

    # ===== تحديد الـ caption (لو بعت رسالة مع الملف) =====
    user_caption = message.caption or ""

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
    stored_history = get_conversation_history(chat_id, limit=15)
    recent_history = format_history_for_claude(stored_history, limit=8)
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
    update_memory(chat_id, conversation_text, reply)
