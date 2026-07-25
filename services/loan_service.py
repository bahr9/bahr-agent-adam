# -*- coding: utf-8 -*-
"""
💳 خدمة متابعة الأقساط والقروض
- جدول الأقساط الثابت لكل برنامج (فاليو، سهولة، Credit Agricole، إلخ)
- حساب الملخصات (المدفوع، المتبقي، أقساط الشهر الحالي/القادم)
- حالة "مدفوع/لأ" بتتخزن في Firestore (بدل window.storage بتاعة الـ React app الأصلية)
"""

from utils.time_utils import now_cairo
from utils.logger import logger

# ============================================================
# 📋 جدول البرامج الثابت (نفس بيانات تطبيق الأقساط الأصلي)
# ============================================================

def _build_programs():
    """بناء جدول البرامج والأقساط (نفس منطق ملف الـ React الأصلي)"""

    def monthly(amount, count, start_month=7, start_year=2026):
        result = []
        for i in range(count):
            m = ((start_month - 1 + i) % 12) + 1
            y = start_year + (start_month - 1 + i) // 12
            result.append({"date": f"01/{m:02d}/{y}", "amount": amount})
        return result

    programs = [
        {
            "id": "valu",
            "name": "فاليو",
            "installments": [
                {"date": "01/07/2026", "amount": 32149},
                {"date": "01/08/2026", "amount": 32149},
                {"date": "01/09/2026", "amount": 20373},
                {"date": "01/10/2026", "amount": 11544},
                {"date": "01/11/2026", "amount": 11106},
                {"date": "01/12/2026", "amount": 6190},
            ],
        },
        {
            "id": "souhoula",
            "name": "سهولة",
            "installments": monthly(7241, 6),
        },
        {
            "id": "ca",
            "name": "Credit Agricole",
            "installments": monthly(13000, 72),
        },
        {
            "id": "halan",
            "name": "حالا",
            "installments": monthly(10268, 4),
        },
        {
            "id": "premium",
            "name": "بريميم كارد",
            "installments": monthly(10261, 3),
        },
        {
            "id": "mani",
            "name": "ماني فيلوز",
            "installments": monthly(5400, 6),
        },
        {
            "id": "fawry",
            "name": "فوري",
            "installments": None,  # هيتحسب لوحده تحت
        },
    ]

    # فوري: 3 أقساط مبالغها مختلفة + 19 قسط بنفس المبلغ
    fawry_amounts = [4327, 4152, 4152] + [2161] * 19
    fawry_installments = []
    for i, amount in enumerate(fawry_amounts):
        m = ((7 - 1 + i) % 12) + 1
        y = 2026 + (7 - 1 + i) // 12
        fawry_installments.append({"date": f"01/{m:02d}/{y}", "amount": amount})

    for p in programs:
        if p["id"] == "fawry":
            p["installments"] = fawry_installments

    return programs

PROGRAMS = _build_programs()

# اسم عربي أو إنجليزي مرن للبحث عن البرنامج
PROGRAM_NAME_MAP = {p["id"]: p["name"] for p in PROGRAMS}


def _find_program(program_name):
    """بحث مرن عن البرنامج بالاسم أو الـ id"""
    search = program_name.strip().lower()
    for p in PROGRAMS:
        if search in p["name"].lower() or search in p["id"].lower() or p["id"].lower() in search:
            return p
    return None


def get_current_month_key():
    now = now_cairo()
    return f"01/{now.month:02d}/{now.year}"


def get_next_month_key():
    now = now_cairo()
    next_month = now.month + 1
    year = now.year
    if next_month > 12:
        next_month = 1
        year += 1
    return f"01/{next_month:02d}/{year}"


# ============================================================
# 💾 حالة الدفع (مخزّنة في Firestore)
# ============================================================

def _get_paid_map():
    from services.firebase_service import get_loan_paid_map
    return get_loan_paid_map()


def is_paid(program_id, index, paid_map=None):
    if paid_map is None:
        paid_map = _get_paid_map()
    return bool(paid_map.get(f"{program_id}_{index}"))


# ملاحظة: الكتابة المباشرة لحالة الدفع (set_paid / mark_installment_paid) اتشالت
# في Stage 2 (ADAM Self-State & Observation System). الكتابة دلوقتي بتمر حصريًا
# من services/loan_commands.py عبر event_store.record_event_with_write --
# مفيش مسار كتابة تاني هنا عن قصد.


# ============================================================
# 📊 الملخصات
# ============================================================

def get_overview():
    """ملخص شامل: الإجمالي المدفوع/المتبقي لكل برنامج + الإجمالي الكلي"""
    paid_map = _get_paid_map()

    lines = []
    total_paid = 0
    total_remaining = 0

    for p in PROGRAMS:
        program_total = sum(x["amount"] for x in p["installments"])
        program_paid = sum(
            x["amount"] for i, x in enumerate(p["installments"]) if is_paid(p["id"], i, paid_map)
        )
        program_remaining = program_total - program_paid
        paid_count = sum(1 for i in range(len(p["installments"])) if is_paid(p["id"], i, paid_map))

        total_paid += program_paid
        total_remaining += program_remaining

        lines.append(
            f"- {p['name']}: {paid_count}/{len(p['installments'])} قسط مدفوع | "
            f"مدفوع {program_paid} جنيه | متبقي {program_remaining} جنيه"
        )

    return {
        "total_paid": total_paid,
        "total_remaining": total_remaining,
        "details_text": "\n".join(lines)
    }


def get_month_installments(month_key):
    """أقساط شهر معيّن (بصيغة 01/MM/YYYY) لكل البرامج"""
    paid_map = _get_paid_map()
    items = []

    for p in PROGRAMS:
        for i, inst in enumerate(p["installments"]):
            if inst["date"] == month_key:
                items.append({
                    "program": p["name"],
                    "program_id": p["id"],
                    "index": i,
                    "amount": inst["amount"],
                    "paid": is_paid(p["id"], i, paid_map)
                })

    total = sum(x["amount"] for x in items)
    return items, total
