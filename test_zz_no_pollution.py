# -*- coding: utf-8 -*-
"""
حارس التلوث بين الاختبارات (2026-08-09).

الحادثة: `pytest` على السويت كامل رجّع **14 فشل**، و9 منهم بيعدّوا لما
يتشغّلوا لوحدهم. السبب مكانش اختبارات بايظة -- كان **ملف بيرقّع دوال في
موديولات الخدمة ومبيرجّعهاش**، فكل ملف بعده بيقرا `lambda` أو `boom` بدل
الدالة الحقيقية.

التنصيف وصل لـ`test_attention_thread.py`: بيعيّن `compute_self_state` و
`get_tracked_levels` و`get_initiative_outcomes`، وآخر تعيين بيسيب
`compute_self_state = boom` مركّبة للأبد.

الحلقة القديمة (`for f in test_*.py; do python $f; done`) عمرها ما كشفت ده
لأن كل ملف كان بياخد **عملية جديدة**. التلوث بيظهر بس في عملية واحدة
مشتركة -- يعني الانتقال لـpytest كشف عيب حقيقي كان مستخبي، مش عمل عيب جديد.

الاسم بيبدأ بـ`zz` عشان pytest بيجمّع أبجديًا فيتشغّل **في الآخر**، بعد ما
كل الملفات التانية خلصت. لو اتغيّر الاسم يبقى الحارس بيفحص نص السويت بس.
"""

import importlib
import inspect


# الدوال اللي لو اتربّعت وماترجعتش، اللي بعدها بيقرا غلط. كل واحدة
# (موديول، دالة) لازم تفضل دالة معرّفة في موديولها الأصلي.
GUARDED = [
    ("services.self_state_engine", "compute_self_state"),
    ("services.decision_engine", "get_tracked_levels"),
    ("services.initiative_loop", "get_initiative_outcomes"),
    ("services.price_base_service", "get_prices"),
    ("services.price_base_service", "_all_docs_supabase_first"),
    ("services.project_file_service", "save_project_fact"),
    ("services.attention_thread", "describe_open_threads"),
    ("services.supabase_store", "insert_event"),
    # الجولة التانية (2026-08-09): تسجيل الأحداث. تلات ملفات كانت بتفشل
    # بنفس العرض -- `payload_included` بترجع None -- والسبب إن التسجيل
    # نفسه كان مكسور، مش المنطق اللي بيتفحص.
    ("services.event_store", "record_event"),
    ("services.supabase_store", "_client"),
    ("services.tool_lifecycle_diagnostics", "record_payload_snapshot"),
]


def _is_pristine(mod_name, func_name):
    """الدالة لسه اللي اتعرّفت في الموديول ده، مش بديل مركّب من اختبار؟"""
    try:
        mod = importlib.import_module(mod_name)
    except Exception:
        return True, "الموديول مش متاح -- مش موضوع الفحص"
    fn = getattr(mod, func_name, None)
    if fn is None:
        return False, "الدالة اختفت من الموديول"
    if getattr(fn, "__name__", "") == "<lambda>":
        return False, "اتحوّلت لـlambda -- اختبار رقّعها وماترجعهاش"
    origin = getattr(fn, "__module__", None)
    if origin and origin != mod_name:
        return False, f"جاية من {origin} مش من {mod_name}"
    if not (inspect.isfunction(fn) or inspect.isbuiltin(fn) or inspect.ismethod(fn)):
        return False, f"مش دالة -- {type(fn).__name__}"
    return True, ""


def test_no_service_function_left_patched():
    """أي دالة خدمة مركّب مكانها بديل من اختبار سابق = تلوث.

    الفشل هنا **مش عيب في الملف ده** -- هو بلاغ إن ملف اختبار قبله ساب
    ترقيع. الرسالة بتقول الدالة والسبب عشان تلاقي المصدر بسرعة.
    """
    dirty = []
    for mod_name, func_name in GUARDED:
        ok, why = _is_pristine(mod_name, func_name)
        if not ok:
            dirty.append(f"{mod_name}.{func_name}: {why}")
    assert not dirty, (
        "دوال خدمة سابها اختبار مرقّعة (تلوث بين الاختبارات):\n  "
        + "\n  ".join(dirty)
        + "\n\nالاختبار اللي رقّعها لازم يرجّعها في finally."
    )


def test_no_real_database_client_is_installed():
    """مفيش عميل قاعدة بيانات **حقيقي** مركّب بعد ما السويت تخلص.

    الحادثة (2026-08-09): `test_endpoint_security.py` بيعمل
    `from main import flask_app`، واستيراد `main` بينفّذ `init_supabase()`
    و`init_firebase()` على مستوى الموديول. مع المشغّل القديم (عملية لكل
    ملف) الضرر كان بينتهي مع العملية؛ تحت pytest -- عملية واحدة -- العميل
    الحقيقي فضل مركّب لكل الـ44 ملف اللي بعده، والسويت كانت **بتقرا من
    Supabase الإنتاج** وهي فاكرة نفسها معزولة. الأعراض كانت 10 ملفات بتقف
    احترازيًا على "لقيت 6 حدث سابق" -- والستة كانوا أحداث حقيقية.

    الفحص النصي في `test_no_production_writes.py` عدّى عليها لأن مفيش اسم
    ممنوع اتكتب في ملف الاختبار. ده الفرق: هناك بنمسك النية، وهنا بنمسك
    النتيجة.
    """
    problems = []

    try:
        import services.supabase_service as ss
        if ss.supabase_client is not None:
            problems.append(
                f"supabase_client متصل: {type(ss.supabase_client).__module__}."
                f"{type(ss.supabase_client).__name__}"
            )
    except Exception:
        pass

    try:
        import services.firebase_service as fs
        db = fs.firestore_db
        if db is not None and type(db).__name__ != "FakeFirestore":
            problems.append(f"firestore_db مش fake: {type(db).__name__}")
    except Exception:
        pass

    assert not problems, (
        "عميل قاعدة بيانات حقيقي مركّب أثناء الاختبارات:\n  "
        + "\n  ".join(problems)
        + "\n\nالاتصال ممنوع من جوه الاختبارات -- شوف init_supabase/init_firebase."
    )


def test_the_default_command_excludes_nothing():
    """`pytest` المجرّد لازم يشغّل كل حاجة -- ممنوع أي استبعاد في الإعداد.

    ده حارس ضد تكرار الحادثة نفسها بشكل تاني. الحادثة الأصلية كانت
    استبعاد **بالصدفة** (مفيش conftest، فـ49 ملف مكانوش بيتشافوا). الخطر
    الجديد استبعاد **بالراحة**: حد يحط `-m "not live"` في addopts عشان
    السويت تخف، فيرجع نفس الوضع -- رقم أخضر بيغطي أقل مما بيوحي.

    استبعاد الاختبارات الحية قرار سليم وقت الشغل، بس يتاخد **في سطر
    الأوامر** كل مرة، مش يتخبّى في ملف إعداد حد كتبه مرة ونسيه.
    """
    import configparser
    import pathlib

    ini = pathlib.Path(__file__).with_name("pytest.ini")
    if not ini.exists():
        return

    cfg = configparser.ConfigParser()
    cfg.read(ini, encoding="utf-8")
    addopts = cfg.get("pytest", "addopts", fallback="")

    for flag in (" -m ", " -k ", "--ignore", "--deselect"):
        assert flag not in f" {addopts} ", (
            f"addopts فيه '{flag.strip()}' -- ده بيستبعد اختبارات من الأمر "
            f"الافتراضي في صمت.\naddopts = {addopts}\n"
            "لو عايز تستبعد الحية وانت بتشتغل: pytest -m \"not live\""
        )


if __name__ == "__main__":
    test_no_service_function_left_patched()
    test_no_real_database_client_is_installed()
    test_the_default_command_excludes_nothing()
    print("OK  مفيش تلوث")
