# -*- coding: utf-8 -*-
"""
اختبارات الاتجاه -- بالتة وخامات مشتقة من البريف.

محلي بالكامل: `price_lookup` متحقونة، فصفر شبكة وصفر إنتاج.
"""

import unittest

from services import direction_service as ds


def brief(answers):
    return {"client_name": "عميل", "answers": answers}


def no_prices(_key):
    return None


def fake_prices(key):
    table = {"باركيه": "باركيه بلوط: 750 / متر مسطح",
             "النقاش": "متر النقاش: 75 / متر مسطح"}
    return table.get(key)


class TestBudgetTier(unittest.TestCase):
    def test_economy(self):
        self.assertEqual(ds.budget_tier({"الميزانية": "300K"}), "اقتصادي")

    def test_mid(self):
        self.assertEqual(ds.budget_tier({"الميزانية": "800K"}), "متوسط")

    def test_high(self):
        self.assertEqual(ds.budget_tier({"الميزانية": "1.25M"}), "عالي")

    def test_missing(self):
        self.assertIsNone(ds.budget_tier({}))

    def test_garbage(self):
        self.assertIsNone(ds.budget_tier({"الميزانية": "مش عارف"}))


class TestPalette(unittest.TestCase):
    def test_uses_client_choice(self):
        p = ds.build_palette({"البالتة": "غامق فخم"})
        self.assertEqual(p["name"], "غامق فخم")
        self.assertEqual(p["source"][0], "البالتة")

    def test_falls_back_to_tone(self):
        p = ds.build_palette({"فاتح ولا غامق": "فاتح مضوي"})
        self.assertEqual(p["name"], "فاتح هادي")
        self.assertEqual(p["source"][0], "فاتح ولا غامق")

    def test_default_when_nothing_said(self):
        p = ds.build_palette({})
        self.assertIn(p["name"], ds.PALETTES)
        self.assertIsNone(p["source"])

    def test_shares_sum_to_one(self):
        for name in ds.PALETTES:
            p = ds.build_palette({"البالتة": name})
            self.assertAlmostEqual(sum(c["share"] for c in p["colors"]), 1.0, places=2)

    def test_ban_mutes_matching_colors(self):
        p = ds.build_palette({"البالتة": "غامق فخم", "ممنوعات": ["ألوان غامقة كتير"]})
        muted = [c for c in p["colors"] if c.get("muted")]
        self.assertTrue(muted, "الممنوع مأثرش على البالتة")
        self.assertTrue(p["adjustments"])

    def test_ban_keeps_total_at_one(self):
        p = ds.build_palette({"البالتة": "غامق فخم", "ممنوعات": ["ألوان غامقة كتير"]})
        self.assertAlmostEqual(sum(c["share"] for c in p["colors"]), 1.0, places=2)

    def test_ban_never_removes_a_color(self):
        # التقليص مش الشيل -- شيل اللون بيكسر البالتة
        base = len(ds.build_palette({"البالتة": "غامق فخم"})["colors"])
        with_ban = len(ds.build_palette(
            {"البالتة": "غامق فخم", "ممنوعات": ["ألوان غامقة كتير"]})["colors"])
        self.assertEqual(base, with_ban)

    def test_irrelevant_ban_changes_nothing(self):
        p = ds.build_palette({"البالتة": "ترابي دافي", "ممنوعات": ["رفوف مفتوحة"]})
        self.assertEqual(p["adjustments"], [])


class TestMaterials(unittest.TestCase):
    def test_covers_every_surface(self):
        picks = ds.build_materials({"الميزانية": "800K"}, no_prices)
        surfaces = [p["surface"] for p in picks]
        for s in ("أرضيات", "حوائط", "أسقف"):
            self.assertIn(s, surfaces)

    def test_every_pick_explains_itself(self):
        for p in ds.build_materials({"الميزانية": "800K"}, no_prices):
            self.assertTrue(p["why"], p["surface"] + " من غير سبب")

    def test_economy_excludes_premium_options(self):
        picks = ds.build_materials({"الميزانية": "300K"}, no_prices)
        floor = [p for p in picks if p["surface"] == "أرضيات"][0]
        self.assertNotEqual(floor["name"], "باركيه بلوط")

    def test_wood_limit_from_signature(self):
        picks = ds.build_materials({"الميزانية": "1.5M"}, no_prices)
        woods = [p for p in picks
                 if any("خشب" in m["tags"] for m in ds.MATERIALS if m["name"] == p["name"])]
        self.assertLessEqual(len(woods), 2, "تعدى حد الأخشاب في التوقيع")

    def test_price_attached_when_known(self):
        picks = ds.build_materials({"الميزانية": "800K"}, fake_prices)
        priced = [p for p in picks if p["price"]]
        self.assertTrue(priced)

    def test_missing_price_is_none_not_blank(self):
        for p in ds.build_materials({"الميزانية": "800K"}, no_prices):
            self.assertIsNone(p["price"])

    def test_heavy_use_warns_on_delicate_material(self):
        picks = ds.build_materials(
            {"الميزانية": "800K", "أطفال": "أيوه", "النضافة": "بنفسنا يومياً"}, no_prices)
        warned = [p for p in picks if p["warnings"]]
        self.assertTrue(warned, "استعمال تقيل من غير تحذير صيانة")

    def test_warning_only_on_delicate_not_everything(self):
        # التحذير على كل خامة بيتساب بعد يومين -- الحساسة بس
        picks = ds.build_materials(
            {"الميزانية": "800K", "أطفال": "أيوه", "النضافة": "بنفسنا يومياً"}, no_prices)
        warned = [p["name"] for p in picks if p["warnings"]]
        delicate = {m["name"] for m in ds.MATERIALS if "حساس" in m["tags"]}
        for n in warned:
            self.assertIn(n, delicate, n + " اتحذر عليه وهو مش حساس")

    def test_no_warning_without_heavy_use(self):
        picks = ds.build_materials({"الميزانية": "800K", "أطفال": "لأ", "حيوانات": "لأ"}, no_prices)
        self.assertEqual([p for p in picks if p["warnings"]], [])


class TestCompositionNotes(unittest.TestCase):
    """قاعدة التركيب بتتقال مرة واحدة على المجموعة، ولما تتكسر بس."""

    def test_silent_when_contrast_exists(self):
        picks = [{"name": "كلادينج خشبي"}, {"name": "دهان مطفي"}]   # خشن + ناعم
        self.assertEqual(ds.composition_notes(picks), [])

    def test_fires_when_all_smooth(self):
        picks = [{"name": "دهان مطفي"}, {"name": "جبس بورد بنزلة محيطية"}]
        notes = ds.composition_notes(picks)
        self.assertTrue(notes)
        self.assertIn("تباين ملمسي", notes[0]["text"])

    def test_note_quotes_the_rule(self):
        notes = ds.composition_notes([{"name": "دهان مطفي"}])
        self.assertEqual(notes[0]["rule"], ds._sig.get("rough_beside_smooth")["text"])

    def test_not_repeated_per_material(self):
        picks = [{"name": "دهان مطفي"}, {"name": "جبس بورد بنزلة محيطية"},
                 {"name": "جبس بورد مقاوم للرطوبة"}]
        self.assertEqual(len(ds.composition_notes(picks)), 1)

    def test_closed_kitchen_notes_moisture_ceiling(self):
        picks = ds.build_materials({"الميزانية": "800K", "المطبخ مفتوح": "مقفول"}, no_prices)
        ceiling = [p for p in picks if p["surface"] == "أسقف"][0]
        self.assertIn("رطوبة", ceiling.get("note", ""))


class TestFormatting(unittest.TestCase):
    ROW = brief({
        "البالتة": "ترابي دافي", "الميزانية": "800K",
        "ممنوعات": ["ألوان غامقة كتير"], "أطفال": "أيوه", "النضافة": "بنفسنا يومياً",
    })

    def test_shows_palette_with_percentages(self):
        text = ds.format_direction(self.ROW, price_lookup=no_prices)
        self.assertIn("البالتة", text)
        self.assertIn("٪", text)

    def test_names_unpriced_materials(self):
        text = ds.format_direction(self.ROW, price_lookup=no_prices)
        self.assertIn("محتاج تسعّرها", text)

    def test_shows_source_of_palette(self):
        text = ds.format_direction(self.ROW, price_lookup=no_prices)
        self.assertIn("من البالتة", text)

    def test_ban_adjustment_is_visible(self):
        text = ds.format_direction(self.ROW, price_lookup=no_prices)
        self.assertIn("ألوان غامقة كتير", text)

    def test_empty_brief_no_crash(self):
        text = ds.format_direction(brief({}), price_lookup=no_prices)
        self.assertIn("اتجاه مقترح", text)


if __name__ == "__main__":
    unittest.main()
