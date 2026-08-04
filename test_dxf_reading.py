# -*- coding: utf-8 -*-
"""
Tests First -- قراءة DXF الحتمية (الشريحة الأولى، 2026-08-04).

المنطق الـ pure بيتفحص مباشرة، وقشرة ezdxf بتتفحص على ملف DXF صغير
بيتبني في الذاكرة وقت الاختبار -- صفر اعتماد على ملفات خارجية أو
Firestore أو LLM. الحالات مبنية من التجربة الحقيقية على لوحة Rock
Eden (انحراف 3.70027، حسم الـ 3.79 بكلمة أحمد).
"""
import os
import tempfile


def run_test(name, fn):
    try:
        fn()
        print(f"OK  {name}")
        return True
    except AssertionError as e:
        print(f"FAIL {name}: {e}")
        return False
    except Exception as e:
        print(f"FAIL {name}: خطأ غير متوقع -- {type(e).__name__}: {e}")
        return False


def main():
    from handlers.document_handler import SUPPORTED_EXTENSIONS
    from services.dxf_service import (
        consistency_check,
        extract_plan_geometry,
        extract_recorded_dims,
        format_dxf_report,
        infer_project_from_texts,
    )

    results = []

    # ---------- استخراج الأرقام المسجلة ----------

    def recorded_dims_parse_values():
        doc = {"facts": {"أبعاد": {
            "الريسبشن": {"value": "7.70×5.99 م"},
            "المطبخ": {"value": "ضلع واحد مكتوب في الرسم: 3.79 م -- الضلع التاني غير محسوب"},
            "وصفي": {"value": "واسع ومريح"},
        }}}
        dims = dict(extract_recorded_dims(doc))
        assert dims["الريسبشن"] == [7.70, 5.99]
        assert dims["المطبخ"] == [3.79]
        assert "وصفي" not in dims, "قيمة من غير أرقام متدخلش الفحص"

    # ---------- فحص الاتساق ----------

    def exact_and_deviation_both_match():
        # القيم الحقيقية من لوحة Rock Eden: ضجيج الرسم تحت المليمتر
        # (3.70027 = انحراف 0.27 مم) بيتحسب تطابق تام مش تقريبي
        rows, unmatched = consistency_check(
            [("أوضة نور", [3.70, 3.85])], [3.850000000000135, 3.70027125912873]
        )
        statuses = {(room, num): status for room, num, status, _ in rows}
        assert statuses[("أوضة نور", 3.85)] == "match"
        assert statuses[("أوضة نور", 3.70)] == "match", statuses
        assert unmatched == []
        # انحراف حقيقي (1 سم، جوه السماحية) بيتعلّم كتطابق تقريبي
        rows2, _ = consistency_check([("الماستر", [3.78])], [3.79])
        assert rows2[0][2] == "match_deviation", rows2

    def recorded_but_not_drawn_is_flagged_not_alarmed():
        rows, _ = consistency_check([("الريسبشن", [7.70])], [3.85, 2.20])
        assert rows[0][2] == "not_in_drawing"

    def drawn_but_not_recorded_is_listed():
        _, unmatched = consistency_check([("الماستر", [3.78])], [3.79, 2.20])
        # 3.79 جوه السماحية (فرق 1 سم) فبيتطابق لما مفيش منافس
        assert unmatched == [2.20], unmatched

    def exact_owner_wins_the_drawn_dim():
        # الحالة اللي كشفتها اللوحة الحقيقية: 3.79 المرسومة بتاعة
        # المطبخ (تام) -- الماستر 3.78 مياخدهاش كتطابق تقريبي كمان
        rows, _ = consistency_check(
            [("الماستر", [3.78]), ("المطبخ", [3.79])], [3.79]
        )
        statuses = {room: status for room, _, status, _ in rows}
        assert statuses["المطبخ"] == "match"
        assert statuses["الماستر"] == "not_in_drawing", statuses

    # ---------- التعرف على المشروع من نصوص اللوحة ----------

    existing = ["Rock Eden - essam farag", "شقة جاردينيا"]

    def title_block_identifies_project():
        texts = ["owner : essam farag ", "rock eden compound", "D 10", "2nd floor"]
        assert infer_project_from_texts(texts, existing) == "Rock Eden - essam farag"

    def unrelated_texts_identify_nothing():
        assert infer_project_from_texts(["some tower", "cairo"], existing) is None

    def tie_between_projects_is_never_guessed():
        names = ["فيلا احمد - التجمع الخامس", "شقة سارة - التجمع الخامس"]
        texts = ["التجمع الخامس"]
        assert infer_project_from_texts(texts, names) is None

    # ---------- التقرير ----------

    def report_shows_consistency_and_asks_on_unknown():
        data = {"unit_factor": 1.0, "texts": ["owner: essam"], "dim_values": [3.85],
                "layer_census": {"WALL-AR": 5}, "door_count": 2, "window_count": 1}
        with_project = format_dxf_report(
            data, "Rock Eden - essam farag",
            [("أوضة نور", 3.85, "match", 3.85)], [],
        )
        assert "فحص الاتساق" in with_project and "مطابق تمامًا" in with_project
        without = format_dxf_report(data, None)
        assert "قولي اسم المشروع" in without

    # ---------- قشرة ezdxf على ملف حقيقي مبني في الذاكرة ----------

    def ezdxf_extraction_reads_texts_and_layers():
        import ezdxf
        doc = ezdxf.new()
        doc.header["$INSUNITS"] = 6
        msp = doc.modelspace()
        msp.add_text("owner : essam farag", dxfattribs={"layer": "text"})
        msp.add_line((0, 0), (3.79, 0), dxfattribs={"layer": "WALL-AR"})
        path = os.path.join(tempfile.gettempdir(), "adam_test_plan.dxf")
        doc.saveas(path)
        try:
            data = extract_plan_geometry(path)
        finally:
            os.remove(path)
        assert data["unit_factor"] == 1.0
        assert "owner : essam farag" in data["texts"]
        assert data["layer_census"].get("WALL-AR") == 1
        assert data["dim_values"] == [], "مفيش DIMENSION في الملف ده"

    # ---------- التسجيل في مسار الملفات ----------

    def dxf_is_a_supported_document_type():
        assert ".dxf" in SUPPORTED_EXTENSIONS

    for name, fn in [
        ("أرقام الملف المسجلة بتتقري صح", recorded_dims_parse_values),
        ("التطابق التام والانحراف المليمتري", exact_and_deviation_both_match),
        ("المسجل الغير مرسوم بيتعلّم مش بيفزّع", recorded_but_not_drawn_is_flagged_not_alarmed),
        ("المرسوم الغير مسجل بيتعرض", drawn_but_not_recorded_is_listed),
        ("التطابق التام بياخد القياس مش التقريبي", exact_owner_wins_the_drawn_dim),
        ("الـ title block بيحدد المشروع", title_block_identifies_project),
        ("نصوص غريبة = مفيش تعرف", unrelated_texts_identify_nothing),
        ("التعادل بين مشروعين مبيتخمنش", tie_between_projects_is_never_guessed),
        ("التقرير بيعرض الاتساق وبيسأل عند الجهل", report_shows_consistency_and_asks_on_unknown),
        ("قشرة ezdxf بتقرا نصوص وطبقات", ezdxf_extraction_reads_texts_and_layers),
        ("dxf نوع ملف مدعوم في المسار", dxf_is_a_supported_document_type),
    ]:
        results.append(run_test(name, fn))

    print()
    if all(results):
        print(f"{len(results)}/{len(results)} اختبار عدّى")
    else:
        print(f"{sum(results)}/{len(results)} بس اللي عدّى")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
