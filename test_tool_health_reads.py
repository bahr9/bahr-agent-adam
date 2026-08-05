# -*- coding: utf-8 -*-
"""
Tests First -- تكلفة القراءة في tool_health_engine (حادثة كوتا 2026-08-05).

الحادثة: `_fetch_all` كانت بتعمل `.stream()` على مجموعة `tool_health_checks`
**كاملة** من غير فلتر ولا حد، وتفلتر النافذة الزمنية في بايثون بعد كده.
المجموعة دي بتكبر للأبد (الـ heartbeat بيكتب سجل لكل أداة من 61 أداة كل
6 ساعات، ومفيش job تنظيف)، والدالة بتتنادى كل ساعة من فحص الحالة الذاتية
وكمان مع كل نداء لـ get_adam_self_state / get_tools_health_status.

المقاس في الإنتاج: **53 ألف قراءة مقابل 156 كتابة** في يوم واحد -- الكوتا
المجانية (50 ألف) خلصت وآدم اتشل عن أي قراءة من Firestore.

الاختبارات دي بتقيس عدد القراءات بالرقم (fake_firestore بيعدّها)، وبتتأكد
إن النتيجة النهائية للتصنيف **مطابقة** للسلوك القديم -- التوفير في التكلفة
بس، مش في الدقة.
"""

from datetime import timedelta


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
    from fake_firestore import use_fake_firestore
    from services import tool_health_engine as eng
    from config import TOOL_HEALTH_CHECKS_COLLECTION, TOOL_FAILURES_LOG_COLLECTION
    from utils.time_utils import now_cairo

    now = now_cairo()

    def seeded_db(old_count, recent_count, tool="list_graph_nodes", result="success"):
        """مجموعة فيها سجلات قديمة كتير + سجلات قليلة جوه النافذة."""
        seed = {TOOL_HEALTH_CHECKS_COLLECTION: {}, TOOL_FAILURES_LOG_COLLECTION: {}}
        for i in range(old_count):
            stamp = (now - timedelta(days=5 + i % 30)).isoformat()
            seed[TOOL_HEALTH_CHECKS_COLLECTION][f"old_{i}"] = {
                "tool_name": tool, "result": result, "checked_at": stamp,
                "evidence_event_id": f"ev_old_{i}",
            }
        for i in range(recent_count):
            stamp = (now - timedelta(hours=1 + i % 20)).isoformat()
            seed[TOOL_HEALTH_CHECKS_COLLECTION][f"new_{i}"] = {
                "tool_name": tool, "result": result, "checked_at": stamp,
                "evidence_event_id": f"ev_new_{i}",
            }
        return seed

    results = []

    # ---------- الحارس الأساسي: التكلفة ----------
    def reads_scale_with_the_window_not_the_collection():
        """5000 سجل قديم + 40 جوه النافذة = لازم نقرا ~40 مش 5040."""
        with use_fake_firestore(seed=seeded_db(5000, 40)) as db:
            db.reset_reads()
            eng.evaluate_all_tools()
            assert db.reads < 200, (
                f"اتقرا {db.reads} مستند -- المفروض عشرات مش آلاف. "
                "ده معناه إن القراءة لسه على المجموعة كاملة."
            )

    def a_huge_collection_does_not_cost_more():
        """التكلفة تفضل تقريبًا ثابتة مهما كبرت المجموعة -- ده جوهر الإصلاح."""
        with use_fake_firestore(seed=seeded_db(500, 40)) as db:
            db.reset_reads()
            eng.evaluate_all_tools()
            small = db.reads
        with use_fake_firestore(seed=seeded_db(20000, 40)) as db:
            db.reset_reads()
            eng.evaluate_all_tools()
            huge = db.reads
        assert huge <= small + 5, (
            f"مجموعة أكبر 40 مرة كلّفت {huge} قراءة مقابل {small} -- التكلفة لسه مربوطة بالحجم"
        )

    def the_hard_cap_is_enforced():
        """حتى لو كل السجلات جوه النافذة، فيه سقف مايتعداش."""
        seed = {TOOL_HEALTH_CHECKS_COLLECTION: {}, TOOL_FAILURES_LOG_COLLECTION: {}}
        for i in range(eng.MAX_RECORDS_PER_FETCH + 500):
            seed[TOOL_HEALTH_CHECKS_COLLECTION][f"r_{i}"] = {
                "tool_name": "list_graph_nodes", "result": "success",
                "checked_at": (now - timedelta(minutes=5)).isoformat(),
                "evidence_event_id": f"ev_{i}",
            }
        with use_fake_firestore(seed=seed) as db:
            db.reset_reads()
            eng.evaluate_all_tools()
            assert db.reads <= eng.MAX_RECORDS_PER_FETCH + 10, db.reads

    # ---------- الدقة: النتيجة لازم تفضل زي ما هي ----------
    def old_records_are_still_excluded():
        """السجلات خارج النافذة ماتأثرش على التصنيف -- زي الأول بالظبط."""
        with use_fake_firestore(seed=seeded_db(300, 0)) as db:
            evaluations = eng.evaluate_all_tools()
            assert evaluations["list_graph_nodes"]["status"] == "UNKNOWN", (
                "سجلات قديمة برة النافذة اتحسبت: " + str(evaluations["list_graph_nodes"])
            )

    def enough_recent_successes_give_healthy():
        with use_fake_firestore(seed=seeded_db(2000, 5)) as db:
            evaluations = eng.evaluate_all_tools()
            ev = evaluations["list_graph_nodes"]
            assert ev["status"] == "HEALTHY", ev
            assert ev["detail"]["successful_checks"] == 5, ev

    def recent_failures_still_degrade():
        seed = {TOOL_HEALTH_CHECKS_COLLECTION: {}, TOOL_FAILURES_LOG_COLLECTION: {}}
        for i in range(3):
            seed[TOOL_HEALTH_CHECKS_COLLECTION][f"f_{i}"] = {
                "tool_name": "list_graph_nodes", "result": "failure",
                "error_type": "Timeout",
                "checked_at": (now - timedelta(hours=2)).isoformat(),
                "evidence_event_id": f"ev_f_{i}",
            }
        with use_fake_firestore(seed=seed):
            ev = eng.evaluate_all_tools()["list_graph_nodes"]
            assert ev["status"] == "DEGRADED", ev

    def real_use_failures_are_read_too():
        """مجموعة الفشل الحقيقي بتتقرا بنفس منطق النافذة."""
        seed = {TOOL_HEALTH_CHECKS_COLLECTION: {}, TOOL_FAILURES_LOG_COLLECTION: {}}
        for i in range(3):
            seed[TOOL_FAILURES_LOG_COLLECTION][f"rf_{i}"] = {
                "tool_name": "create_project", "error_type": "PermissionDenied",
                "failed_at": (now - timedelta(hours=3)).isoformat(),
                "evidence_event_id": f"ev_rf_{i}",
            }
        seed[TOOL_FAILURES_LOG_COLLECTION]["ancient"] = {
            "tool_name": "create_project", "error_type": "PermissionDenied",
            "failed_at": (now - timedelta(days=40)).isoformat(),
            "evidence_event_id": "ev_ancient",
        }
        with use_fake_firestore(seed=seed):
            ev = eng.evaluate_all_tools()["create_project"]
            assert ev["status"] == "DEGRADED", ev
            assert ev["detail"]["failures_total"] == 3, (
                "السجل القديم اتحسب: " + str(ev["detail"])
            )

    def records_without_a_timestamp_are_skipped():
        """سجل ناقص الحقل الزمني ماينفعش يتحسب جوه النافذة."""
        seed = {
            TOOL_HEALTH_CHECKS_COLLECTION: {
                "broken": {"tool_name": "list_graph_nodes", "result": "success"},
            },
            TOOL_FAILURES_LOG_COLLECTION: {},
        }
        with use_fake_firestore(seed=seed):
            ev = eng.evaluate_all_tools()["list_graph_nodes"]
            assert ev["status"] == "UNKNOWN", ev

    def empty_collections_are_not_an_error():
        with use_fake_firestore(seed={}) as db:
            evaluations = eng.evaluate_all_tools()
            assert len(evaluations) > 0, "الـ registry المفروض يرجّع أدوات"
            assert all("status" in ev for ev in evaluations.values())


    # ---------- النجاح الحقيقي كدليل (أوديت 2026-08-05 مساءً) ----------
    def real_use_success_promotes_an_unprobed_tool():
        """الحارس الأساسي الجديد: أداة من غير probe اتنفذت ونجحت = HEALTHY.
        قبل الإصلاح كانت بتفضل NOT_MONITORED للأبد مهما اشتغلت."""
        seed = {TOOL_HEALTH_CHECKS_COLLECTION: {}, TOOL_FAILURES_LOG_COLLECTION: {}}
        seed[TOOL_HEALTH_CHECKS_COLLECTION]["ru_1"] = {
            "tool_name": "save_price", "result": "success",
            "probe_version": "real_use",
            "checked_at": (now - timedelta(hours=1)).isoformat(),
            "evidence_event_id": None,
        }
        with use_fake_firestore(seed=seed):
            ev = eng.evaluate_all_tools()["save_price"]
            assert ev["status"] == "HEALTHY", ev
            assert ev["detail"].get("evidence") == "real_use", ev

    def unprobed_tool_with_no_usage_stays_not_monitored():
        """أداة من غير probe ومن غير أي استخدام -- NOT_MONITORED صادقة."""
        with use_fake_firestore(seed={}):
            ev = eng.evaluate_all_tools()["save_price"]
            assert ev["status"] == "NOT_MONITORED", ev

    def real_use_failure_still_wins_over_success():
        """فشل حقيقي بيتغلب على النجاح -- مش بنجمّل الصورة."""
        seed = {TOOL_HEALTH_CHECKS_COLLECTION: {}, TOOL_FAILURES_LOG_COLLECTION: {}}
        seed[TOOL_HEALTH_CHECKS_COLLECTION]["ru_ok"] = {
            "tool_name": "save_price", "result": "success",
            "probe_version": "real_use",
            "checked_at": (now - timedelta(hours=2)).isoformat(),
        }
        for i in range(2):
            seed[TOOL_FAILURES_LOG_COLLECTION][f"f_{i}"] = {
                "tool_name": "save_price", "error_type": "PermissionDenied",
                "failed_at": (now - timedelta(hours=1)).isoformat(),
                "evidence_event_id": f"ev_{i}",
            }
        with use_fake_firestore(seed=seed):
            ev = eng.evaluate_all_tools()["save_price"]
            assert ev["status"] == "DEGRADED", ev

    def old_real_use_success_outside_window_does_not_count():
        seed = {TOOL_HEALTH_CHECKS_COLLECTION: {}, TOOL_FAILURES_LOG_COLLECTION: {}}
        seed[TOOL_HEALTH_CHECKS_COLLECTION]["old_ru"] = {
            "tool_name": "save_price", "result": "success",
            "probe_version": "real_use",
            "checked_at": (now - timedelta(days=3)).isoformat(),
        }
        with use_fake_firestore(seed=seed):
            ev = eng.evaluate_all_tools()["save_price"]
            assert ev["status"] == "NOT_MONITORED", ev

    def real_use_counts_toward_probed_tool_sample():
        """للأداة المفحوصة: نجاح حقيقي + heartbeats بيكملوا العينة سوا."""
        seed = {TOOL_HEALTH_CHECKS_COLLECTION: {}, TOOL_FAILURES_LOG_COLLECTION: {}}
        for i in range(2):
            seed[TOOL_HEALTH_CHECKS_COLLECTION][f"hb_{i}"] = {
                "tool_name": "list_graph_nodes", "result": "success",
                "probe_version": "v1",
                "checked_at": (now - timedelta(hours=2 + i)).isoformat(),
                "evidence_event_id": f"hb_ev_{i}",
            }
        seed[TOOL_HEALTH_CHECKS_COLLECTION]["ru"] = {
            "tool_name": "list_graph_nodes", "result": "success",
            "probe_version": "real_use",
            "checked_at": (now - timedelta(minutes=30)).isoformat(),
        }
        with use_fake_firestore(seed=seed):
            ev = eng.evaluate_all_tools()["list_graph_nodes"]
            assert ev["status"] == "HEALTHY", ev
            assert ev["detail"]["successful_checks"] == 3, ev

    for name, fn in [
        ("التكلفة مربوطة بالنافذة مش بحجم المجموعة (الحارس الأساسي)", reads_scale_with_the_window_not_the_collection),
        ("مجموعة أكبر 40 مرة ماتكلّفش أكتر", a_huge_collection_does_not_cost_more),
        ("السقف الصارم بيتطبق", the_hard_cap_is_enforced),
        ("السجلات القديمة لسه مستبعدة من التصنيف", old_records_are_still_excluded),
        ("نجاحات كافية جوه النافذة = HEALTHY", enough_recent_successes_give_healthy),
        ("فشل حديث لسه بيدي DEGRADED", recent_failures_still_degrade),
        ("سجل الفشل الحقيقي بيتقرا بنفس المنطق", real_use_failures_are_read_too),
        ("سجل من غير تاريخ بيتخطى", records_without_a_timestamp_are_skipped),
        ("مجموعات فاضية مش خطأ", empty_collections_are_not_an_error),
        ("نجاح حقيقي بيخلي أداة بلا probe سليمة (الحارس الجديد)", real_use_success_promotes_an_unprobed_tool),
        ("بلا probe وبلا استخدام = غير مُراقَبة بصدق", unprobed_tool_with_no_usage_stays_not_monitored),
        ("الفشل بيتغلب على النجاح -- مفيش تجميل", real_use_failure_still_wins_over_success),
        ("نجاح قديم برة النافذة مش بيتحسب", old_real_use_success_outside_window_does_not_count),
        ("النجاح الحقيقي بيكمّل عينة الأداة المفحوصة", real_use_counts_toward_probed_tool_sample),
    ]:
        results.append(run_test(name, fn))

    print()
    passed = sum(1 for r in results if r)
    print(f"{passed}/{len(results)} اختبار عدّى")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
