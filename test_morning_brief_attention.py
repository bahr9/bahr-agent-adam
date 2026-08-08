# -*- coding: utf-8 -*-
"""
حارس: بريف الصبح لازم يشوف خيط الانتباه (2026-08-08).

الحادثة: آدم بنى حواس كاملة -- خيط انتباه، حلقة مبادرة، محرك حالة -- وكلهم
اتوصلوا **كأدوات**. يعني بيقولهم لما أحمد يسأل، ومبيقولهمش لما هو يبادر.

وبريف الصبح هو **اللحظة الوحيدة اللي آدم بيتكلم فيها من نفسه كل يوم**، وكان
بيجمّع مواعيد وأقساط وملاحظات وطقس ومزاج، ويعدي على الحواس كلها. يعني آدم
يعرف إن فيه شغل بعته لمداد من يوم ومحدش خده، وإنه كلّم أحمد من ٦ أيام
ومردش عليه -- **ويقوله الطقس**.

الاختبار ده بيقفل الباب ده. صفر شبكة، صفر Firestore -- المصادر كلها متبدّلة.
"""

import morning_brief as mb


def run_test(name, fn):
    try:
        fn()
        print("OK  " + name)
        return True
    except AssertionError as e:
        print("FAIL " + name + ": " + str(e))
        return False
    except Exception as e:
        print("FAIL " + name + ": خطأ غير متوقع -- " + type(e).__name__ + ": " + str(e))
        return False


THREAD = (
    "- شغل بعته من 7 يوم ومحدش خده — Hope: تنفيذ التوصية المسجلة في ADR 0002\n"
    "- unresolved_conflict: 3 — مفتوحة من 12 يوم — قلت عنها من 6 يوم ومحصلش رد"
)


def _swap_attention(text=None, boom=None):
    """يبدّل attention_thread بمصدر ثابت. بيرجع دالة الاستعادة."""
    import sys, types
    original = sys.modules.get("services.attention_thread")
    fake = types.ModuleType("services.attention_thread")

    def describe():
        if boom:
            raise boom
        return text

    fake.describe_open_threads = describe
    sys.modules["services.attention_thread"] = fake

    import services
    original_attr = getattr(services, "attention_thread", None)
    services.attention_thread = fake

    def restore():
        if original is not None:
            sys.modules["services.attention_thread"] = original
        else:
            sys.modules.pop("services.attention_thread", None)
        if original_attr is not None:
            services.attention_thread = original_attr
    return restore


def _context_only():
    """يشغّل build_morning_context والمصادر التانية كلها واقعة (بتتبلع)."""
    return mb.build_morning_context("123")


def main():
    results = []

    def الخيط_بيوصل_للسياق():
        restore = _swap_attention(THREAD)
        try:
            ctx = _context_only()
        finally:
            restore()
        assert ctx.get("attention") == THREAD, ctx.get("attention")

    def الخيط_لما_يقع_البريف_بيكمّل():
        """عطل في الحواس مايمنعش رسالة الصبح."""
        restore = _swap_attention(boom=RuntimeError("Firestore واقع"))
        try:
            ctx = _context_only()
        finally:
            restore()
        assert ctx.get("attention") == "", ctx.get("attention")
        assert "weather" in ctx, "السياق اتكسر بدل ما يكمّل"

    def السياق_فيه_المفتاح_دايمًا():
        """غياب المفتاح كان هيرمي KeyError في بناء البرومبت."""
        restore = _swap_attention("")
        try:
            ctx = _context_only()
        finally:
            restore()
        assert "attention" in ctx

    # ---- فحص المصدر: مكان الخيط في البرومبت وقاعدته ----

    SRC = open(mb.__file__, encoding="utf-8").read()

    def الخيط_في_البرومبت_قبل_الطقس():
        """الترتيب بيأثر على اللي الموديل بيبدأ بيه."""
        assert "{attention_text}" in SRC, "الخيط مش في البرومبت خالص"
        assert SRC.index("{attention_text}") < SRC.index("{weather_text}"), \
            "الطقس قبل اللي محتاج انتباهه"

    def فيه_قاعدة_بتلزمه_يقوله():
        """وجوده في السياق مش كفاية -- لازم قاعدة تقول إنه الأهم."""
        assert "دي أهم حاجة في الرسالة ولازم تتقال" in SRC, "مفيش قاعدة تلزمه"

    def فيه_منع_صريح_لتقريب_المدد():
        """'من ٦ أيام' لو اتقرّبت لأسبوع تبقى رقم مخترع في جملة عن الأمانة."""
        assert "ممنوع تقرّبها" in SRC, "مفيش منع لتغيير المدد"

    def مفيش_حاجة_مفتوحة_مبيتحطش_في_البرومبت():
        """جملة 'مفيش حاجة مفتوحة' مش معلومة -- حشو بياخد مكان."""
        assert 'مفيش حاجة مفتوحة' in SRC and 'not in raw_attention' in SRC, \
            "بيحط نص الفاضي في البرومبت"

    def المشاريع_بتوصل_للبرومبت():
        """كانت بتتجاب وتتحط في السياق وتترمى -- projects مكانتش في البرومبت."""
        assert "{projects_text}" in SRC, "المشاريع لسه مش في البرومبت"
        assert SRC.index("{projects_text}") < SRC.index("{weather_text}"),             "الطقس قبل مشاريعه"

    def المشروع_المتأخر_بيتعلّم():
        assert 'status == "delayed"' in SRC, "حالة delayed مش متميزة عن غيرها"

    def المشروع_من_غير_عميل_بيتتخطى():
        """سجل ناقص مبيتعرضش كسطر فاضي."""
        assert 'if p.get("client")' in SRC, "مفيش فلترة للسجلات الناقصة"

    def ملاحظات_النظام_مستبعدة():
        """146 من 183 ملاحظة مصنّفة «مشروع» وكلهم عن بناء آدم."""
        assert "مشروع" not in mb.BRIEF_NOTE_CATEGORIES, mb.BRIEF_NOTE_CATEGORIES
        assert set(mb.BRIEF_NOTE_CATEGORIES) == {"عميل", "مالي", "شخصي"}, mb.BRIEF_NOTE_CATEGORIES

    def الفلترة_قبل_القص_مش_بعده():
        """لو اتفلترت بعد الـlimit، آخر 10 كلهم نظام والنتيجة صفر."""
        assert "limit=30" in SRC, "الـlimit صغير -- الفلترة هترجع فاضي"
        assert SRC.index("BRIEF_NOTE_CATEGORIES") < SRC.index("context[\"recent_notes\"]")             or "n.get(\"category\") in BRIEF_NOTE_CATEGORIES" in SRC.replace("'", '"'),             "الفلترة مش في مكان الجلب"

    for name, fn in [
        ("الخيط بيوصل للسياق", الخيط_بيوصل_للسياق),
        ("المشاريع بتوصل للبرومبت", المشاريع_بتوصل_للبرومبت),
        ("المشروع المتأخر بيتعلّم", المشروع_المتأخر_بيتعلّم),
        ("المشروع من غير عميل بيتتخطى", المشروع_من_غير_عميل_بيتتخطى),
        ("ملاحظات النظام مستبعدة", ملاحظات_النظام_مستبعدة),
        ("الفلترة قبل القص", الفلترة_قبل_القص_مش_بعده),
        ("الخيط لما يقع البريف بيكمّل", الخيط_لما_يقع_البريف_بيكمّل),
        ("السياق فيه المفتاح دايمًا", السياق_فيه_المفتاح_دايمًا),
        ("الخيط في البرومبت قبل الطقس", الخيط_في_البرومبت_قبل_الطقس),
        ("فيه قاعدة بتلزمه يقوله", فيه_قاعدة_بتلزمه_يقوله),
        ("فيه منع صريح لتقريب المدد", فيه_منع_صريح_لتقريب_المدد),
        ("الفاضي مبيدخلش البرومبت", مفيش_حاجة_مفتوحة_مبيتحطش_في_البرومبت),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
