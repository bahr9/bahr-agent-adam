# -*- coding: utf-8 -*-
"""
📐 قراءة DXF الحتمية (الشريحة الأولى -- قرار أحمد 2026-08-04)

الفرق الجوهري عن مسار الـ PDF البصري: ملف DXF بيتقري **رياضيًا** --
إحداثيات وقياسات ككائنات، مش بيكسلات بيتخمنها فيجن. القدرات هنا:
- استخراج الـ title block والنصوص والقياسات (DIMENSION) بقيمها الفعلية
- التعرف التلقائي على المشروع من نصوص اللوحة (owner / compound ...)
- فحص اتساق: مقارنة أبعاد ملف المشروع المسجلة بقياسات الرسم

الشريحة التانية (قرار أحمد 2026-08-04 الصبح): ربط كل قياس مرسوم
بالفراغ بتاعه عن طريق **أقرب عنصر مسمى** (كتلة toilet، نص dish
washer، كتلة tasri7a...) -- حساب مسافات إقليدية بحت، مش رؤية. الربط
بيتقدم كترشيح بالموقع، والتثبيت في ملف المشروع بيفضل بكلمة أحمد.

اللي لسه مش هنا: تجميع حدود الأوض من خطوط الحوائط (topology) لحساب
المساحات من الجيومتري مباشرة -- شريحة تالتة لو اتطلبت.

التجربة الأصلية على furniture plan.dxf الحقيقي بتاع Rock Eden لقت
تعارضًا مرشحًا من أول تشغيلة (3.79 في الرسم) اتحسم بكلمة أحمد (ضلع
المطبخ) -- النمط المقصود: الأداة بتعرض وتسأل، أحمد بيحسم.
"""

import re
from collections import Counter

from utils.logger import logger

# سماحية المطابقة بين الرقم المسجل والقياس المرسوم: انحرافات الرسم
# الفعلية اللي شفناها (3.70027 مقابل 3.70) في حدود مليمترات.
MATCH_TOLERANCE_M = 0.02

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩٫", "0123456789.")

# INSUNITS -> معامل تحويل للمتر (اللي مش هنا = وحدات غير محسومة)
_UNIT_FACTORS = {6: 1.0, 5: 0.01, 4: 0.001}

# أقصى مسافة (بالمتر) بين قياس وعنصر مسمى عشان نرشح إنهم لنفس الفراغ.
ANCHOR_RADIUS_M = 3.0

# أسماء المراسي المعروفة -> اسم الفراغ بالعربي. اللي مش في القاموس
# بيتعرض باسمه الخام بأمانة ("جنب كتلة ...") -- مش بيتخفى ولا بيتخمن.
_ANCHOR_LABELS = (
    (("dish washer", "washing machine", "magic corner", "sink"), "المطبخ"),
    (("tasri7a", "dressing"), "التصريحة (الدريسنج)"),
    (("toilet", "wc", "bathtub", "shower"), "الحمام"),
    (("bed",), "أوضة نوم"),
    (("sofa",), "الريسبشن/المعيشة"),
)

# عناصر مش بتنفع مراسي: الأبواب والشبابيك قاعدين على الحيطة *بين*
# فراغين -- الربط بيهم بيضلل. والإطارات title block مش فراغ أصلًا.
_NON_ANCHOR_LAYERS = ("DOOR", "WIN", "GLASS", "FRAMES")
_NON_ANCHOR_NAMES = ("door", "window", "w60", "frame")


# ============================================================
# منطق pure (بدون ezdxf) -- قابل للاختبار مباشرة
# ============================================================

def extract_recorded_dims(project_doc):
    """أرقام الأبعاد المسجلة في ملف المشروع: [(اسم الفراغ, [أرقام]), ...]"""
    out = []
    entries = (project_doc or {}).get("facts", {}).get("أبعاد", {}) or {}
    for key in sorted(entries):
        entry = entries[key]
        value = entry.get("value", "") if isinstance(entry, dict) else str(entry)
        numbers = [float(n) for n in _NUMBER.findall(str(value).translate(_ARABIC_INDIC))]
        if numbers:
            out.append((key, numbers))
    return out


def consistency_check(recorded_dims, drawing_values, tolerance=MATCH_TOLERANCE_M):
    """يطابق كل رقم مسجل مع أقرب قياس مرسوم.

    بيرجع (rows, unmatched_drawing):
      rows: [(فراغ, رقم مسجل, حالة)] والحالة "match" / "match_deviation" /
            "not_in_drawing" (مع القيمة المرسومة لو فيه)
      unmatched_drawing: قياسات مرسومة محدش من المسجل طابقها
    """
    # كل قياس مرسوم بيتستهلك مرة واحدة بس، والأقرب بياخده الأول --
    # الدرس من لوحة Rock Eden الحقيقية: 3.79 المرسومة بتاعة المطبخ
    # (تطابق تام)، فممنوع الماستر 3.78 ياخدها كمان كتطابق تقريبي.
    targets = [
        (room, num) for room, numbers in recorded_dims for num in numbers
    ]
    candidates = sorted(
        (abs(dv - num), t_idx, d_idx)
        for t_idx, (_, num) in enumerate(targets)
        for d_idx, dv in enumerate(drawing_values)
        if abs(dv - num) <= tolerance
    )
    assigned = {}
    used = set()
    for diff, t_idx, d_idx in candidates:
        if t_idx in assigned or d_idx in used:
            continue
        assigned[t_idx] = (diff, d_idx)
        used.add(d_idx)

    rows = []
    for t_idx, (room, num) in enumerate(targets):
        if t_idx not in assigned:
            rows.append((room, num, "not_in_drawing", None))
        else:
            diff, d_idx = assigned[t_idx]
            status = "match" if diff < 0.001 else "match_deviation"
            rows.append((room, num, status, drawing_values[d_idx]))
    unmatched = [dv for i, dv in enumerate(drawing_values) if i not in used]
    return rows, unmatched


def label_for_anchor(raw_name):
    """اسم الفراغ بالعربي لو المرساة معروفة، وإلا None (يتعرض خام)."""
    lowered = str(raw_name or "").casefold()
    for keywords, label in _ANCHOR_LABELS:
        if any(k in lowered for k in keywords):
            return label
    return None


def is_usable_anchor(name, layer):
    """هل العنصر ده ينفع مرساة فراغ؟ (مش باب/شباك/إطار/مجهول النجمة)"""
    name_l, layer_u = str(name or "").casefold(), str(layer or "").upper()
    if name_l.startswith("*") or not name_l.strip():
        return False
    if any(part in layer_u for part in _NON_ANCHOR_LAYERS):
        return False
    return not any(part in name_l for part in _NON_ANCHOR_NAMES)


def associate_dims_to_anchors(positioned_dims, anchors, radius=ANCHOR_RADIUS_M):
    """يرشح فراغ كل قياس بأقرب مرساة مسماة ليه (مسافة إقليدية بحت).

    positioned_dims: [(قيمة, x, y)] -- anchors: [(اسم, x, y)]
    بيرجع (groups, unassigned): groups بترتيب الاسم المعروض، والمراسي
    اللي بتترجم لنفس الفراغ العربي بتتلم في مجموعة واحدة.
    """
    groups = {}
    unassigned = []
    for value, dx, dy in positioned_dims:
        best_name, best_dist = None, None
        for name, ax, ay in anchors:
            dist = ((dx - ax) ** 2 + (dy - ay) ** 2) ** 0.5
            if dist <= radius and (best_dist is None or dist < best_dist):
                best_name, best_dist = name, dist
        if best_name is None:
            unassigned.append(value)
        else:
            display = label_for_anchor(best_name) or ("جنب كتلة " + str(best_name))
            groups.setdefault(display, []).append(value)
    return {k: sorted(v) for k, v in sorted(groups.items())}, sorted(unassigned)


def infer_project_from_texts(texts, existing_names):
    """يتعرف على المشروع من نصوص اللوحة (owner / compound / اسم الوحدة).

    اسم المشروع بيتقسم لمقاطع (على "-") وكل مقطع بيتدور عليه جوه
    النصوص. أعلى اسم في عدد الإصابات بيكسب؛ التعادل بين مشروعين
    مختلفين = None (متخمنش هوية مشروع أبدًا -- درس هوب).
    """
    haystack = " | ".join(" ".join(str(t or "").split()).casefold() for t in texts)
    scores = {}
    for name in existing_names:
        fragments = [
            " ".join(f.split()).casefold()
            for f in str(name).replace("_", "-").split("-")
        ]
        hits = sum(1 for f in fragments if len(f) >= 4 and f in haystack)
        if hits:
            scores[name] = hits
    if not scores:
        return None
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


def format_dxf_report(data, project_name=None, rows=None, unmatched=None):
    """تقرير عربي مقروء من بيانات الاستخراج + فحص الاتساق لو اتعمل."""
    lines = ["📐 قراءة رياضية للوحة (مش تخمين بصري):"]

    if data.get("unit_factor") is None:
        lines.append("⚠️ وحدات الرسم غير محسومة في الملف -- الأرقام معروضة زي ما هي بدون تحويل.")
    title_texts = [t for t in data.get("texts", []) if t.strip()][:8]
    if title_texts:
        lines.append("")
        lines.append("نصوص اللوحة (أول " + str(len(title_texts)) + "): " + " | ".join(title_texts))

    dims = data.get("dim_values", [])
    lines.append("")
    if dims:
        lines.append("قياسات مرسومة ككائنات (" + str(len(dims)) + "): "
                     + "، ".join(f"{d:.2f}" for d in sorted(dims)))
    else:
        lines.append("مفيش كائنات قياس (DIMENSION) في اللوحة -- الجيومتري نفسه لسه بيحمل الأطوال، بس استخراجها من الحوائط شريحة جاية.")

    lines.append("عناصر: أبواب " + str(data.get("door_count", 0))
                 + " | شبابيك " + str(data.get("window_count", 0))
                 + " | طبقات " + str(len(data.get("layer_census", {}))))

    # الشريحة التانية: تسمية القياسات. المعرفة المثبتة أولًا --
    # القياس اللي بيطابق بُعد مسجل في ملف المشروع بياخد اسم فراغه
    # المؤكد (لوحة Rock Eden علّمتنا: الـ 3.79 بتاعة المطبخ بكلمة
    # أحمد، وكتلة الـ toilet أقرب ليها مكانيًا -- القرب بيضلل على
    # حدود الفراغات). الترشيح المكاني للقياسات المجهولة بس.
    positioned = data.get("positioned_dims", [])
    anchor_list = data.get("anchors", [])
    if positioned and anchor_list:
        confirmed_by_value = {}
        for room, _, status, drawn in (rows or []):
            if status in ("match", "match_deviation") and drawn is not None:
                confirmed_by_value[round(drawn, 4)] = room

        confirmed_groups = {}
        unknown_positioned = []
        for value, dx, dy in positioned:
            room = confirmed_by_value.get(round(value, 4))
            if room:
                confirmed_groups.setdefault(room, []).append(value)
            else:
                unknown_positioned.append((value, dx, dy))

        groups, unassigned = associate_dims_to_anchors(unknown_positioned, anchor_list)
        if confirmed_groups or groups:
            lines.append("")
            lines.append("تسمية القياسات:")
            for room in sorted(confirmed_groups):
                lines.append("  ✓ " + room + ": "
                             + "، ".join(f"{v:.2f}" for v in sorted(confirmed_groups[room]))
                             + " -- مثبت من ملف المشروع")
            for label, values in groups.items():
                lines.append("  ~ " + label + ": " + "، ".join(f"{v:.2f}" for v in values)
                             + " -- ترشيح بالموقع (أقرب عنصر مسمى)")
            if unassigned:
                lines.append("  ؟ بعيدة عن أي عنصر مسمى: "
                             + "، ".join(f"{v:.2f}" for v in unassigned))
            if groups or unassigned:
                lines.append("(الترشيحات مش تأكيد -- لو صح قول مثلًا \"سجل التصريحة 2.83×1.17\" وأثبتها في ملف المشروع)")

    if project_name:
        lines.append("")
        lines.append("🎯 اتعرفت على المشروع من اللوحة: " + project_name)
        if rows:
            lines.append("فحص الاتساق (المسجل في الملف مقابل المرسوم):")
            for room, num, status, drawn in rows:
                if status == "match":
                    lines.append(f"  ✓ {room}: {num:g} -- مطابق تمامًا")
                elif status == "match_deviation":
                    lines.append(f"  ✓ {room}: {num:g} -- مطابق (المرسوم {drawn:.3f}، انحراف مليمترات)")
                else:
                    lines.append(f"  ○ {room}: {num:g} -- مش من ضمن القياسات المرسومة (مش تعارض -- ممكن بس مالوش dimension في اللوحة دي)")
            if unmatched:
                lines.append("قياسات مرسومة مالهاش مقابل مسجل: "
                             + "، ".join(f"{d:.2f}" for d in sorted(unmatched))
                             + " -- لو حابب أسجل أي واحد فيهم لفراغ معين قولي.")
    else:
        lines.append("")
        lines.append("معرفتش أربط اللوحة بمشروع مسجل -- قولي اسم المشروع وأعمل فحص الاتساق.")

    return "\n".join(lines)


# ============================================================
# قشرة ezdxf الرفيعة (I/O)
# ============================================================

def extract_plan_geometry(file_path):
    """يقرا DXF ويرجع dict بيانات جاهزة للمنطق الـ pure."""
    import ezdxf

    doc = ezdxf.readfile(file_path)
    msp = doc.modelspace()

    unit_factor = _UNIT_FACTORS.get(doc.header.get("$INSUNITS", 0))

    texts = []
    for e in msp:
        if e.dxftype() == "TEXT":
            texts.append(e.dxf.text)
        elif e.dxftype() == "MTEXT":
            texts.append(e.plain_text().replace("\n", " / "))

    dim_values = []
    positioned_dims = []
    for e in msp.query("DIMENSION"):
        try:
            value = float(e.get_measurement())
        except Exception:
            continue
        if unit_factor:
            value *= unit_factor
        value = round(value, 4)
        dim_values.append(value)
        try:
            dp = e.dxf.defpoint
            positioned_dims.append((value, float(dp[0]), float(dp[1])))
        except Exception:
            pass

    # المراسي: كتل INSERT + نصوص جوه الرسم (أسماء أجهزة/فراغات) --
    # القياس بيترشح لأقرب واحدة ليه جوه نصف القطر
    anchors = []
    for e in msp.query("INSERT"):
        if is_usable_anchor(e.dxf.name, e.dxf.layer):
            p = e.dxf.insert
            anchors.append((e.dxf.name, float(p[0]), float(p[1])))
    for e in msp:
        if e.dxftype() == "TEXT" and str(e.dxf.text or "").strip():
            p = e.dxf.insert
            anchors.append((e.dxf.text, float(p[0]), float(p[1])))

    layer_census = Counter(e.dxf.layer for e in msp)
    door_count = sum(1 for e in msp.query("INSERT") if "DOOR" in e.dxf.layer.upper())
    window_count = sum(
        1 for e in msp.query("INSERT")
        if "WIN" in e.dxf.layer.upper() or "GLASS" in e.dxf.layer.upper()
    )

    return {
        "unit_factor": unit_factor,
        "texts": texts,
        "dim_values": dim_values,
        "positioned_dims": positioned_dims,
        "anchors": anchors,
        "layer_census": dict(layer_census),
        "door_count": door_count,
        "window_count": window_count,
    }


def analyze_dxf_for_ahmed(file_path):
    """المسار الكامل: استخراج + تعرف على المشروع + فحص اتساق + تقرير."""
    data = extract_plan_geometry(file_path)

    project_name, rows, unmatched = None, None, None
    try:
        from services.project_file_service import (
            _collection, list_project_names, project_id_for_name,
        )
        names = list_project_names()
        project_name = infer_project_from_texts(data["texts"], names)
        if project_name:
            snapshot = _collection().document(project_id_for_name(project_name)).get()
            doc = snapshot.to_dict() if snapshot.exists else {}
            recorded = extract_recorded_dims(doc)
            if recorded and data["dim_values"]:
                rows, unmatched = consistency_check(recorded, data["dim_values"])
    except Exception as e:
        logger.error("❌ فحص الاتساق اتعطل (التقرير الأساسي شغال): " + str(e))

    return format_dxf_report(data, project_name, rows, unmatched)
