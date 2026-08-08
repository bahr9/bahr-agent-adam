# -*- coding: utf-8 -*-
"""
حارس مزامنة أكشنات الأنظمة التانية -- **عبر الريبوهات** (2026-08-08).

الحادثة (متسجلة في تعليق `agent_orchestration`): "لما ضفنا
website_readiness_report لمداد وحدّثنا الوصف بس، آدم شاف تعارض بين مصدرين
وبلّغ أحمد 'الأكشن مش معروف' عن أكشن اتنفذ فعلًا".

اتصلحت وقتها في تلات أماكن، **ورجعت في الرابع**. مراجعة 2026-08-08 لقت وصف
أداة `dispatch_agent_task` لسه فيه أكشن واحد لمداد بينما السجل فيه تلاتة.

الوصف بقى **مولّد** من السجل فالمكان الرابع اتشال أصلًا. الملف ده بيحرس
اللي فضل: الجانب التاني -- `ALLOWLISTED_ACTIONS` في ريبو مداد. القاعدة دي
كانت متعتمدة على إن حد يفتكر يعدّل ريبوين مع بعض، والذاكرة مش آلية.

فحص نص -- صفر شبكة، صفر Firestore، صفر تنفيذ لمداد.
"""

import io
import os
import re

# ريبو مداد جنب آدم على نفس المستوى. مش موجود = تخطي معلن، مش فشل: الحارس
# ده لازم يعدي على أي جهاز فيه آدم لوحده (CI مثلاً).
MEDAD_EXECUTOR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "bahr marketing agent", "services", "agent_task_executor.py",
)


def run_test(name, fn):
    try:
        result = fn()
        if result == "skip":
            print("SKIP " + name)
        else:
            print("OK  " + name)
        return True
    except AssertionError as e:
        print("FAIL " + name + ": " + str(e))
        return False
    except Exception as e:
        print("FAIL " + name + ": خطأ غير متوقع -- " + type(e).__name__ + ": " + str(e))
        return False


def _medad_allowlist():
    """أكشنات مداد المسموح بيها، أو None لو الريبو مش موجود."""
    if not os.path.exists(MEDAD_EXECUTOR):
        return None
    src = io.open(MEDAD_EXECUTOR, encoding="utf-8").read()
    block = re.search(r"ALLOWLISTED_ACTIONS\s*=\s*\{(.*?)\n\}", src, re.S)
    if not block:
        return None
    # الأسطر المعلّقة مستبعدة -- التعليقات في الليستة دي فيها أسماء أكشنات
    body = "\n".join(l for l in block.group(1).splitlines()
                     if not l.strip().startswith("#"))
    return set(re.findall(r'"([a-z_]+)"', body))


def main():
    from services import claude_service as cs
    from services.agent_orchestration import AUTOMATED_ACTIONS_BY_TARGET

    adam_medad = set(AUTOMATED_ACTIONS_BY_TARGET.get("مداد") or ())
    SRC = io.open(cs.__file__, encoding="utf-8").read()
    PROMPT = SRC.split('"name": "', 1)[0]
    DESC = next(t for t in cs.TOOLS if t["name"] == "dispatch_agent_task") \
        ["input_schema"]["properties"]["action"]["description"]

    def وصف_الأداة_مولّد_مش_مكتوب_بالإيد():
        """المكان الرابع اتشال: الوصف بيتبنى من السجل وقت التعريف."""
        assert "_automated_actions_line()" in SRC, \
            "الوصف رجع مكتوب بالإيد -- الانحراف هيرجع معاه"

    def الوصف_فيه_كل_أكشنات_السجل():
        missing = sorted(a for a in adam_medad if a not in DESC)
        assert not missing, (
            "أكشنات في السجل ومش في الوصف اللي الموديل بيقراه: " + str(missing)
            + " -- آدم هيقول 'الأكشن مش معروف' عن أكشن منفّذ"
        )

    def الوصف_مفيهوش_أكشن_مش_موجود():
        """العكس بردو خطر: وصف بيوعد بأوتوميشن مش موجود."""
        all_known = set()
        for actions in AUTOMATED_ACTIONS_BY_TARGET.values():
            all_known |= set(actions)
        promised = set(re.findall(r"'([a-z_]{6,})'", DESC))
        ghost = sorted(promised - all_known)
        assert not ghost, "الوصف بيوعد بأكشنات مش في السجل: " + str(ghost)

    def البرومبت_متطابق_مع_السجل():
        missing = sorted(a for a in adam_medad if a not in PROMPT)
        assert not missing, "أكشنات مش مذكورة في فقرة الأوركسترا: " + str(missing)

    def مداد_وآدم_متطابقين():
        """الجانب التاني -- الريبو التاني. ده اللي القاعدة كانت بتعتمد فيه
        على إن حد يفتكر."""
        medad = _medad_allowlist()
        if medad is None:
            print("     (ريبو مداد مش موجود على الجهاز ده -- المقارنة اتخطت)")
            return "skip"
        only_adam = sorted(adam_medad - medad)
        only_medad = sorted(medad - adam_medad)
        assert not only_medad, (
            "مداد بينفّذ أكشنات آدم مش عارفها: " + str(only_medad)
            + " -- آدم هيبلّغ أحمد إنها 'مش معروفة' وهي شغالة"
        )
        assert not only_adam, (
            "آدم بيوعد بأكشنات مداد مش منفّذها: " + str(only_adam)
            + " -- التاسك هيقعد pending للأبد"
        )

    def قاعدة_المزامنة_موثّقة_في_الجانبين():
        assert "قاعدة مزامنة" in io.open(
            "services/agent_orchestration.py", encoding="utf-8").read(), \
            "تحذير المزامنة اتشال من ناحية آدم"
        if os.path.exists(MEDAD_EXECUTOR):
            assert "قاعدة مزامنة" in io.open(MEDAD_EXECUTOR, encoding="utf-8").read(), \
                "تحذير المزامنة اتشال من ناحية مداد"

    results = [
        run_test("وصف الأداة مولّد مش مكتوب بالإيد", وصف_الأداة_مولّد_مش_مكتوب_بالإيد),
        run_test("الوصف فيه كل أكشنات السجل", الوصف_فيه_كل_أكشنات_السجل),
        run_test("الوصف مفيهوش أكشن مش موجود", الوصف_مفيهوش_أكشن_مش_موجود),
        run_test("البرومبت متطابق مع السجل", البرومبت_متطابق_مع_السجل),
        run_test("مداد وآدم متطابقين", مداد_وآدم_متطابقين),
        run_test("قاعدة المزامنة موثّقة في الجانبين", قاعدة_المزامنة_موثّقة_في_الجانبين),
    ]

    print()
    passed = sum(1 for r in results if r)
    print(str(passed) + "/" + str(len(results)) + " اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
