# -*- coding: utf-8 -*-
"""
اختبارات قراءة البريف -- محلية بالكامل، صفر شبكة وصفر إنتاج.

بتغطي حاجتين: إن القواعد بتولع في التركيب الصح وبتسكت في الغلط،
وإن **الالتزام الدستوري محفور في المخرج** (كل flag له basis، والفصل
بين حقيقة واستنتاج وسؤال قايم).
"""

import unittest

from services import brief_reader as br


def brief(answers, final=True, name="عميل"):
    return {"client_name": name, "is_final": final, "answers": answers}


# بريف أحمد الحقيقي (2026-08-09) كحالة مرجعية
REAL = {
    "الاسم": "Ahmed gowaida", "الموبايل": "01120051578", "مكان الوحدة": "Sodic",
    "نوع الوحدة": "دوبلكس", "حالة الوحدة": "على الطوب الأحمر", "الخدمة": "تصميم وتنفيذ",
    "الميزانية": "1.25M", "شمول الميزانية": "كل حاجة", "أولوية التضحية": "قطع أثاث معينة",
    "ممنوعات": ["ألوان غامقة كتير", "دهبي وفضي لامع", "نقوش وزخارف كتير", "ستايل كلاسيك تقيل"],
    "فاتح ولا غامق": "فاتح مضوي", "البالتة": "فاتح هادي",
    "مودرن ولا دافي كلاسيك": "دافي بلمسة كلاسيك",
    "عدد الأفراد": "٥ أو أكتر", "أطفال": "أيوه",
    "تفاصيل الأطفال": "3 اولاد و بنت كلهم من ٨-١٥",
    "احتياج أوضة الأطفال": ["ركن لعب", "ركن مذاكرة", "سرير دورين", "تخزين كتير"],
    "حيوانات": "كلاب", "بعد ٥ سنين": "العيلة هتكبر",
    "شكل العزومة": "الاتنين حسب المناسبة", "عدد العزومة": "٧ - ١٢",
    "عزومات رمضان": "أكيد، عزومات كبيرة",
    "ريحة الأكل": "لازم تتحبس في المطبخ", "المطبخ مفتوح": "مقفول",
    "النضافة": "بنفسنا يومياً",
    "أجهزة المطبخ": ["غسالة أطباق", "فرن بلت إن", "ميكروويف بلت إن", "تلاجة كبيرة جنب بعض"],
    "مكان الغسالة": "المطبخ", "السترة": "أيوه مهم", "ركن صلاة": "أيوه يا ريت",
    "شغل من البيت": "ساعات",
}


def ids(read):
    return {f["id"] for f in read["flags"]}


class TestBudgetParsing(unittest.TestCase):
    def test_k(self):
        self.assertEqual(br.budget_thousands({"الميزانية": "500K"}), 500)

    def test_m(self):
        self.assertEqual(br.budget_thousands({"الميزانية": "1.25M"}), 1250)

    def test_m_plus(self):
        self.assertEqual(br.budget_thousands({"الميزانية": "3M+"}), 3000)

    def test_missing(self):
        self.assertIsNone(br.budget_thousands({}))

    def test_garbage(self):
        self.assertIsNone(br.budget_thousands({"الميزانية": "مش عارف"}))


class TestRealBrief(unittest.TestCase):
    """الحالة المرجعية: نفس اللي اتقري بالإيد لازم يطلع من القواعد."""

    def setUp(self):
        self.read = br.read_brief(brief(REAL))

    def test_budget_scope_fires(self):
        self.assertIn("budget_scope", ids(self.read))

    def test_privacy_guests_fires(self):
        self.assertIn("privacy_guests", ids(self.read))

    def test_signature_gender_rule_fires(self):
        self.assertIn("girl_among_boys", ids(self.read))

    def test_light_palette_fires(self):
        self.assertIn("light_palette_load", ids(self.read))

    def test_closed_kitchen_fires(self):
        self.assertIn("closed_kitchen_appliances", ids(self.read))

    def test_no_kitchen_contradiction(self):
        # ريحة تتحبس + مطبخ مقفول = متسق، مش تعارض
        self.assertNotIn("kitchen_contradiction", ids(self.read))

    def test_wfh_silent_when_not_daily(self):
        self.assertNotIn("wfh_without_detail", ids(self.read))

    def test_nothing_missing(self):
        self.assertEqual(self.read["missing"], [])

    def test_high_severity_comes_first(self):
        sevs = [f["severity"] for f in self.read["flags"]]
        self.assertEqual(sevs, sorted(sevs, key=lambda s: br._SEV_ORDER[s]))


class TestConstitutionShape(unittest.TestCase):
    """الالتزام الدستوري لازم يكون محفور في البنية مش في النية."""

    def test_every_flag_has_basis(self):
        read = br.read_brief(brief(REAL))
        for f in read["flags"]:
            self.assertTrue(f.get("basis"), f"{f['id']} من غير basis")

    def test_every_flag_has_source(self):
        read = br.read_brief(brief(REAL))
        for f in read["flags"]:
            self.assertIn(f.get("source"), ("البريف", "توقيعك"))

    def test_facts_are_verbatim(self):
        read = br.read_brief(brief(REAL))
        for k, v in read["facts"]:
            self.assertEqual(v, REAL[k])

    def test_no_state_claims_in_text(self):
        text = br.format_read(brief(REAL))
        for bad in ("العميل عايز", "العميل حاسس", "العميل مش مرتاح", "حاسس إن"):
            self.assertNotIn(bad, text)

    def test_inference_section_is_labeled(self):
        text = br.format_read(brief(REAL))
        self.assertIn("استنتاج (مش كلام العميل)", text)

    def test_signature_rule_quoted_in_text(self):
        text = br.format_read(brief(REAL))
        self.assertIn("توقيعك", text)
        self.assertIn(br._sig.get("separate_genders")["text"], text)


class TestRulesFireCorrectly(unittest.TestCase):
    def test_kitchen_contradiction_fires(self):
        read = br.read_brief(brief({
            "ريحة الأكل": "لازم تتحبس في المطبخ",
            "المطبخ مفتوح": "مفتوح على الريسبشن",
        }))
        self.assertIn("kitchen_contradiction", ids(read))

    def test_budget_silent_for_small_flat(self):
        read = br.read_brief(brief({
            "نوع الوحدة": "شقة", "شمول الميزانية": "كل حاجة", "الميزانية": "1.25M",
        }))
        self.assertNotIn("budget_scope", ids(read))

    def test_budget_silent_when_finishing_only(self):
        read = br.read_brief(brief({
            "نوع الوحدة": "دوبلكس", "شمول الميزانية": "التشطيب بس", "الميزانية": "1.25M",
        }))
        self.assertNotIn("budget_scope", ids(read))

    def test_privacy_silent_for_small_gatherings(self):
        read = br.read_brief(brief({"السترة": "أيوه مهم", "عدد العزومة": "لحد ٦"}))
        self.assertNotIn("privacy_guests", ids(read))

    def test_gender_rule_silent_for_boys_only(self):
        read = br.read_brief(brief({
            "أطفال": "أيوه", "تفاصيل الأطفال": "ولدين ٦ و٩",
        }))
        self.assertNotIn("girl_among_boys", ids(read))

    def test_light_palette_silent_without_load(self):
        read = br.read_brief(brief({"البالتة": "فاتح هادي", "حيوانات": "لأ"}))
        self.assertNotIn("light_palette_load", ids(read))

    def test_wfh_fires_when_daily_and_blank(self):
        read = br.read_brief(brief({"شغل من البيت": "يومياً ومحتاج مكتب"}))
        self.assertIn("wfh_without_detail", ids(read))

    def test_wfh_silent_when_detail_given(self):
        read = br.read_brief(brief({
            "شغل من البيت": "يومياً ومحتاج مكتب", "تفاصيل المكتب": "شاشتين ومكتبة",
        }))
        self.assertNotIn("wfh_without_detail", ids(read))


class TestPartialAndEmpty(unittest.TestCase):
    def test_partial_is_labeled(self):
        text = br.format_read(brief({"الاسم": "منى"}, final=False))
        self.assertIn("لسه مكملش", text)

    def test_missing_critical_reported(self):
        read = br.read_brief(brief({"الاسم": "منى"}))
        self.assertIn("الميزانية", read["missing"])
        self.assertIn("نوع الوحدة", read["missing"])

    def test_empty_brief_no_crash(self):
        text = br.format_read(brief({}))
        self.assertIn("قراءة بريف", text)

    def test_no_flags_says_so(self):
        text = br.format_read(brief({"نوع الوحدة": "شقة"}))
        self.assertIn("مفيش توترات ظاهرة", text)


if __name__ == "__main__":
    unittest.main()
