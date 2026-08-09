# -*- coding: utf-8 -*-
"""
🖋️ توقيع أحمد -- سجل قواعد الممارسة

التوقيع مش مرحلة في الماكينة، **التوقيع هو معايرة الماكينة** (التصور §3).
هو اللي بيخلي المخرج بتاع أحمد مش متوسط الإنترنت.

## ليه السجل في الكود مش في داتابيز

ده **معرفة تصميم**، مش داتا تشغيل: بتتغير نادر، وكل تغيير فيها يستاهل يتراجع
ويتشاف في الـ diff زي أي قرار معماري. لو بقت في جدول، هتتغير من غير أثر ومحدش
هيعرف ليه القاعدة اتبدلت. لما تكبر وتحتاج تعديل من الموبايل، تتنقل لجدول.

## المؤكد مقابل المقترح

`confirmed` = أحمد قالها بلسانه. **مفيش قاعدة تبقى confirmed غير كده.**
`proposed` = معرفة مهنية عامة مقترحة عليه، لسه مش جزء من توقيعه.
القاعدة المقترحة **بتتعرض كسؤال مش كحكم** -- نفس قاعدة الدستور
(CONSTITUTION.md §0): ادعاء بلا أساس ممنوع، والسؤال الصادق مسموح.

## applies_at -- القاعدة بتتفعل امتى

  brief      -- عند قراءة البريف
  layout     -- في التوزيع والحركة
  materials  -- عند اختيار الخامات
  lighting   -- في مخطط الإنارة
  execution  -- عند التنفيذ والتوريد
"""

CONFIRMED = "confirmed"
PROPOSED = "proposed"

# --------------------------------------------------------------------------
# السجل. الترتيب داخل كل فئة من الأعم للأخص.
# --------------------------------------------------------------------------
RULES = [
    # ===================== الفراغ والنسب =====================
    {
        "id": "separate_genders",
        "category": "الفراغ",
        "status": CONFIRMED,
        "captured": "2026-08-09",
        "text": "دايمًا بنحاول نفصل الولاد عن البنات",
        "why": "الفصل بيغير عدد الأوض المطلوبة، فلازم يتحدد في التوزيع مش بعد ما يتقفل.",
        "applies_at": "brief",
    },
    {
        "id": "main_corridor_90",
        "category": "الفراغ",
        "status": PROPOSED,
        "text": "ممر الحركة الرئيسي ٩٠ سم على الأقل، والثانوي ٦٠",
        "why": "أقل من كده الفراغ بيتعب في الاستعمال اليومي حتى لو باين واسع في المخطط.",
        "applies_at": "layout",
    },
    {
        "id": "dining_clearance_90",
        "category": "الفراغ",
        "status": PROPOSED,
        "text": "حوالين السفرة ٩٠ سم صافي عشان الكرسي يترجع وحد يعدي وراه",
        "why": "دي المسافة اللي بتفرق بين سفرة بتشتغل في العزومة وسفرة بتتقفل.",
        "applies_at": "layout",
    },
    {
        "id": "sofa_table_gap",
        "category": "الفراغ",
        "status": PROPOSED,
        "text": "بين الكنبة وترابيزة الوسط ٤٠ لـ ٤٥ سم",
        "why": "أقل بتزنق الرجلين، وأكتر بتخلي الترابيزة بعيدة عن الإيد.",
        "applies_at": "layout",
    },
    {
        "id": "one_empty_wall",
        "category": "الفراغ",
        "status": PROPOSED,
        "text": "حيطة واحدة على الأقل تفضل فاضية تمامًا في كل فراغ",
        "why": "الفراغ اللي كل حيطانه مشغولة بيبقى متعب مهما كانت الخامات حلوة.",
        "applies_at": "layout",
    },
    {
        "id": "entrance_storage",
        "category": "الفراغ",
        "status": PROPOSED,
        "text": "المدخل لازم يبقى فيه تخزين — معاطف وشنط وأحذية",
        "why": "غيابه بيظهر بعد السكن على طول، وبيتحل بحلول وحشة.",
        "applies_at": "layout",
    },
    {
        "id": "guest_path_separate",
        "category": "الفراغ",
        "status": PROPOSED,
        "text": "باب الشقة ميفتحش على قعدة الضيوف مباشرة",
        "why": "السترة مش رفاهية في البيت المصري، وحلها في التوزيع مش بستارة.",
        "applies_at": "layout",
    },

    # ===================== النور =====================
    {
        "id": "kelvin_3000",
        "category": "النور",
        "status": PROPOSED,
        "text": "٣٠٠٠ كلفن في البيت كله، مفيش استثناء",
        "why": "اختلاف حرارة اللون بين أوضة وأوضة بيبان فورًا وبيخلي الخامات تقرا غلط.",
        "applies_at": "lighting",
    },
    {
        "id": "three_light_layers",
        "category": "النور",
        "status": PROPOSED,
        "text": "تلات طبقات إنارة في أي فراغ رئيسي: عام، مهام، إبرازي",
        "why": "الإنارة الواحدة بتخلي الفراغ مسطح ومبيشتغلش بالليل.",
        "applies_at": "lighting",
    },
    {
        "id": "hidden_source",
        "category": "النور",
        "status": PROPOSED,
        "text": "مصدر النور مخفي — الوحدة نفسها متتشافش",
        "why": "الوحدة الظاهرة بتسحب العين من التصميم وبتعمل وهج.",
        "applies_at": "lighting",
    },
    {
        "id": "sample_under_project_light",
        "category": "النور",
        "status": PROPOSED,
        "text": "العينة تتشاف تحت إضاءة المشروع قبل الاعتماد",
        "why": "نفس البيج بيقرا وردي تحت ٢٧٠٠ ورمادي تحت ٤٠٠٠ — والاعتماد تحت نور المعرض كذبة.",
        "applies_at": "materials",
    },

    # ===================== الخامات =====================
    {
        "id": "rough_beside_smooth",
        "category": "الخامات",
        "status": PROPOSED,
        "text": "كل خامة ناعمة جنبها خامة خشنة في نفس المدى",
        "why": "التباين الملمسي هو اللي بيدي الفراغ عمق من غير ما يزود ألوان.",
        "applies_at": "materials",
    },
    {
        "id": "max_three_woods",
        "category": "الخامات",
        "status": PROPOSED,
        "text": "أقصى درجتين خشب في الفراغ الواحد",
        "why": "التلاتة بتخلي الفراغ مبعثر، والعين بتقراها كخطأ مش كتنوع.",
        "applies_at": "materials",
    },
    {
        "id": "brass_not_steel",
        "category": "الخامات",
        "status": PROPOSED,
        "text": "النحاس المطفي بدل الاستانلس في التفاصيل",
        "why": "الاستانلس بارد وبيبوظ دفا الفراغ، والنحاس بيكبر معاه.",
        "applies_at": "materials",
    },
    {
        "id": "touched_beats_seen",
        "category": "الخامات",
        "status": PROPOSED,
        "text": "اللي بيتلمس أعلى درجة من اللي بيتشاف — المقابض والحواف والدرابزين",
        "why": "جودة البيت بتتحكم عليها باليد قبل العين، والتوفير هنا بيتحس كل يوم.",
        "applies_at": "materials",
    },
    {
        "id": "maintenance_before_beauty",
        "category": "الخامات",
        "status": PROPOSED,
        "text": "الخامة الفاتحة متتحطش في بيت فيه عيال أو حيوانات من غير ما يتقال",
        "why": "الجمال اللي مبيتنضفش بيتكره في شهرين، والعميل بينسى إنه اختاره.",
        "applies_at": "materials",
    },

    # ===================== الأرضيات والسقف =====================
    {
        "id": "one_continuous_floor",
        "category": "الأرضيات",
        "status": PROPOSED,
        "text": "أرضية واحدة مستمرة في المناطق المفتوحة",
        "why": "تغيير الأرضية بيقطّع الفراغ ويخليه يبان أصغر.",
        "applies_at": "materials",
    },
    {
        "id": "brass_threshold",
        "category": "الأرضيات",
        "status": PROPOSED,
        "text": "فاصل نحاس ٤ مم عند أي تغيير خامة في الأرضية",
        "why": "نقطة الالتقاء هي اللي بتفرق المحترف عن الهاوي.",
        "applies_at": "execution",
    },
    {
        "id": "grain_along_longest",
        "category": "الأرضيات",
        "status": PROPOSED,
        "text": "اتجاه العروق موازي لأطول ضلع في الفراغ",
        "why": "بيمد الفراغ بصريًا وبيقلل القطع.",
        "applies_at": "execution",
    },
    {
        "id": "no_full_drop_ceiling",
        "category": "السقف",
        "status": PROPOSED,
        "text": "مفيش سقف معلق كامل — نزلة محيطية بس",
        "why": "السقف الكامل بياكل من الارتفاع الصافي وبيخنق الفراغ.",
        "applies_at": "layout",
    },
    {
        "id": "min_clear_height",
        "category": "السقف",
        "status": PROPOSED,
        "text": "الارتفاع الصافي مينزلش عن ٢.٦٠ بعد كل النزلات والمجاري",
        "why": "التكييف وبيت الستارة والنزلة بياكلوا من بعض من غير ما حد ياخد باله.",
        "applies_at": "layout",
    },

    # ===================== المطبخ =====================
    {
        "id": "counter_height_from_user",
        "category": "المطبخ",
        "status": PROPOSED,
        "text": "ارتفاع سطح العمل يتحسب من طول اللي بيطبخ، مش من المقاس القياسي",
        "why": "المطبخ بيتصمم لواحد بعينه، والقياسي بيوجع ضهره كل يوم.",
        "applies_at": "layout",
    },
    {
        "id": "kitchen_before_appliances",
        "category": "المطبخ",
        "status": PROPOSED,
        "text": "الأجهزة بمقاساتها تتحدد قبل رسم الوحدات",
        "why": "جهاز واحد ناقص من الجرد = خزانة بتتكسر بعد التركيب.",
        "applies_at": "layout",
    },

    # ===================== الكهربا والتنفيذ =====================
    {
        "id": "no_socket_behind_fixed",
        "category": "الكهربا",
        "status": PROPOSED,
        "text": "مفيش بريزة ورا أثاث ثابت",
        "why": "البريزة اللي مبتوصلهاش بريزة ميتة، وبتتكتشف بعد ما الحيطة تتقفل.",
        "applies_at": "layout",
    },
    {
        "id": "single_batch",
        "category": "التنفيذ",
        "status": PROPOSED,
        "text": "أي خامة تتطلب من تشغيلة واحدة",
        "why": "نفس البلاطة من تشغيلتين بتطلع لونين، وبيبان بعد الفرش.",
        "applies_at": "execution",
    },
    {
        "id": "long_lead_first",
        "category": "التنفيذ",
        "status": PROPOSED,
        "text": "اللي مدته أطول يتطلب الأول مهما كان سعره",
        "why": "أشهر سبب تأخير في التشطيبات مش الفلوس، ده بند اتطلب متأخر.",
        "applies_at": "execution",
    },
]

# --------------------------------------------------------------------------
# قراءة
# --------------------------------------------------------------------------

_BY_ID = {r["id"]: r for r in RULES}


def get(rule_id):
    return _BY_ID.get(rule_id)


def confirmed():
    return [r for r in RULES if r["status"] == CONFIRMED]


def proposed():
    return [r for r in RULES if r["status"] == PROPOSED]


def by_stage(stage):
    return [r for r in RULES if r.get("applies_at") == stage]


def categories():
    """الفئات بترتيب أول ظهور -- الترتيب في RULES مقصود."""
    out = []
    for r in RULES:
        if r["category"] not in out:
            out.append(r["category"])
    return out


def format_signature():
    """عرض التوقيع لتليجرام: المؤكد أولًا، والمقترح كسؤال مش كحكم."""
    conf, prop = confirmed(), proposed()
    out = [f"🖋️ توقيعك — {len(conf)} مؤكدة و{len(prop)} مقترحة"]

    if conf:
        out.append("\n✅ قواعدك (قلتها بلسانك):")
        for r in conf:
            out.append(f"• {r['text']}")
            out.append(f"   ↳ {r['why']}")

    if prop:
        out.append("\n❔ مقترحة — مش جزء من توقيعك لحد ما تأكدها:")
        cur = None
        for r in prop:
            if r["category"] != cur:
                cur = r["category"]
                out.append(f"\n— {cur} —")
            out.append(f"• [{r['id']}] {r['text']}")
            out.append(f"   ↳ {r['why']}")

    out.append("\nقول لي «أكد <id>» أو «امسح <id>» أو عدّل الصيغة بلسانك.")
    return "\n".join(out)
