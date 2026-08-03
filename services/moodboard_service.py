# -*- coding: utf-8 -*-
"""
🎨 خدمة الـ Mood Board (2c -- دمج دور HOPE، ADR 0006)

بتولّد mood board احترافية بـ gpt-image-1 بناءً على الستايل والألوان
والخامات. توجيه أحمد الصريح (2026-08-04) محفور في بنية الـ prompt نفسها:
"المود بورد لازم تبقى مفيدة -- الخامات والـ color palette، والستايل
واضح فيها" -- يعني وثيقة شغل تتعرض على عميل، مش صورة حلوة:

  1. شريط palette بالألوان المطلوبة **بأساميها مكتوبة** (زي عينة التجربة
     اللي أحمد اعتمدها: Warm Greige / Soft Mint / Muted Mango).
  2. عينات الخامات هي بطلة اللوحة -- مساحة وحضور أكبر من الأكسسوارات.
  3. هوية الستايل باينة من التكوين نفسه، مش من كلام مكتوب.

التجربة اللي سبقت الكود ده: صورة واحدة بنفس البنية دي طلعت من أول
محاولة بجودة عرض-على-عميل (اعتمدها أحمد بالنص: "حلو اوى").
"""

import base64

from utils.logger import logger

# جودة high بـ 1536x1024 ≈ ربع دولار للصورة -- سعر عرض تقديمي كامل.
_IMAGE_MODEL = "gpt-image-1"
_IMAGE_SIZE = "1536x1024"
_IMAGE_QUALITY = "high"


def build_moodboard_prompt(style, colors, materials, notes=""):
    """يبني prompt الصورة ببنية 'وثيقة الشغل' الثابتة.

    Args:
        style: اسم الستايل (مثال: "Scandinavian-Bohemian")
        colors: قايمة ألوان أو نص -- كل لون هيظهر كـ swatch مُسمّى
        materials: قايمة خامات أو نص -- دي بطلة اللوحة
        notes: توجيهات إضافية اختيارية من أحمد
    """
    if isinstance(colors, (list, tuple)):
        colors = ", ".join(str(c) for c in colors)
    if isinstance(materials, (list, tuple)):
        materials = ", ".join(str(m) for m in materials)

    prompt = (
        "Professional interior design mood board, flat-lay collage on a "
        "clean white background, arranged like a real designer's physical "
        "presentation board for a client meeting. "
        f"Design style, clearly expressed through the objects and "
        f"composition themselves: {style}. "
        f"A labeled paint color palette strip with these colors as named "
        f"swatches: {colors} -- the color names written under each swatch "
        f"in small elegant type, and these are the ONLY words on the "
        f"board. "
        f"The dominant content of the board is real material samples, "
        f"larger and more prominent than any accessory: {materials} -- "
        f"each as a distinct physical sample (wood pieces, fabric "
        f"swatches, stone or ceramic tiles, metal finishes) with visible "
        f"texture. "
        "A few small style-defining accessories at most, never crowding "
        "the materials. Softly lit, photorealistic, high detail, elegant "
        "overlapping grid, no logos, no text anywhere except the palette "
        "labels."
    )
    if notes and str(notes).strip():
        prompt += " Additional direction: " + str(notes).strip()
    return prompt


def generate_mood_board(style, colors, materials, notes=""):
    """يولّد الصورة ويرجّع bytes بتاعتها، أو يرمي Exception لو فشل."""
    from services.openai_service import openai_client

    if openai_client is None:
        raise RuntimeError("OpenAI client مش متصل")

    prompt = build_moodboard_prompt(style, colors, materials, notes)
    logger.info("🎨 بتوليد mood board: " + str(style))
    response = openai_client.images.generate(
        model=_IMAGE_MODEL,
        prompt=prompt,
        size=_IMAGE_SIZE,
        quality=_IMAGE_QUALITY,
    )
    return base64.b64decode(response.data[0].b64_json)
