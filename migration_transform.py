# -*- coding: utf-8 -*-
"""
🔄 دوال التحويل للهجرة -- Firestore JSON -> صفوف Postgres

كل دالة هنا **صافية**: مفيش شبكة، مفيش قاعدة بيانات، مفيش حالة. الاستيراد
الفعلي بيستخدمها، والاختبارات بتغطيها من غير أي اعتماد خارجي.

المبدأ الحاكم: **الغموض بيوقف الاستيراد، مابيتحلش بتخمين.** أي قيمة مش
مفهومة بترمي استثناء بدل ما تتحول لـ NULL بصمت -- لأن NULL صامتة في
عمود مالي أسوأ بكتير من استيراد بيقف ويسأل.
"""

import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    CAIRO = ZoneInfo("Africa/Cairo")
except Exception:                                    # pragma: no cover
    CAIRO = None


class TransformError(ValueError):
    """قيمة مش قابلة للتحويل بثقة -- الاستيراد لازم يقف."""


# ============================================================
# 1. الوقت -- خمس صيغ مختلفة بتتجمع في timestamptz واحد
# ============================================================

def to_timestamptz(value, field_name="", assume_tz=CAIRO):
    """يحوّل أي صيغة وقت موجودة في Firestore لـ datetime واعي بالمنطقة.

    الصيغ اللي بتتقابل فعلاً في البيانات:
      A. رقم epoch بالميلي        1785490887553
      B. نص ISO بإزاحة            "2026-08-05T14:23:11+03:00"
      C. زي B بس بمسافة مش T      "2026-08-05 14:23:11+03:00"
      D. نص ساذج بالدقيقة         "2026-08-05 14:23"
      E. نص ساذج بالميكروثانية    "2026-08-05 14:23:11.123456"

    D و E مالهمش إزاحة، فبيتقروا بـ assume_tz. خد بالك إن ده **مش** دايمًا
    القاهرة -- شوف correct_server_naive_time تحت.
    """
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        raise TransformError(f"{field_name}: قيمة منطقية مكان وقت -- {value!r}")

    # A: رقم epoch بالميلي
    if isinstance(value, (int, float)):
        return _from_epoch_ms(value, field_name)

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=assume_tz)

    if not isinstance(value, str):
        raise TransformError(f"{field_name}: نوع وقت غير متوقع {type(value).__name__}")

    text = value.strip()
    if not text:
        return None

    # رقم متخزن كنص
    if text.lstrip("-").isdigit():
        return _from_epoch_ms(int(text), field_name)

    # B/C/D/E -- fromisoformat بتاكل المسافة بدل T من بايثون 3.11
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as e:
        raise TransformError(f"{field_name}: نص وقت مش مقروء {text!r} -- {e}")

    if parsed.tzinfo is None:
        if assume_tz is None:
            raise TransformError(f"{field_name}: نص بلا إزاحة ومفيش منطقة مفترضة -- {text!r}")
        parsed = parsed.replace(tzinfo=assume_tz)
    return parsed


def _from_epoch_ms(value, field_name):
    """epoch بالميلي -> datetime بـ UTC، مع فحص معقولية.

    الفحص ده بيمسك أشهر غلطة في الهجرات: قيمة متخزنة بالثواني مش بالميلي
    (أو العكس). القسمة الغلط بتدي تاريخ في 1970 أو في سنة 57000 -- والاتنين
    بيعدّوا بصمت من غير الفحص ده.
    """
    seconds = value / 1000.0
    try:
        moment = datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as e:
        raise TransformError(f"{field_name}: epoch خارج المدى {value!r} -- {e}")

    if not (2000 <= moment.year <= 2100):
        raise TransformError(
            f"{field_name}: epoch بيدّي سنة {moment.year} من {value!r} -- "
            "غالبًا ثواني مش ميلي (أو العكس)"
        )
    return moment


def correct_server_naive_time(value, field_name=""):
    """للحقول اللي اتكتبت بـ datetime.now() على الحاوية -- يعني UTC.

    الحقول دي (expenses.date, decision_ledger.date, memory_notes.timestamp_str)
    اتخزنت بتوقيت السيرفر من غير أي إزاحة مسجلة. على Railway ده UTC، مش
    القاهرة -- فمصروف اتسجل 11 مساءً بالقاهرة اتخزن على اليوم اللي فات.

    التصحيح بيقرا القيمة كـ UTC (اللي هي فعلاً كانت) ويرجّعها كلحظة مطلقة.
    العرض بتوقيت القاهرة بعد كده بيطلع صح تلقائيًا.

    ⚠️ الإزاحة **مش ثابتة**: القاهرة +02:00 شتاءً و+03:00 صيفًا. عشان كده
    بنقرا كـ UTC ونسيب timestamptz يتصرف، بدل ما نضيف رقم ثابت.
    """
    return to_timestamptz(value, field_name, assume_tz=timezone.utc)


# ============================================================
# 2. المواعيد المدفونة في نص الملاحظة
# ============================================================

_DEADLINE_RE = re.compile(r"\s*\[Deadline:\s*(\d{4}-\d{2}-\d{2})\s*\]\s*")


def extract_deadline(text):
    """يفصل الموعد النهائي عن نص الملاحظة.

    الكتابة كانت: f"{text} [Deadline: {date}]"
    والقراءة كانت regex على نفس النص -- مفيش عمود للموعد خالص.

    بيرجع (النص_النضيف، الموعد_أو_None).
    """
    if not text:
        return text, None

    match = _DEADLINE_RE.search(text)
    if not match:
        return text, None

    try:
        deadline = datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except ValueError as e:
        raise TransformError(f"موعد مش صالح جوه النص: {match.group(1)!r} -- {e}")

    clean = _DEADLINE_RE.sub(" ", text).strip()
    return clean, deadline


# ============================================================
# 3. الأرقام المتخزنة كنصوص
# ============================================================

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def to_numeric(value, field_name="", allow_empty=False):
    """نص -> رقم، بصرامة.

    price_base.price متخزن str(price).strip() -- رقم في عمود نصي.
    التحويل هنا بيرمي على أي قيمة مش قابلة للتحويل بدل ما يحطها NULL،
    عشان قيمة سعر ضايعة بصمت أسوأ من استيراد بيقف.

    بيتعامل مع الأرقام العربية والفواصل الألفية.
    """
    if value is None or value == "":
        if allow_empty:
            return None
        raise TransformError(f"{field_name}: قيمة رقمية فاضية")

    if isinstance(value, bool):
        raise TransformError(f"{field_name}: قيمة منطقية مكان رقم")

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip().translate(_ARABIC_DIGITS)
    text = text.replace(",", "").replace("٬", "").replace(" ", "")
    text = re.sub(r"(جنيه|ج\.?م|EGP|LE)\s*$", "", text, flags=re.IGNORECASE).strip()

    if not text:
        if allow_empty:
            return None
        raise TransformError(f"{field_name}: مفيش رقم بعد التنظيف من {value!r}")

    try:
        return float(text)
    except ValueError:
        raise TransformError(f"{field_name}: مش قابل للتحويل لرقم -- {value!r}")


_RANGE_RE = re.compile(r"^\s*(\d[\d,٠-٩]*(?:\.\d+)?)\s*[-:–]\s*(\d[\d,٠-٩]*(?:\.\d+)?)\s*$")


def parse_price_range(value, field_name=""):
    """سعر ممكن يكون رقم واحد أو مدى -- بيرجع (من، إلى_أو_None).

    قرار أحمد (2026-08-06): أسعار الخامات في السوق مدى مش رقم --
    "البورسيلين 60×60 من 300:800". الأشكال المقبولة:
      "75"        -> (75.0, None)      سعر ثابت
      "850-1200"  -> (850.0, 1200.0)   مدى بشرطة
      "300:800"   -> (300.0, 800.0)    مدى بنقطتين (طريقة كتابة أحمد)
    ولو المدى مقلوب (أكبر قبل أصغر) بيترتب -- مش بيرمي.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), None

    text = str(value or "").strip().translate(_ARABIC_DIGITS)
    match = _RANGE_RE.match(text)
    if match:
        low = float(match.group(1).replace(",", ""))
        high = float(match.group(2).replace(",", ""))
        if low > high:
            low, high = high, low
        return low, high

    return to_numeric(value, field_name), None


# ============================================================
# 4. الإحداثيات المتخزنة كنص واحد
# ============================================================

def split_gps(value, field_name=""):
    """'30.123456, 31.234567' -> (30.123456, 31.234567)

    كانت متخزنة نص واحد مفصول بفاصلة -- مش geopoint ولا رقمين.
    بيرجع (None, None) لو فاضية، وبيرمي لو الشكل غلط.
    """
    if not value:
        return None, None

    parts = [p.strip() for p in str(value).split(",")]
    if len(parts) != 2:
        raise TransformError(f"{field_name}: شكل إحداثيات غير متوقع -- {value!r}")

    try:
        lat, lng = float(parts[0]), float(parts[1])
    except ValueError:
        raise TransformError(f"{field_name}: إحداثيات مش أرقام -- {value!r}")

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        raise TransformError(f"{field_name}: إحداثيات خارج المدى -- {value!r}")

    return lat, lng


# ============================================================
# 5. الفراغ -- توحيد "" و None
# ============================================================

def blank_to_none(value):
    """'' -> None. المشروع بيستخدم الاتنين لنفس المعنى في أماكن مختلفة
    (expenses.project بـ None، decision_ledger.project بـ '')."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


# ============================================================
# 6. أسماء الحقول العربية
# ============================================================

ARABIC_FIELD_MAP = {
    "نص": "text",
    "تم": "done",
}


def rename_arabic_fields(record):
    """يعيد تسمية المفاتيح العربية لإنجليزي.

    personal_tasks و ideas فيهم مفاتيح عربية بتحتاج اقتباس في كل
    استعلام SQL. بنعيد تسميتها مرة واحدة هنا.
    """
    return {ARABIC_FIELD_MAP.get(key, key): value for key, value in record.items()}


# ============================================================
# 7. التبعية بالترتيب في مصفوفات العناصر
# ============================================================

def assign_positions(items):
    """يضيف position لكل عنصر -- الترتيب هو العلاقة بين الأب والفرعي.

    عنصر sub=true تابع لأقرب عنصر قبله sub=false، ومفيش أي مفتاح
    بيربطهم. من غير الترتيب الهرم بيتدمر بالكامل.

    بيرجع نسخ جديدة فيها position و parent_position.
    """
    result = []
    last_parent = None
    for index, item in enumerate(items or []):
        row = dict(item)
        row["position"] = index
        if item.get("sub"):
            row["parent_position"] = last_parent
        else:
            row["parent_position"] = None
            last_parent = index
        result.append(row)
    return result
