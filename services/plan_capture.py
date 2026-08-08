# -*- coding: utf-8 -*-
"""
📐➜📁 إمساك البلان: اللي آدم قراه يفضل موجود بدل ما يقع على الأرض.

الفجوة اللي الملف ده بيسدها (تشخيص 2026-08-08): آدم بيقرا البلانات كويس
من زمان -- `analyze_plan_pdf` بيطلع اسم المشروع والموقع وأسماء الفراغات
وأبعادها، ومجرّب على بلان حقيقي. وبعدين بيبعت الجدول في تليجرام
و**يتنسى**. آخر سطر في المسار كان `bot.reply_to(...)` وبس.

النتيجة اللي بانت في قاعدة البيانات: 5,139 حدث آدم بيسجّل بيهم نفسه،
مقابل ملف مشروع واحد. مش لأن أحمد مش بيدخّل بيانات -- لأن اللي بيدخّله
مبيتمسكش.

فالملف ده مش أداة جديدة. هو **خط بين قارئ موجود ومُخزّن موجود**:

    analyze_plan_pdf (موجود)  ->  [هنا]  ->  save_project_fact (موجود)

## ليه تمريرتين بدل واحدة

التهيكِل بيشتغل على **النص اللي طلع من القراءة**، مش على البلان نفسه.
ده مش ترتيب عشوائي -- هو الضمان الأساسي في التصميم ده: المُهيكِل مشايف
الرسمة أصلاً، فمش قادر فيزيائيًا يقرا بُعد القارئ مقالوش. أي رقم بيوصل
للتخزين لازم يكون عدّى على قاعدة "متخمنش رقم أبدًا" بتاعت القراءة الأصلية.

والفايدة التانية: القراءة الأصلية متتلمسش. هي متجرّبة وشغالة، وأي عطل
هنا بيرجّع None فأحمد بياخد قراءته زي ما هي.

## المصدر مش "أحمد"

كل حقيقة بتتخزن هنا مصدرها `"plan"` مش `"ahmed"`. ده مش تفصيلة إدارية --
أحمد مقالش الأرقام دي، **موديل قراها من رسمة**. فبتتعرض متعلّمة إنها
مستخرجة ولسه مش مراجَعة، وآدم مايتكلمش عنها كأنها حقيقة مؤكدة. نفس
القاعدة اللي في كل حتة في النظام: مش عارف ≠ صفر، ومستخرَج ≠ مؤكد.
"""

import json

from utils.logger import logger

# القيم اللي معناها "القارئ مقدرش يقرا ده" -- بتتحول لـ None مش لنص.
# لو دخلت التخزين كنص هتبقى حقيقة مكتوبة عن حاجة مش معروفة، وده بالظبط
# الفخ اللي النظام كله متبني على تفاديه.
_UNKNOWN_MARKERS = {"مش واضح", "غير واضح", "مش معروف", "unknown", "n/a", "na", "-", ""}

# اسم مشروع أطول من كده غالبًا جملة اتقريت غلط مش اسم
_MAX_NAME_CHARS = 60


PLAN_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "project_name": {"type": ["string", "null"]},
        "location": {"type": ["string", "null"]},
        "drawing_date": {"type": ["string", "null"]},
        "drawing_number": {"type": ["string", "null"]},
        "rooms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "dimensions": {"type": ["string", "null"]},
                },
                "required": ["name", "dimensions"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "project_name", "location", "drawing_date",
        "drawing_number", "rooms", "notes",
    ],
    "additionalProperties": False,
}


STRUCTURING_PROMPT = (
    "النص اللي جاي ده ناتج قراءة بلان معماري. حوّله لبيانات منظّمة "
    "**من غير ما تضيف أي حاجة مش مكتوبة فيه**.\n\n"
    "قواعد ملزمة:\n"
    "- أي خانة النص قال عنها 'مش واضح' أو مذكرهاش خالص -> null. "
    "متستنتجش ومتخمنش.\n"
    "- الأبعاد انقلها **بنص الأرقام زي ما هي** (مثلاً '4.20 × 3.15'). "
    "متحسبش مساحات ومتحوّلش وحدات -- الحساب بيتعمل بعدين بالكود.\n"
    "- أسماء الفراغات زي ما هي مكتوبة في النص حرفيًا.\n"
    "- لو النص ذكر إن تسمية فراغ استنتاجية، سيبها بس ضيف الملاحظة دي "
    "في notes.\n"
    "- لو النص مش ناتج بلان أصلاً، رجّع كل الخانات null و rooms فاضية."
)

_CAPTION_RULE = (
    "\n\nأحمد بعت البلان ومعاه التعليق ده: «{caption}»\n"
    "لو اسم المشروع **مش موجود في اللوحة**، شوف التعليق: لو فيه اسم "
    "مشروع أو عميل فعلاً (زي «بلان شقة مدحت») خده. لكن لو التعليق طلب أو "
    "سؤال أو تحية (زي «بص عليه وقوللي رأيك») يبقى مفيش اسم -> null. "
    "التعليق رسالة لك، مش عنوان -- متحوّلش كلام أحمد لاسم ملف.\n"
    "ولو خدت الاسم من التعليق، شيل الكلام الزيادة حواليه: «بلان شقة مدحت» "
    "-> «شقة مدحت». الاسم ده هيفضل معرّف الملف سنين."
)


# ============================================================
# منطق pure (بدون I/O ولا شبكة) -- ده اللي الاختبارات بتمسكه
# ============================================================

def clean_value(value):
    """يرجّع النص منضّف، أو None لو معناه 'مش معروف'."""
    text = " ".join(str(value or "").split())
    if text.casefold() in _UNKNOWN_MARKERS:
        return None
    return text or None


def pick_project_name(structured):
    """اسم المشروع اللي الملف هيتسجل عليه، أو None لو مفيش.

    الاسم بيتحدد في التهيكِل (من اللوحة، أو من تعليق أحمد لو كان اسم
    فعلاً) -- الدالة دي بوابة أخيرة بس. **مفيش اختراع** ومفيش تخمين من
    التعليق هنا: ملف باسم "بص عليه وقوللي رأيك" تلوث دايم في قاعدة عمرها
    ما هتتنضف، وسؤال أحمد عن الاسم أرخص بكتير.

    الحد الأقصى للطول مش تعريف للاسم -- هو حزام أمان لو التهيكِل رجّع
    جملة كاملة رغم التعليمات (اتكتب بعد ما اختبار كشف إن جملة من 57 حرف
    كانت هتعدي كاسم مشروع، 2026-08-08).
    """
    name = clean_value((structured or {}).get("project_name"))
    if name and len(name) <= _MAX_NAME_CHARS:
        return name
    if name:
        logger.warning("⚠️ اسم مشروع طويل جدًا من البلان -- اتجاهل: " + name[:70])
    return None


def facts_from_structured(structured):
    """يحوّل البيانات المنظّمة لقايمة (فئة، مفتاح، قيمة) جاهزة للتخزين.

    التوزيع على الفئات الموجودة في `project_file_service.CATEGORIES`:

      - فراغ **بأبعاد**    -> "أبعاد"    (عشان `computed_area` تحسب المساحة
                                          حتميًا من الأرقام المكتوبة)
      - فراغ **من غير أبعاد** -> "فراغات" (الاسم معلومة حقيقية لوحده؛
                                          غياب البعد بيتقال صراحة)
      - الموقع/التاريخ/رقم اللوحة -> "ملاحظات"
      - ملاحظات البلان            -> "ملاحظات"

    الفراغ اللي مالوش اسم بيتتخطى -- مفتاح فاضي مش حقيقة.
    """
    data = structured or {}
    facts = []

    for label, key in (
        ("الموقع", "location"),
        ("تاريخ اللوحة", "drawing_date"),
        ("رقم اللوحة", "drawing_number"),
    ):
        value = clean_value(data.get(key))
        if value:
            facts.append(("ملاحظات", label, value))

    for room in data.get("rooms") or []:
        if not isinstance(room, dict):
            continue
        name = clean_value(room.get("name"))
        if not name:
            continue
        dims = clean_value(room.get("dimensions"))
        if dims:
            facts.append(("أبعاد", name, dims))
        else:
            facts.append(("فراغات", name, "الفراغ موجود في البلان -- الأبعاد مش واضحة"))

    for index, note in enumerate(data.get("notes") or [], start=1):
        value = clean_value(note)
        if value:
            facts.append(("ملاحظات", "من البلان " + str(index), value))

    return facts


def summarize_capture(project_name, facts, saved_count):
    """السطر اللي أحمد بيقراه بعد ما البلان يتحفظ. أرقام محسوبة مش موصوفة."""
    rooms = sum(1 for category, _, _ in facts if category in ("أبعاد", "فراغات"))
    with_dims = sum(1 for category, _, _ in facts if category == "أبعاد")
    line = (
        "📁 حفظته في ملف مشروع «" + project_name + "»: "
        + str(rooms) + " فراغ (" + str(with_dims) + " بأبعاد مكتوبة)"
    )
    if saved_count < len(facts):
        line += " -- " + str(len(facts) - saved_count) + " بند مقدرتش أحفظه"
    return line + ".\nالبيانات دي **مستخرجة من البلان ولسه مش مراجعة منك** -- "


# ============================================================
# التهيكِل (نداء واحد رخيص على النص) والتخزين
# ============================================================

def structure_plan_text(plan_text, caption=""):
    """يحوّل نص القراءة لبيانات منظّمة متحقّقة. None لو فشل.

    نداء واحد صغير: الدخل نص القراءة (مش البلان)، والخرج JSON مقيّد
    بالـ schema فمفيش parsing هش. الفشل هنا مش كارثة -- أحمد بياخد
    قراءته عادي والمسودة بس هي اللي مبتتحفظش.

    التعليق بيتبعت معاه عشان يحكم عليه: "بلان شقة مدحت" فيه اسم،
    "بص عليه وقوللي رأيك" مفيهوش. الحكم ده مش بيتعمل بعدّ الحروف.
    """
    if not str(plan_text or "").strip():
        return None
    try:
        from services.claude_service import _tracked_create, CLAUDE_MODEL

        instructions = STRUCTURING_PROMPT
        clean_caption = clean_value(caption)
        if clean_caption:
            instructions += _CAPTION_RULE.format(caption=clean_caption[:200])

        response = _tracked_create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            thinking={"type": "disabled"},
            output_config={
                "format": {"type": "json_schema", "schema": PLAN_JSON_SCHEMA}
            },
            messages=[{
                "role": "user",
                "content": instructions + "\n\n---\n" + str(plan_text),
            }],
        )
        payload = "".join(b.text for b in response.content if b.type == "text")
        return json.loads(payload)
    except Exception as e:
        logger.warning("⚠️ تهيكِل البلان فشل (القراءة نفسها مش متأثرة): " + str(e)[:120])
        return None


def capture_plan(plan_text, caption=""):
    """يمسك بلان اتقرا ويحفظه كمسودة مشروع. بيرجع سطر لأحمد أو None.

    None معناها "مفيش حاجة تتقال" -- إما التهيكِل فشل أو مفيش فراغات.
    """
    structured = structure_plan_text(plan_text, caption)
    if not structured:
        return None

    facts = facts_from_structured(structured)
    if not facts:
        return None

    project_name = pick_project_name(structured)
    if not project_name:
        # الاسم مش معروف -- بنسأل بدل ما نخترع ملف مايتلاقاش تاني
        return (
            "📐 قريت البلان بس **اسم المشروع مش واضح فيه**، فمحفظتوش. "
            "قوللي الاسم وابعته تاني وأنا أمسكه."
        )

    from services import project_file_service as pfs

    saved = 0
    reasons = []
    for category, key, value in facts:
        try:
            result = pfs.save_project_fact(project_name, category, key, value, source="plan")
            if str(result).startswith("اتسجلت"):
                saved += 1
            else:
                reasons.append(str(result))
        except Exception as e:
            logger.error("❌ حفظ حقيقة من البلان فشل (" + str(key) + "): " + str(e)[:90])
            reasons.append("الحفظ فشل: " + str(e)[:60])

    if saved == 0:
        # كان بيرجع None، و None معناها "مفيش حاجة تتقال" -- فأحمد كان
        # بياخد قراءة البلان ومايعرفش إن **ولا حرف اتحفظ**. وأشهر سبب هو
        # فرع متوقع أصلًا: اسم المشروع بيطابق أكتر من ملف، فكل حقيقة
        # بترجع سؤال الالتباس. الفشل الكامل لازم يتقال (مراجعة 2026-08-08).
        if not reasons:
            return None
        first = reasons[0]
        if "أكتر من مشروع" in first:
            return "📐 قريت البلان بس **محفظتوش**: " + first
        return ("📐 قريت البلان بس **مقدرتش أحفظ منه حاجة** — " + first[:120]
                + "\nابعته تاني كمان شوية أو قوللي أسجّل الأبعاد بإيدي.")

    logger.info("📐➜📁 بلان اتمسك: " + project_name + " -- " + str(saved) + " بند")
    return summarize_capture(project_name, facts, saved) + "قول «ملف " + project_name + "» أي وقت تشوفه."
