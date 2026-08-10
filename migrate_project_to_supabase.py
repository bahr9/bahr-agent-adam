# -*- coding: utf-8 -*-
"""
نقل مشروع من Firestore للجداول المفكوكة في Supabase (2026-08-10).

    python migrate_project_to_supabase.py PRJ-MRE9OHLK --dry-run
    python migrate_project_to_supabase.py PRJ-MRE9OHLK --write

## ليه الجداول مفكوكة مش عمود jsonb

الداتا أثبتت إنها بتتفكك: `project_phase_items` بيتقرا منه المجموع، و
`project_quantity_items` بيتحسب منه المقدار حسب الوحدة. عمود jsonb كان
هيخلي الاتنين دول قراءة في الذاكرة بدل استعلام. الاقتراح ده اتلغى قبل
الشغلانة دي.

## القواعد اللي السكربت مبني عليها

1. **نسخ مش قص.** Firestore مايتلمسش خالص -- ولا كتابة ولا حذف. النسخة
   القديمة بتفضل يتيمة عن قصد كمرجع طول ما نافذة التضارب مفتوحة.

2. **إعادة التشغيل مش بتكرّر.** كل كتابة `upsert` بمفتاح طبيعي، مش
   `insert` أعمى. تشغّله عشر مرات تلاقي نفس الـ106 صف.

3. **العدّ بيوقف مش بيحذّر.** بعد كل جدول بنعدّ اللي في Supabase ونقارنه
   باللي في المصدر. أي رقم مايطبقش بيرمي `MigrationError` باسم الجدول
   والرقمين. تحذير في اللوج معناه إن النقل خلص ناقص وحد هيكتشف بعد شهر.

4. **`position` حامل معنى.** في `project_phase_items` و
   `project_quantity_items` البند اللي `is_sub=true` تابع لأقرب بند
   قبله `is_sub=false` -- **ومفيش أي مفتاح بيربطهم**. الترتيب في
   المصفوفة هو العلاقة. بنستخدم فهرس المصفوفة زي ما هو (صفري) عشان
   الترتيب يفضل مطابق حرفيًا للمصدر.

5. **الأبعاد الخام بتتنقل زي ما هي.** length/width/height/count كل واحد
   في عموده. ممنوع نطبّعهم لعمود كمية واحد: الوحدة هي اللي بتحدد أنهي
   بُعد له معنى (م³ بيستخدم التلاتة، م.ط بيستخدم length بس)، والتطبيع
   بيمنع إعادة الحساب والمراجعة بعد كده.
"""

import argparse
import sys
from datetime import datetime, timezone


class MigrationError(Exception):
    """فشل بيوقف النقل. مش تحذير."""


# ============================================================
# تطبيع الوحدات
# ============================================================
# الوحدتين دول **ترميز مش معنى**، والتطبيع هنا مش بيغيّر أي رقم:
#
#   'م2'  ->  'م²'        رقم 2 عادي بدل الأُسّي. نفس الوحدة بالحرف.
#   'مق'  ->  'مقطوعية'   اختصار. أحمد أكّده صراحةً (2026-08-09).
#
# الوحدات الحقيقية اللي مكانتش في السكيما (`عدد` و`فاتورة`) **مش** هنا
# بالقصد: دول اتحلوا بتوسيع القيد في ميجريشن 015، لأن تحويلهم لوحدة
# تانية كان هيزوّر أرقام في مقايسة حقيقية.
#
# الخريطة دي مكتوبة كقاعدة مسمّاة مش سطر عابر عشان سبب: الوحدات دي جت
# من ملفات المقايسات الأصلية عن طريق سكربت استيراد، مش من قايمة BAHR OS
# (اللي عمرها ما عرضتهم). الكاتب ده مش شغّال دلوقتي، فـ`م2` مش هترجع
# لوحدها -- بس أي استيراد جديد من نفس الملفات هيرجّعها، ولازم يعدّي من
# هنا.
UNIT_ENCODING_FIXES = {
    "م2": "م²",
    "مق": "مقطوعية",
}

# القيد بعد ميجريشن 015
PHASE_UNITS_ALLOWED = {"مقطوعية", "م.ط", "م²", "م³", "عدد", "فاتورة"}
QUANTITY_UNITS_ALLOWED = {"مقطوعية", "م.ط", "م²", "م³"}

# اسم البلوك في Firestore -> قيمة `phase` في Supabase
PHASE_BLOCKS = {
    "foundationdata": "foundation",
    "finishdata": "finish",
    # ⚠️ `finaldata` **مش** ملخص ولا بيانات نهائية -- دي تقدير مرحلة
    #    "الفينيش والديكور"، مطابقة في الشكل للمرحلتين التانيتين.
    "finaldata": "final",
}


def log(msg=""):
    print(msg, flush=True)


# ============================================================
# القراءة من Firestore
# ============================================================

def read_source(project_id):
    from services.firebase_service import init_firebase
    import services.firebase_service as fb

    if not init_firebase():
        raise MigrationError("مقدرتش أتصل بـFirestore -- مفيش مصدر أقرا منه.")

    snap = fb.firestore_db.collection("projects").document(project_id).get()
    if not snap.exists:
        raise MigrationError(f"المشروع {project_id} مش موجود في Firestore.")
    return snap.to_dict() or {}


def normalize_unit(raw, allowed, where, fixes_applied):
    unit = (raw or "").strip()
    if unit in UNIT_ENCODING_FIXES:
        fixed = UNIT_ENCODING_FIXES[unit]
        fixes_applied.append((where, unit, fixed))
        unit = fixed
    if unit not in allowed:
        raise MigrationError(
            f"{where}: وحدة مش مسموحة {unit!r}. المسموح: {sorted(allowed)}. "
            "لو دي وحدة حقيقية، القيد هو اللي ناقص -- وسّعه بميجريشن، "
            "متحوّلهاش لوحدة تانية."
        )
    return unit


def build_payloads(project_id, doc):
    """يحوّل مستند Firestore لصفوف الجداول. بيرمي عند أي حاجة مش مفهومة."""
    fixes = []

    # ---------- projects ----------
    updated_candidates = []
    if isinstance(doc.get("updatedAt"), (int, float)):
        updated_candidates.append(
            datetime.fromtimestamp(doc["updatedAt"] / 1000, tz=timezone.utc)
        )
    if doc.get("last_updated"):
        try:
            updated_candidates.append(
                datetime.fromisoformat(str(doc["last_updated"]))
            )
        except ValueError:
            pass
    # العمودين في Firestore نسختين من نفس المعنى (`updatedAt` رقم من
    # الفرونت، `last_updated` نص ISO من آدم) وبيتدمجوا في عمود واحد.
    # بناخد الأحدث -- الأقدم مش معلومة زيادة، ده انعكاس للازدواج.
    updated_at = max(updated_candidates).isoformat() if updated_candidates else None

    created_by = doc.get("createdBy") or ""
    if "@" in created_by:
        created_by_kind = "email"
    elif created_by == "ADAM":
        created_by_kind = "adam"
    elif created_by:
        created_by_kind = "firebase_uid"
    else:
        created_by_kind = None

    completion = doc.get("completion")
    project_row = {
        "id": project_id,
        "name": doc.get("name") or None,
        "client": doc.get("client") or None,
        "area": doc.get("area"),
        "level": doc.get("level") or None,
        "status": doc.get("status") or None,
        "allowed_supervisors": doc.get("allowedSupervisors") or [],
        "note": doc.get("note") or None,
        "adam_notes": doc.get("adam_notes") or None,
        "created_by": created_by or None,
        "created_by_kind": created_by_kind,
        "deadline": doc.get("deadline") or None,
        # العمود نصي في السكيما والمصدر بيكتب رقم -- التحويل صريح هنا
        # بدل ما PostgREST يقرره.
        "completion": str(completion) if completion is not None else None,
        "last_report": doc.get("last_report") or None,
        "updated_at": updated_at,
    }

    # ---------- المقايسات ----------
    phases = []
    for block_name, phase in PHASE_BLOCKS.items():
        blk = doc.get(block_name)
        if not blk:
            continue
        items = blk.get("items") or []
        rows = []
        for pos, it in enumerate(items):        # الفهرس الصفري = الترتيب
            where = f"{block_name}[{pos}]"
            rows.append({
                "position": pos,
                "description": it.get("desc") or "",
                "unit": normalize_unit(it.get("unit"), PHASE_UNITS_ALLOWED, where, fixes),
                "qty": it.get("qty") or 0,
                "price": it.get("price") or 0,
                "is_sub": bool(it.get("sub")),
            })
        phases.append({
            "phase": phase,
            "estimate": {
                "project_id": project_id,
                "phase": phase,
                "client_text": blk.get("client") or None,
                "project_text": blk.get("project") or None,
                # نص خام بالقصد -- الفرونت مابيعملش parseFloat هنا
                "area_text": str(blk["area"]) if blk.get("area") is not None else None,
            },
            "items": rows,
        })

    # ---------- الحصر ----------
    quantity = None
    qblk = doc.get("quantity")
    if qblk:
        qrows = []
        for pos, it in enumerate(qblk.get("items") or []):
            where = f"quantity[{pos}]"
            images = it.get("images") or []
            if images:
                # الصور كانت base64 جوه المستند، وجدولها بيشيل مرجع تخزين
                # كائنات مش الصورة نفسها. مفيش مسار رفع في السكربت ده،
                # فوجود صورة معناه إن النقل هيضيّع داتا -- ووقفة أحسن.
                raise MigrationError(
                    f"{where}: فيه {len(images)} صورة مخزّنة. الجدول بيشيل "
                    "مرجع تخزين كائنات مش base64، والسكربت ده مفيهوش رفع. "
                    "النقل هيضيّعها -- اتوقفت."
                )
            phase = (it.get("phase") or "").strip() or None
            if phase is not None and phase not in ("foundation", "finish", "final"):
                raise MigrationError(f"{where}: مرحلة مش معروفة {phase!r}")
            qrows.append({
                "position": pos,
                "description": it.get("desc") or "",
                "unit": normalize_unit(it.get("unit"), QUANTITY_UNITS_ALLOWED, where, fixes),
                # الأبعاد الخام زي ما هي -- كل واحد في عموده
                "length": it.get("length") or 0,
                "width": it.get("width") or 0,
                "height": it.get("height") or 0,
                "count": it.get("count") if it.get("count") is not None else 1,
                "wastage_pct": it.get("wastage") or 0,
                "phase": phase,
            })
        quantity = {
            "header": {
                "project_id": project_id,
                "client_text": qblk.get("client") or None,
                "project_text": qblk.get("project") or None,
                "area_text": str(qblk["area"]) if qblk.get("area") is not None else None,
            },
            "items": qrows,
        }

    return project_row, phases, quantity, fixes


# ============================================================
# الكتابة في Supabase
# ============================================================

def _client():
    from services import supabase_service
    return supabase_service.supabase_client


def _count(table, column, value):
    resp = _client().table(table).select("*", count="exact").eq(column, value).execute()
    return resp.count if resp.count is not None else len(resp.data or [])


def write_all(project_id, project_row, phases, quantity):
    c = _client()

    # ---------- projects ----------
    c.table("projects").upsert(project_row, on_conflict="id").execute()

    # ---------- المقايسات ----------
    for ph in phases:
        c.table("project_phase_estimates").upsert(
            ph["estimate"], on_conflict="project_id,phase"
        ).execute()
        got = (
            c.table("project_phase_estimates").select("id")
            .eq("project_id", project_id).eq("phase", ph["phase"])
            .limit(1).execute()
        )
        if not got.data:
            raise MigrationError(
                f"project_phase_estimates: كتبت مرحلة {ph['phase']} وملقتهاش بعدها."
            )
        estimate_id = got.data[0]["id"]
        rows = [dict(r, estimate_id=estimate_id) for r in ph["items"]]
        if rows:
            try:
                c.table("project_phase_items").upsert(
                    rows, on_conflict="estimate_id,position"
                ).execute()
            except Exception as e:
                # الحالة الوحيدة المتوقعة هنا: ميجريشن 015 لسه ماتشغلتش،
                # فالقيد لسه أربع وحدات. الرسالة الخام بتقول اسم القيد
                # والصف الواقع وبس -- مش بتقول تعمل إيه.
                if "project_phase_items_unit_valid" in str(e):
                    used = sorted({r["unit"] for r in rows})
                    raise MigrationError(
                        "قيد الوحدات في project_phase_items لسه أربع وحدات.\n"
                        f"  المرحلة: {ph['phase']}\n"
                        f"  الوحدات المستخدمة فيها: {used}\n"
                        "  شغّل migrations/015_phase_item_units.sql في محرّر SQL "
                        "بتاع Supabase الأول (فيها DDL، ومش بتعدّي من PostgREST)، "
                        "وبعدين شغّل السكربت تاني -- الكتابة upsert فمفيش تكرار."
                    ) from None
                raise
        ph["_estimate_id"] = estimate_id

    # ---------- الحصر ----------
    if quantity:
        c.table("project_quantity").upsert(
            quantity["header"], on_conflict="project_id"
        ).execute()
        got = (
            c.table("project_quantity").select("id")
            .eq("project_id", project_id).limit(1).execute()
        )
        if not got.data:
            raise MigrationError("project_quantity: كتبت الرأس وملقيتهوش بعدها.")
        quantity_id = got.data[0]["id"]
        rows = [dict(r, quantity_id=quantity_id) for r in quantity["items"]]
        if rows:
            c.table("project_quantity_items").upsert(
                rows, on_conflict="quantity_id,position"
            ).execute()
        quantity["_quantity_id"] = quantity_id


def verify(project_id, phases, quantity):
    """العدّ بعد الكتابة. أي رقم مايطبقش بيوقف النقل باسم الجدول."""
    mismatches = []

    n = _count("projects", "id", project_id)
    if n != 1:
        mismatches.append(f"projects: متوقع 1، لقيت {n}")

    n = _count("project_phase_estimates", "project_id", project_id)
    if n != len(phases):
        mismatches.append(f"project_phase_estimates: متوقع {len(phases)}، لقيت {n}")

    for ph in phases:
        eid = ph.get("_estimate_id")
        want = len(ph["items"])
        got = _count("project_phase_items", "estimate_id", eid) if eid else 0
        if got != want:
            mismatches.append(
                f"project_phase_items[{ph['phase']}]: متوقع {want}، لقيت {got}"
            )

    want_q = 1 if quantity else 0
    n = _count("project_quantity", "project_id", project_id)
    if n != want_q:
        mismatches.append(f"project_quantity: متوقع {want_q}، لقيت {n}")

    if quantity:
        qid = quantity.get("_quantity_id")
        want = len(quantity["items"])
        got = _count("project_quantity_items", "quantity_id", qid) if qid else 0
        if got != want:
            mismatches.append(f"project_quantity_items: متوقع {want}، لقيت {got}")

    if mismatches:
        raise MigrationError(
            "العدّ بعد النقل مش مطابق:\n  - " + "\n  - ".join(mismatches)
        )
    return True


def verify_order(project_id, phases, quantity):
    """الترتيب حامل معنى التبعية -- بنتأكد إنه اتنقل حرفيًا.

    عدّ مطابق مش كفاية: 95 صف بترتيب متبعتر بيدّي نفس الرقم وهرم تابع
    مختلف تمامًا، لأن البند التابع بيتبع أقرب بند قبله وبس.
    """
    c = _client()
    problems = []

    for ph in phases:
        got = (
            c.table("project_phase_items")
            .select("position, description, is_sub")
            .eq("estimate_id", ph["_estimate_id"]).order("position").execute()
        )
        rows = got.data or []
        for want, have in zip(ph["items"], rows):
            if (want["position"] != have["position"]
                    or want["description"] != (have["description"] or "")
                    or want["is_sub"] != have["is_sub"]):
                problems.append(
                    f"project_phase_items[{ph['phase']}] موضع {want['position']}: "
                    f"المصدر {want['description'][:40]!r}/sub={want['is_sub']} != "
                    f"الهدف {(have['description'] or '')[:40]!r}/sub={have['is_sub']}"
                )
                break

    if quantity:
        got = (
            c.table("project_quantity_items")
            .select("position, description, length, width, height, count")
            .eq("quantity_id", quantity["_quantity_id"]).order("position").execute()
        )
        for want, have in zip(quantity["items"], got.data or []):
            same_dims = all(
                float(want[k]) == float(have[k] or 0)
                for k in ("length", "width", "height", "count")
            )
            if want["position"] != have["position"] or not same_dims:
                problems.append(
                    f"project_quantity_items موضع {want['position']}: "
                    f"الأبعاد الخام مش مطابقة -- المصدر "
                    f"{[want[k] for k in ('length','width','height','count')]} != "
                    f"الهدف {[have[k] for k in ('length','width','height','count')]}"
                )
                break

    if problems:
        raise MigrationError("الترتيب أو الأبعاد اتغيّروا:\n  - " + "\n  - ".join(problems))
    return True


# ============================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_id", nargs="?", default="PRJ-MRE9OHLK")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="اقرا واعرض، من غير أي كتابة")
    g.add_argument("--write", action="store_true", help="اكتب فعلاً في Supabase")
    args = ap.parse_args()

    doc = read_source(args.project_id)
    project_row, phases, quantity, fixes = build_payloads(args.project_id, doc)

    source_total = sum(len(p["items"]) for p in phases) + (
        len(quantity["items"]) if quantity else 0
    )

    log("=" * 60)
    log(f"المصدر: Firestore/projects/{args.project_id}")
    log(f"  {project_row['name']} — {project_row['client']}")
    log("=" * 60)
    log(f"projects                   1 صف")
    log(f"project_phase_estimates    {len(phases)} صف")
    for ph in phases:
        log(f"  project_phase_items[{ph['phase']:10s}] {len(ph['items']):3d} بند")
    log(f"project_quantity           {1 if quantity else 0} صف")
    if quantity:
        log(f"  project_quantity_items      {len(quantity['items']):3d} بند")
    log(f"\nإجمالي البنود: {source_total}")

    if fixes:
        log(f"\nتطبيع ترميز الوحدات ({len(fixes)} بند) -- كل واحد بالاسم:")
        for where, before, after in fixes:
            log(f"  {where:22s} {before!r} -> {after!r}")
    else:
        log("\nمفيش أي تطبيع وحدات.")

    if args.dry_run:
        log("\n[dry-run] مكتبتش أي حاجة. للتنفيذ: --write")
        return 0

    log("\nبكتب في Supabase...")
    from services.supabase_service import init_supabase, bypasses_rls
    if not init_supabase():
        raise MigrationError("مقدرتش أتصل بـSupabase.")
    if not bypasses_rls():
        raise MigrationError(
            "المفتاح مش بيتخطى RLS -- الكتابة هتترفض والقراءة هترجّع [] كذبًا."
        )

    write_all(args.project_id, project_row, phases, quantity)
    verify(args.project_id, phases, quantity)
    verify_order(args.project_id, phases, quantity)

    log("\n✅ النقل خلص والعدّ مطابق والترتيب محفوظ.")
    log("   Firestore زي ما هو -- نسخة يتيمة، مالمستهاش.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MigrationError as e:
        print("\n❌ النقل اتوقف:\n" + str(e), file=sys.stderr)
        raise SystemExit(1)
