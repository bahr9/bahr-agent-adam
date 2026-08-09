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
        picks = ds.build_materials({"الميزانية": "800K"}, no_prices)[0]
        surfaces = [p["surface"] for p in picks]
        for s in ("أرضيات", "حوائط", "أسقف"):
            self.assertIn(s, surfaces)

    def test_every_pick_explains_itself(self):
        for p in ds.build_materials({"الميزانية": "800K"}, no_prices)[0]:
            self.assertTrue(p["why"], p["surface"] + " من غير سبب")

    def test_economy_excludes_premium_options(self):
        picks = ds.build_materials({"الميزانية": "300K"}, no_prices)[0]
        floor = [p for p in picks if p["surface"] == "أرضيات"][0]
        self.assertNotEqual(floor["name"], "باركيه بلوط")

    def test_wood_limit_from_signature(self):
        picks = ds.build_materials({"الميزانية": "1.5M"}, no_prices)[0]
        woods = [p for p in picks
                 if any("خشب" in m["tags"] for m in ds.MATERIALS if m["name"] == p["name"])]
        self.assertLessEqual(len(woods), 2, "تعدى حد الأخشاب في التوقيع")

    def test_price_attached_when_known(self):
        picks = ds.build_materials({"الميزانية": "800K"}, fake_prices)[0]
        priced = [p for p in picks if p["price"]]
        self.assertTrue(priced)

    def test_missing_price_is_none_not_blank(self):
        for p in ds.build_materials({"الميزانية": "800K"}, no_prices)[0]:
            self.assertIsNone(p["price"])

    def test_heavy_use_warns_on_delicate_material(self):
        picks = ds.build_materials(
            {"الميزانية": "800K", "أطفال": "أيوه", "النضافة": "بنفسنا يومياً"}, no_prices)[0]
        warned = [p for p in picks if p["warnings"]]
        self.assertTrue(warned, "استعمال تقيل من غير تحذير صيانة")

    def test_warning_only_on_delicate_not_everything(self):
        # التحذير على كل خامة بيتساب بعد يومين -- الحساسة بس
        picks = ds.build_materials(
            {"الميزانية": "800K", "أطفال": "أيوه", "النضافة": "بنفسنا يومياً"}, no_prices)[0]
        warned = [p["name"] for p in picks if p["warnings"]]
        delicate = {m["name"] for m in ds.MATERIALS if "حساس" in m["tags"]}
        for n in warned:
            self.assertIn(n, delicate, n + " اتحذر عليه وهو مش حساس")

    def test_no_warning_without_heavy_use(self):
        picks = ds.build_materials({"الميزانية": "800K", "أطفال": "لأ", "حيوانات": "لأ"}, no_prices)[0]
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
        picks = ds.build_materials({"الميزانية": "800K", "المطبخ مفتوح": "مقفول"}, no_prices)[0]
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


class TestLayersChangeBehaviour(unittest.TestCase):
    """سؤال أحمد (2026-08-10): الذوق بتاع مين؟

    الطريقة بتتطبق على أي حاجة، والاقتراح بيتنازل قدام كلام العميل --
    والتنازل بيتقال بصوت عالي عشان أحمد يقدر يتدخل عن قصد.
    """

    BANS_SHINY = {"الميزانية": "800K", "ممنوعات": ["دهبي وفضي لامع"]}

    def test_offer_yields_to_client_ban(self):
        picks, _ = ds.build_materials(self.BANS_SHINY, no_prices)
        detail = [p for p in picks if p["surface"] == "تفاصيل"]
        self.assertTrue(detail)
        self.assertNotEqual(detail[0]["name"], "نحاس مطفي",
                            "اقتراح أحمد اتفرض رغم منع العميل")

    def test_yield_is_reported_not_silent(self):
        _, yielded = ds.build_materials(self.BANS_SHINY, no_prices)
        self.assertTrue(yielded, "التنازل عدى في صمت")
        self.assertEqual(yielded[0]["material"], "نحاس مطفي")
        self.assertEqual(yielded[0]["ban"], "دهبي وفضي لامع")

    def test_offer_applies_when_client_silent(self):
        picks, yielded = ds.build_materials({"الميزانية": "800K"}, no_prices)
        detail = [p for p in picks if p["surface"] == "تفاصيل"][0]
        self.assertEqual(detail["name"], "نحاس مطفي")
        self.assertEqual(yielded, [])

    def test_offer_labelled_as_suggestion_not_rule(self):
        picks, _ = ds.build_materials({"الميزانية": "800K"}, no_prices)
        detail = [p for p in picks if p["surface"] == "تفاصيل"][0]
        sources = [w["source"] for w in detail["why"]]
        self.assertIn("اقتراحك", sources)
        self.assertNotIn("طريقتك", sources)

    def test_method_labelled_as_method(self):
        picks, _ = ds.build_materials({"الميزانية": "800K"}, no_prices)
        light = [p for p in picks if p["surface"] == "إنارة"][0]
        self.assertIn("طريقتك", [w["source"] for w in light["why"]])

    def test_yield_visible_in_output(self):
        text = ds.format_direction(brief(self.BANS_SHINY), price_lookup=no_prices)
        self.assertIn("نزلت عن", text)
        self.assertIn("دهبي وفضي لامع", text)

    def test_every_rule_has_a_layer(self):
        for r in ds._sig.RULES:
            self.assertIn(r.get("layer"), (ds._sig.FIXED, ds._sig.METHOD, ds._sig.OFFER), r["id"])


class TestSixtyThirtyTen(unittest.TestCase):
    """قاعدة أحمد (2026-08-10). طريقة مش ذوق -- بتشتغل مع أي ألوان."""

    def test_rule_is_his_and_is_method(self):
        r = ds._sig.get("palette_60_30_10")
        self.assertIsNotNone(r)
        self.assertEqual(r["origin"], ds._sig.AHMED)
        self.assertEqual(r["layer"], ds._sig.METHOD)

    def test_every_palette_follows_the_ratio(self):
        for name in ds.PALETTES:
            p = ds.build_palette({"البالتة": name})
            by_role = {}
            for c in p["colors"]:
                by_role[c["role"]] = round(by_role.get(c["role"], 0) + c["share"], 3)
            self.assertAlmostEqual(by_role["سايد"], 0.60, places=2, msg=name)
            self.assertAlmostEqual(by_role["تاني"], 0.30, places=2, msg=name)
            self.assertAlmostEqual(by_role["لمسة"], 0.10, places=2, msg=name)

    def test_secondary_is_a_real_second_colour(self):
        # الـ30 لو درجة قريبة من الـ60 بتطلع فعليًا 90/10 وبتقرا رخيص
        for name in ds.PALETTES:
            p = ds.PALETTES[name]
            self.assertNotEqual(p["dominant"][1], p["secondary"][1], name)

    def test_floor_material_sits_in_the_thirty(self):
        # الباركيه اللي غطى الشقة مش لمسة
        p = ds.PALETTES["ترابي دافي"]
        self.assertIn("بلوط", p["secondary"][0])

    def test_shares_still_total_one(self):
        for name in ds.PALETTES:
            p = ds.build_palette({"البالتة": name})
            self.assertAlmostEqual(sum(c["share"] for c in p["colors"]), 1.0, places=2)

    def test_timid_accent_is_called_out(self):
        p = ds.build_palette({"البالتة": "غامق فخم", "ممنوعات": ["ألوان غامقة كتير"]})
        if p["accent_total"] < 0.05:
            self.assertTrue(p["timid_accent"])
            text = ds.format_direction(brief({"البالتة": "غامق فخم",
                                              "ممنوعات": ["ألوان غامقة كتير"]}),
                                       price_lookup=no_prices)
            self.assertIn("خجولة", text)

    def test_ratio_shown_in_output(self):
        text = ds.format_direction(brief({"البالتة": "ترابي دافي"}), price_lookup=no_prices)
        self.assertIn("٦٠ / ٣٠ / ١٠", text)
        self.assertIn("سايد", text)
        self.assertIn("لمسة", text)


class TestPaletteRules(unittest.TestCase):
    """قواعد البالتة بتفحص بالتة الأداة نفسها كمان.

    قاعدة بتفحص كل حاجة إلا اللي كاتبها هي قاعدة نص.
    """

    def test_shipped_palettes_pass_their_own_rules(self):
        for name in ds.PALETTES:
            p = ds.build_palette({"البالتة": name})
            self.assertEqual(p["issues"], [],
                             name + " بيكسر قاعدة من قواعد التوقيع")

    def test_pure_white_is_caught(self):
        issues = ds.check_palette([{"name": "أبيض", "hex": "#FFFFFF", "share": 0.6, "role": "سايد"}])
        self.assertTrue(issues)
        self.assertIn("أبيض صافي", issues[0]["text"])

    def test_broken_white_passes(self):
        issues = ds.check_palette([{"name": "أوف-وايت", "hex": "#F2EEE6", "share": 0.6, "role": "سايد"}])
        self.assertEqual(issues, [])

    def test_cold_grey_on_large_area_is_caught(self):
        issues = ds.check_palette([{"name": "رمادي بارد", "hex": "#9AA6B4", "share": 0.6, "role": "سايد"}])
        self.assertTrue(any("بارد" in i["text"] for i in issues))

    def test_cold_as_small_accent_is_allowed(self):
        # البارد كلمسة صغيرة مقبول -- القاعدة عن المساحة الكبيرة
        issues = ds.check_palette([{"name": "كحلي", "hex": "#29384D", "share": 0.04, "role": "لمسة"}])
        self.assertEqual([i for i in issues if "بارد" in i["text"]], [])

    def test_two_strong_accents_are_caught(self):
        issues = ds.check_palette([
            {"name": "أوف-وايت", "hex": "#F2EEE6", "share": 0.6, "role": "سايد"},
            {"name": "طوبي", "hex": "#C25E40", "share": 0.06, "role": "لمسة"},
            {"name": "كحلي غامق", "hex": "#29384D", "share": 0.04, "role": "لمسة"},
        ])
        self.assertTrue(any("بيتخانقوا" in i["text"] for i in issues))

    def test_one_strong_plus_one_quiet_passes(self):
        issues = ds.check_palette([
            {"name": "أوف-وايت", "hex": "#F2EEE6", "share": 0.6, "role": "سايد"},
            {"name": "أخضر غامق", "hex": "#33413A", "share": 0.06, "role": "لمسة"},
            {"name": "نحاس مطفي", "hex": "#A8834E", "share": 0.04, "role": "لمسة", "metal": True},
        ])
        self.assertEqual([i for i in issues if "بيتخانقوا" in i["text"]], [])

    def test_bad_hex_does_not_crash(self):
        self.assertEqual(ds.check_palette([{"name": "x", "hex": "مش لون", "share": 0.6, "role": "سايد"}]), [])

    def test_the_four_rules_are_seeded_not_ahmeds(self):
        # أحمد وافق عليهم، مقالهمش -- الاعتماد مش التأليف
        for rid in ("no_pure_white", "no_cold_under_egyptian_sun",
                    "one_strong_accent", "colour_needs_a_source"):
            r = ds._sig.get(rid)
            self.assertIsNotNone(r, rid)
            self.assertEqual(r["origin"], ds._sig.SEEDED, rid)
            self.assertEqual(r["layer"], ds._sig.METHOD, rid)
