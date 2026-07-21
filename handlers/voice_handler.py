# -*- coding: utf-8 -*-
"""
🎤 معالج الرسائل الصوتية
- استقبال الصوت من تليجرام
- تحويله لنص بواسطة Whisper
- معالجته زي أي رسالة نصية عادية (نفس الأدوات والذاكرة)
"""

import os
from bot import bot, set_chat_id, send_error_message
from utils.logger import logger
from services.openai_service import transcribe_audio, text_to_speech, is_openai_available
from services.claude_service import ask_claude_agentic, format_history_for_claude
from services.firebase_service import get_conversation_history, save_conversation
from services.memory_service import get_memory, update_memory

@bot.message_handler(content_types=['voice'])
def handle_voice_message(message):
    """معالجة الرسائل الصوتية"""
    try:
        chat_id = message.chat.id
        set_chat_id(chat_id)

        if not is_openai_available():
            bot.reply_to(message, "❌ ميزة الرسائل الصوتية مش مفعّلة دلوقتي (مفتاح OpenAI مش موجود).")
            return

        bot.send_chat_action(chat_id, 'typing')
        logger.info(f"🎤 رسالة صوتية من {chat_id}")

        # نزّل ملف الصوت من تليجرام
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        import tempfile
        voice_path = os.path.join(tempfile.gettempdir(), f"voice_{message.message_id}.ogg")
        with open(voice_path, "wb") as f:
            f.write(downloaded_file)

        # حوّل الصوت لنص
        transcribed_text = transcribe_audio(voice_path, language="ar")

        # امسح الملف المؤقت بعد الاستخدام
        try:
            os.remove(voice_path)
        except Exception:
            pass

        if not transcribed_text:
            bot.reply_to(message, "❌ ما قدرتش أفهم الرسالة الصوتية، جرب تاني.")
            return

        logger.info(f"🎤 اتحوّلت الرسالة الصوتية لنص: {transcribed_text[:50]}...")

        # عالج النص المحوّل زي أي رسالة عادية (نفس الأدوات والذاكرة)
        stored_history = get_conversation_history(chat_id, limit=15)
        recent_history = format_history_for_claude(stored_history, limit=8)
        memory_summary = get_memory(chat_id)

        reply = ask_claude_agentic(
            transcribed_text,
            chat_id,
            conversation_history=recent_history,
            memory_summary=memory_summary
        )

        # إرسال الرد نص أولاً
        bot.reply_to(message, reply)
        logger.info(f"✅ تم الرد على الرسالة الصوتية لـ {chat_id}")
        
        # محاولة تحويل الرد لصوت وإرساله (اختياري)
        try:
            audio_file = text_to_speech(reply, output_file_path=os.path.join(tempfile.gettempdir(), f"response_{message.message_id}.mp3"))
            if audio_file and os.path.exists(audio_file):
                with open(audio_file, "rb") as audio:
                    bot.send_audio(chat_id, audio, title="🎤 الرد الصوتي")
                logger.info(f"✅ اتبعت رد صوتي لـ {chat_id}")
                # امسح الملف المؤقت
                try:
                    os.remove(audio_file)
                except:
                    pass
            else:
                logger.warning("⚠️ ما قدرتش تحول الرد لصوت، بس الرد النصي اتبعت")
        except Exception as e:
            logger.warning(f"⚠️ خطأ في إرسال الرد الصوتي (الرد النصي اتبعت): {e}")

        conversation_text = f"[صوت] {transcribed_text}"
        save_conversation(chat_id, conversation_text, reply)
        if len(transcribed_text) > 15 or len(reply) > 60:
            update_memory(chat_id, conversation_text, reply)

    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الرسالة الصوتية: {e}")
        send_error_message(message, "حصلت مشكلة في تحويل الرسالة الصوتية، جرب تاني")
