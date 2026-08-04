# -*- coding: utf-8 -*-
"""
🖼️ معالج الصور
- استقبال الصور من تليجرام
- تحليلها بواسطة Claude Vision
- حفظ التبادل في الذاكرة (قريبة + دائمة)
"""

import base64
from bot import bot, set_chat_id, send_error_message, safe_typing
from utils.logger import logger
from services.claude_service import analyze_with_vision
from services.firebase_service import save_conversation
from services.memory_service import get_memory, update_memory

@bot.message_handler(content_types=['photo'])
def handle_photo_message(message):
    """معالجة الصور المرسلة على تليجرام"""
    try:
        chat_id = message.chat.id
        set_chat_id(chat_id)
        safe_typing(chat_id)

        logger.info(f"🖼️ صورة من {chat_id}")

        # جيب أعلى جودة للصورة (آخر عنصر في القايمة)
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # حوّل الصورة لـ base64
        image_base64 = base64.b64encode(downloaded_file).decode('utf-8')

        # حدد نوع الصورة من امتداد الملف
        file_path_lower = file_info.file_path.lower()
        if file_path_lower.endswith('.png'):
            media_type = "image/png"
        elif file_path_lower.endswith('.webp'):
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"

        # النص المرافق للصورة (لو المستخدم كتب حاجة) أو نص افتراضي
        caption = message.caption or "شوف الصورة دي وقولي رأيك أو وصفها، وأي حاجة مهمة فيها تخص شغل Bahr Designs لو موجودة"

        # الذاكرة الدائمة عشان يفهم السياق حتى وهو بيحلل صورة
        memory_summary = get_memory(chat_id)

        reply = analyze_with_vision(image_base64, caption, media_type=media_type, memory_summary=memory_summary)

        bot.reply_to(message, reply)
        logger.info(f"✅ تم تحليل الصورة والرد على {chat_id}")

        # حفظ التبادل في الذاكرة (نستخدم caption كنص "الرسالة" بما إن الصورة نفسها مش نص)
        conversation_text = f"[صورة] {message.caption or ''}".strip()
        save_conversation(chat_id, conversation_text, reply)
        try:
            from services.claude_service import should_store_in_memory
            if should_store_in_memory(conversation_text, reply):
                update_memory(chat_id, conversation_text, reply)
        except Exception as e:
            logger.warning(f"LearningDecision (photo) error: {e}")
            update_memory(chat_id, conversation_text, reply)  # افتراضي آمن -- أحسن تتحفظ من تتفوت

    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الصورة: {e}")
        send_error_message(message, "حصلت مشكلة في تحليل الصورة، جرب تاني")
