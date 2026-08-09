# -*- coding: utf-8 -*-
"""
جسر بين pytest وأسلوب الاختبارات السايد في المشروع.

## المشكلة اللي الملف ده بيحلها (2026-08-09)

56 ملف اختبار، **49 منهم اختباراتهم جوه `main()`** بمشغّل مخصص
(`run_test(name, fn)`) وبيرجعوا كود خروج غير صفر عند الفشل. الأسلوب ده شغال
تمامًا لما الملف يتنده مباشرة -- اتحقق بالتحوير: **56/56 بيحمرّوا فعلًا،
صفر أخضر كذب**.

بس `pytest` بيجمّع دوال `test_` على مستوى الموديول بس. فمن غير الملف ده
كان بيشوف **7 ملفات و85 اختبار** ويعدي على 49 ملف **في صمت كامل** -- من
غير تحذير ولا سطر واحد. يعني `pytest` بيقول "85 عدّى" وهو مغطّي 12% من
شبكة الأمان، وأي بوابة شحن بتصدّقه بتطمّن غلط.

نفس النمط المتكرر في المشروع: قدرة مبنية وشغالة، ومقطوعة عند وصلة. الوصلة
هنا كانت بين الاختبارات والأداة اللي بتشغّلها.

## الحل

الملف ده بيخلي pytest يجمّع الـ`main()` كاختبار واحد لكل ملف. **مفيش تحويل
ولا إضعاف**: نفس الكود بيتنفّذ، والفشل بيوصل زي ما هو -- سواء رجع كود غير
صفر أو رمى استثناء.

الملفات اللي فيها دوال `test_` عادية أو `unittest.TestCase` مبتتلمسش --
pytest بيجمّعها لوحده، والملف ده بيتخطاها عشان ماتتعدش مرتين.
"""

import importlib.util
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _fresh_firestore_per_test():
    """كل اختبار بياخد مخزن fake **نضيف**، والأصلي بيرجع بعده.

    21 ملف اختبار بينادوا `install_fake_firestore()`، ودالته مكتوب في
    توثيقها صراحةً: "fake واحد لكل عملية، ومفيش داعي لـteardown لأن العملية
    بتنتهي أصلاً". الافتراض ده صحيح مع المشغّل القديم (عملية لكل ملف)،
    و**بيتكسر تحت pytest** -- عملية واحدة مشتركة.

    المحاولة الأولى هنا كانت "احفظ المقبض ورجّعه بعد كل اختبار"، وطلعت
    أسوأ: التركيب اللي كل ملف بيعمله لنفسه كان بيتلغي، فالسويت كلها كانت
    بتشتغل على fake واحد بتتراكم فيه الأحداث، و10 ملفات وقفت احترازيًا
    ("لقيت 6 حدث سابق") -- وهي محقة.

    fake نضيف لكل اختبار هو بالظبط العزل اللي المؤلفين افترضوه. مش إضعاف:
    التلوث الحقيقي (اختبار بيرقّع دالة خدمة ومبيرجعهاش) مش بيتغطى هنا --
    `test_zz_no_pollution.py` هو اللي بيمسكه، وقصده يفضل يمسكه.
    """
    try:
        import services.firebase_service as fs
        from fake_firestore import FakeFirestore
    except Exception:
        yield
        return
    original = getattr(fs, "firestore_db", None)
    fs.firestore_db = FakeFirestore()
    try:
        yield
    finally:
        fs.firestore_db = original


def _has_native_tests(path: Path) -> bool:
    """pytest شايف الملف ده لوحده؟ (دوال test_ أو TestCase)"""
    try:
        src = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return ("unittest.TestCase" in src
            or "\ndef test_" in src
            or src.startswith("def test_"))


def _has_main_runner(path: Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8")
    except Exception:
        return False
    return "\ndef main(" in src and "__main__" in src


def pytest_collect_file(file_path, parent):
    if not (file_path.suffix == ".py" and file_path.name.startswith("test_")):
        return None
    p = Path(str(file_path))
    if _has_native_tests(p) or not _has_main_runner(p):
        return None                      # pytest بيتصرف فيه لوحده
    return MainStyleFile.from_parent(parent, path=file_path)


class MainStyleFile(pytest.File):
    def collect(self):
        yield MainStyleItem.from_parent(self, name=self.path.stem)


class MainStyleItem(pytest.Item):
    """بينفّذ `main()` بتاع الملف ويترجم نتيجته لنجاح/فشل pytest."""

    def runtest(self):
        path = Path(str(self.path))
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        try:
            spec.loader.exec_module(module)
            result = module.main()
        finally:
            sys.modules.pop(path.stem, None)

        # main() بترجع 0 للنجاح وغيره للفشل (والبعض بيرجع None عند النجاح
        # ويرمي استثناء عند الفشل -- الاتنين بيتعاملوا صح هنا)
        if result not in (0, None):
            raise AssertionError(
                f"{path.name}: main() رجّع {result!r} -- فيه اختبارات فشلت. "
                "شغّل الملف مباشرة عشان تشوف أنهي واحد."
            )

    def repr_failure(self, excinfo):
        return str(excinfo.value)

    def reportinfo(self):
        return self.path, 0, f"main-style: {self.name}"
