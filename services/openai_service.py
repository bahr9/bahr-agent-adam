# -*- coding: utf-8 -*-
"""
🎤 خدمة OpenAI
- تحويل الصوت لنص (Whisper)
- تحويل النص لصوت (TTS) - اختياري
"""

from openai import OpenAI
from utils.logger import logger
from config import OPENAI_API_KEY

# إنشاء العميل (لو متوفر)
openai_client = None

def init_openai():
    """تهيئة اتصال OpenAI"""
    global openai_client
    
    if OPENAI_API_KEY:
        try:
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("✅ اتصلت بـ OpenAI")
            return True
        except Exception as e:
            logger.error(f"❌ خطأ في الاتصال بـ OpenAI: {e}")
            return False
    else:
        logger.warning("⚠️ OPENAI_API_KEY مش موجود")
        return False

def transcribe_audio(audio_file_path, language="ar"):
    """
    تحويل الصوت لنص باستخدام Whisper
    
    Args:
        audio_file_path: مسار الملف الصوتي
        language: لغة الملف (ar, en, إلخ)
    
    Returns:
        النص المحول أو None إذا فشل
    """
    if openai_client is None:
        logger.error("❌ OpenAI client مش متصل")
        return None
    
    try:
        with open(audio_file_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language
            )
        
        text = transcript.text.strip()
        logger.info(f"✅ تحويل صوت: {text[:50]}...")
        return text
        
    except Exception as e:
        logger.error(f"❌ خطأ في تحويل الصوت: {e}")
        return None

def text_to_speech(text, output_file_path="/tmp/response.mp3", voice="nova"):
    """
    تحويل النص لصوت باستخدام OpenAI TTS
    
    Args:
        text: النص المراد تحويله
        output_file_path: مسار ملف الـ MP3 الناتج
        voice: نوع الصوت (alloy, echo, fable, onyx, nova, shimmer)
    
    Returns:
        مسار الملف إذا نجح، None إذا فشل
    """
    if openai_client is None:
        logger.error("❌ OpenAI client مش متصل")
        return None
    
    try:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            language="ar"
        )
        
        # حفظ الملف
        with open(output_file_path, "wb") as f:
            f.write(response.content)
        
        logger.info(f"✅ تحويل نص لصوت: {text[:50]}... → {output_file_path}")
        return output_file_path
        
    except Exception as e:
        logger.error(f"❌ خطأ في تحويل النص لصوت: {e}")
        return None

def is_openai_available():
    """التحقق من توفر OpenAI"""
    return openai_client is not None

# تهيئة عند الاستيراد
init_openai()
